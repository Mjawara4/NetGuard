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
    - devices (id, name, ip_address, site_id, is_active, device_type) -- 'device_type' is a COLUMN in 'devices' table!
    - sites (id, name, location, organization_id)
    - metrics (time, device_id, metric_type, value)
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
    You are a Network Operations Assistant for "NetGuard".
    
    Database Schema:
    {schema}
    
    User Query: "{user_query}"
    Organization ID: {organization_id}

    Task: Determine intent and return valid JSON.

    YOUR CAPABILITIES (SCOPE):
    1. **Data Retrieval**: You can query the database for:
       - Devices (inventory, status, IPs)
       - Sites (locations, names)
       - Metrics (cpu, memory, latency history)
       - Alerts (active, past, critical issues)
       - Hotspot Sales (revenue, vouchers, user sessions)
       
    2. **Device Actions**: You can perform these specific actions via SSH:
       - Reboot a device
       - Restart a service (nginx, docker, wireguard)
       - Reset persistent issues

    INTENT CATEGORIES:
    
    Type 1: SQL (Data Retrieval)
    - Output: {{ "type": "SQL", "content": "VALID_POSTGRES_SQL" }}
    - Rule: ALWAYS enforce `organization_id = '{organization_id}'` in WHERE clauses.
    
    Type 2: ACTION (State Change)
    - Output: {{ "type": "ACTION", "action": "reboot|restart_service", "target_device_name": "fuzzy_match_name", "command": "shell_command" }}
    - Rule: Only allow safe, recognized actions.
    
    Type 3: HELP (Out of Scope / Clarity Needed)
    - Use this if the user asks about:
      - Things outside of network management (e.g., "write a poem", "weather forecast")
      - Features NetGuard doesn't have (e.g., "order pizza")
      - Vague requests where you don't know if they want data or action.
    - Output: {{ "type": "HELP", "message": "A friendly message explaining what you CAN do (Data & Actions) and asking them to rephrase." }}
    
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


def explain_result(user_query, result_data, total_count):
    """
    Asks LLM to explain the SQL result in natural language.
    """
    if not result_data:
        return "No results found matching your query."

    # Limit context size
    data_sample = result_data[:20]
    
    prompt = f"""
    You are a helpful Network Ops Assistant.
    
    User Query: "{user_query}"
    
    Data Found ({len(data_sample)} of {total_count} records):
    {data_sample}
    
    Task: Answer the user's question based on this data.
    - Be concise and friendly.
    - Summarize key findings (e.g., "Found 5 critical CPU alerts").
    - If list is long, mention only the most important items (e.g., critical severity).
    - Do not simply list all tuples.
    """
    
    try:
        if LLM_PROVIDER == "gemini":
            from google import genai
            client = genai.Client(api_key=LLM_API_KEY)
            resp = client.models.generate_content(
                model='gemini-2.5-flash-lite',
                contents=prompt
            )
            return resp.text.strip()
            
        elif LLM_PROVIDER == "openai":
            client = openai.OpenAI(api_key=LLM_API_KEY)
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}]
            )
            return completion.choices[0].message.content.strip()
            
    except Exception as e:
        logger.error(f"Explanation Error: {e}")
        return f"Found {total_count} records, but could not summarize them due to an error."

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
        target_user = result_json.get("target_user")
        command = result_json.get("command")
        
        # 1. CLEAR ALERTS (No device needed)
        if action == "clear_alerts":
            try:
                # Re-use logic from monitoring.py (but we can't import the router function easily as it depends on request context)
                # So we simulate it here:
                from app.models import Alert
                from app.models.monitoring import AlertStatus
                
                # Fetch open alerts
                query = text("""
                    UPDATE alerts 
                    SET status = 'archived' 
                    FROM devices, sites
                    WHERE alerts.device_id = devices.id 
                    AND devices.site_id = sites.id 
                    AND sites.organization_id = :org_id 
                    AND alerts.status != 'archived'
                """)
                await db.execute(query, {"org_id": current_user.organization_id})
                await db.commit()
                return ChatResponse(response="✅ **All alerts have been cleared/archived.**")
            except Exception as e:
                logger.error(f"Clear Alerts Failed: {e}")
                return ChatResponse(response=f"Failed to clear alerts. Error: {e}")

        # 2. DEVICE ACTIONS (Reboot, Restart, Kick User)
        if not target_name:
             return ChatResponse(response="I need to know which device you are referring to.")

        # Resolve Device (Filtered by Org)
        try:
            query = text("""
                SELECT d.id, d.name, d.ip_address, d.ssh_username, d.ssh_password, d.ssh_port 
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
            
            # Decrypt password
            from app.utils.encryption import decrypt_value
            ssh_pass = decrypt_value(device.ssh_password) if device.ssh_password else None
            
            # Sub-Action: KICK USER
            if action == "kick_user":
                if not target_user:
                     return ChatResponse(response="Please specify which user to kick.")
                     
                import routeros_api
                try:
                    # Connect to Router
                    port = 8728 if not device.ssh_port or int(device.ssh_port) == 22 else int(device.ssh_port)
                    pool = routeros_api.RouterOsApiPool(
                        device.ip_address, 
                        username=device.ssh_username or 'admin', 
                        password=ssh_pass or 'admin', 
                        port=port,
                        plaintext_login=True, 
                        use_ssl=False
                    )
                    api = pool.get_api()
                    
                    # Find Active Session
                    active_resource = api.get_resource('/ip/hotspot/active')
                    active_sessions = active_resource.get(user=target_user)
                    
                    if not active_sessions:
                        pool.disconnect()
                        return ChatResponse(response=f"User '{target_user}' is not currently active on {device.name}.")
                        
                    # Remove (Kick)
                    for session in active_sessions:
                        active_resource.remove(id=session.get('.id') or session.get('id'))
                        
                    pool.disconnect()
                    return ChatResponse(response=f"✅ **User '{target_user}' has been kicked** from {device.name}.")
                    
                except Exception as e:
                    logger.error(f"Kick User Failed: {e}")
                    return ChatResponse(response=f"Failed to kick user. Router Error: {e}")

            # Sub-Action: SSH COMMANDS (Reboot, Restart)
            elif action in ["reboot", "restart_service"]:
                if action == "reboot":
                     cmd = "reboot"
                elif action == "restart_service":
                     cmd = command if command else "echo 'No command provided'"
                
                # Exec
                ssh_output = execute_ssh_command(
                    host=device.ip_address,
                    command=cmd,
                    user=device.ssh_username, 
                    password=ssh_pass
                )
                return ChatResponse(response=f"✅ **Action Executed**\n\nTarget: {device.name}\nCommand: `{cmd}`\n\nOutput:\n```\n{ssh_output}\n```")
            
            else:
                 return ChatResponse(response=f"I don't know how to perform action: {action}")

        except Exception as e:
             logger.error(f"Action Execution Failed: {e}")
             return ChatResponse(response=f"Failed to execute action. Error: {str(e)}")
             
    elif intent_type == "HELP":
        return ChatResponse(response=result_json.get("message", "I can help you view network data (Devices, Alerts, Sales) or perform actions (Reboot, Kicking Users)."))
             
    else:
        return ChatResponse(response="I'm not sure if you want data or an action. Try asking 'Show me critical alerts' or 'Reboot router X'.")
