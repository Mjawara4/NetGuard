from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
import os
import logging
import openai

# Configure Logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
LLM_API_KEY = os.getenv("GEMINI_API_KEY") if LLM_PROVIDER == "gemini" else os.getenv("OPENAI_API_KEY")

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    response: str
    sql_query: str | None = None

def get_db_schema_context():
    """
    Returns a simplified schema representation for the LLM.
    """
    return """
    Tables:
    - devices (id, name, ip_address, site_id, is_active, device_type)
    - sites (id, name, location, organization_id)
    - metrics (time, device_id, metric_type, value) -- metric_types: cpu, memory, latency, uptime_status
    - alerts (id, device_id, rule_name, severity, status, message, created_at)
    - hotspot_sales (id, username, price, created_at, site_id)
    """

from app.auth.deps import get_current_user
from app.models import User

# ... import statements ...

from app.services.device_control import execute_ssh_command
from sqlalchemy import text # Ensure text is imported

def ask_llm_intent(user_query: str, organization_id: str):
    """
    Asks the LLM to determine if the user wants to querying DATA (SQL) or performing an ACTION (Command).
    """
    if not LLM_API_KEY:
        return None, "Error: LLM API Key not configured.", None

    schema = get_db_schema_context()
    
    system_prompt = f"""
    You are a Network Operations Assistant.
    
    Database Schema:
    {schema}
    
    User Query: "{user_query}"
    
    Organization ID: {organization_id}

    Task: Determine intent.
    
    Type 1: DATA RETRIEVAL (User asks for info, stats, alerts, list devices)
    - Output JSON: {{"type": "SQL", "content": "VALID_POSTGRES_SQL"}}
    - Enforce Organization ID restriction in WHERE clauses.
    
    Type 2: ACTION (User wants to change state: reboot, restart, block, reset)
    - Output JSON: {{"type": "ACTION", "action": "reboot|restart_service|other", "target_device_name": "exact name or fuzzy match", "command": "shell command if applicable"}}
    - Note: Only allow safe actions.
    
    Output strictly JSON.
    """

    try:
        import json
        response_text = ""
        
        if LLM_PROVIDER == "gemini":
            from google import genai
            client = genai.Client(api_key=LLM_API_KEY)
            resp = client.models.generate_content(
                model='gemini-2.5-flash-lite',
                contents=system_prompt
            )
            response_text = resp.text
            
        elif LLM_PROVIDER == "openai":
            client = openai.OpenAI(api_key=LLM_API_KEY)
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": system_prompt}],
                response_format={"type": "json_object"}
            )
            response_text = completion.choices[0].message.content

        # Clean JSON
        response_text = response_text.replace("```json", "").replace("```", "").strip()
        data = json.loads(response_text)
        return data, None

    except Exception as e:
        logger.error(f"LLM Intent Error: {e}")
        return None, f"LLM Error: {str(e)}"


# ... explain_result ...

@router.post("/chat", response_model=ChatResponse)
async def chat_with_network(
    request: ChatRequest, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Chat with your network data using AI. Supports Queries and Actions.
    """
    user_query = request.query
    
    # 1. Determine Intent
    result_json, error = ask_llm_intent(user_query, str(current_user.organization_id))
    
    if error:
         return ChatResponse(response=f"System Error: {error}")
    
    if not result_json:
         return ChatResponse(response="I couldn't understand your request.")

    intent_type = result_json.get("type")
    
    # --- HANDLE SQL QUERIES ---
    if intent_type == "SQL":
        sql = result_json.get("content")
        if not sql or sql == "NO_SQL":
             return ChatResponse(response="I couldn't understand how to query the database for that.")
             
        # Safety Check
        if any(keyword in sql.upper() for keyword in ["DELETE", "DROP", "UPDATE", "INSERT", "TRUNCATE", "ALTER"]):
            return ChatResponse(response="I cannot execute destructive queries. Read-only access only.", sql_query=sql)

        try:
            result = await db.execute(text(sql))
            rows = result.fetchall()
            data = [str(row) for row in rows]
            summary = explain_result(user_query, data, len(data))
            return ChatResponse(response=summary, sql_query=sql)
            
        except Exception as e:
            logger.error(f"SQL Execution Failed: {e}")
            return ChatResponse(response=f"The generated query failed to execute. Error: {str(e)}", sql_query=sql)
            
    # --- HANDLE ACTIONS ---
    elif intent_type == "ACTION":
        target_name = result_json.get("target_device_name")
        action = result_json.get("action")
        command = result_json.get("command")
        
        if not target_name:
            return ChatResponse(response="I understood you want to perform an action, but I couldn't identify the device.")

        # Resolve Device (Filtered by Org)
        try:
            # We must select ssh_username/ssh_password (fixing my previous mistake)
            query = text("""
                SELECT d.id, d.name, d.ip_address, d.ssh_username, d.ssh_password 
                FROM devices d
                JOIN sites s ON d.site_id = s.id
                WHERE s.organization_id = :org_id
                AND d.name ILIKE :name
                LIMIT 1
            """)
            result = await db.execute(query, {
                "org_id": current_user.organization_id, 
                "name": f"%{target_name}%"
            })
            device = result.one_or_none()
            
            if not device:
                 return ChatResponse(response=f"I couldn't find a device named '{target_name}' in your organization.")
            
            # Decrypt password if present
            from app.utils.encryption import decrypt_value
            ssh_pass = decrypt_value(device.ssh_password) if device.ssh_password else None
                 
            # EXECUTE
            if action == "reboot":
                 cmd = "reboot"
            elif action == "restart_service":
                 cmd = command if command else "echo 'No command provided'"
            else:
                 return ChatResponse(response=f"I don't know how to perform action: {action}")
                 
            # Call Service
            ssh_output = execute_ssh_command(
                host=device.ip_address,
                command=cmd,
                user=device.ssh_username, 
                password=ssh_pass
            )
            
            return ChatResponse(response=f"✅ **Action Executed**\n\nTarget: {device.name} ({device.ip_address})\nCommand: `{cmd}`\n\nOutput:\n```\n{ssh_output}\n```")

        except Exception as e:
             logger.error(f"Action Execution Failed: {e}")
             return ChatResponse(response=f"Failed to execute action. Error: {str(e)}")
             
    else:
        return ChatResponse(response="I'm not sure if you want data or an action.")
