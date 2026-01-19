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

def ask_llm_sql(user_query: str, organization_id: str):
    """
    Asks the LLM to generate a SQL query (PostgreSQL) based on the user request.
    Enforces Strict Multi-Tenancy.
    """
    if not LLM_API_KEY:
        return "Error: LLM API Key not configured.", None

    schema = get_db_schema_context()
    system_prompt = f"""
    You are a PostgreSQL expert for a Network Management System.
    
    Database Schema:
    {schema}
    
    CRITICAL SECURITY RULE (MULTI-TENANCY):
    You MUST RESTRICT all data to the Organization ID: '{organization_id}'.
    - For 'sites' table: WHERE organization_id = '{organization_id}'
    - For 'devices' table: JOIN sites ON devices.site_id = sites.id WHERE sites.organization_id = '{organization_id}'
    - For 'metrics' table: JOIN devices ON metrics.device_id = devices.id JOIN sites ON devices.site_id = sites.id WHERE sites.organization_id = '{organization_id}'
    - For 'alerts' table: JOIN devices ON alerts.device_id = devices.id JOIN sites ON devices.site_id = sites.id WHERE sites.organization_id = '{organization_id}'
    - For 'hotspot_sales' table: JOIN sites ON hotspot_sales.site_id = sites.id WHERE sites.organization_id = '{organization_id}'
    
    Other Rules:
    1. Generate a VALID, READ-ONLY PostgreSQL query.
    2. Use "metrics" table for performance data (TimescaleDB).
    3. Return ONLY the SQL query. No markdown.
    4. If the question cannot be answered with SQL, return "NO_SQL".
    
    User Question: {user_query}
    """

    try:
        if LLM_PROVIDER == "gemini":
            from google import genai
            client = genai.Client(api_key=LLM_API_KEY)
            resp = client.models.generate_content(
                model='gemini-2.5-flash-lite',
                contents=system_prompt
            )
            sql = resp.text.strip().replace("```sql", "").replace("```", "")
            return None, sql
            
        elif LLM_PROVIDER == "openai":
            client = openai.OpenAI(api_key=LLM_API_KEY)
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a SQL generator. Output only raw SQL."},
                    {"role": "user", "content": system_prompt}
                ]
            )
            sql = completion.choices[0].message.content.strip().replace("```sql", "").replace("```", "")
            return None, sql
            
    except Exception as e:
        logger.error(f"LLM Error: {e}")
        return f"LLM Error: {str(e)}", None

    return "Could not generate query.", None

# ... explain_result ...

@router.post("/chat", response_model=ChatResponse)
async def chat_with_network(
    request: ChatRequest, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Chat with your network data using AI.
    """
    user_query = request.query
    
    # 1. Generate SQL with Org Context
    error, sql = ask_llm_sql(user_query, str(current_user.organization_id))
    
    if error:
         return ChatResponse(response=f"System Error: {error}", sql_query=None)
    
    if not sql or sql == "NO_SQL":
         return ChatResponse(response="I couldn't understand how to query the database for that. Try asking about devices, alerts, or sales.", sql_query=None)
    
    # 2. Safety Check (Basic)
    if any(keyword in sql.upper() for keyword in ["DELETE", "DROP", "UPDATE", "INSERT", "TRUNCATE", "ALTER"]):
        return ChatResponse(response="I cannot execute destructive queries. Read-only access only.", sql_query=sql)

    # 3. Execute SQL (ASYNC FIX)
    try:
        from sqlalchemy import text
        result = await db.execute(text(sql))
        rows = result.fetchall()
        
        # Convert rows to list of dicts for simpler handling
        data = [str(row) for row in rows]
        
        # 4. Generate Natural Language Answer
        if len(data) > 10:
             summary = f"Found {len(data)} results. First 5: {data[:5]}"
        else:
             summary = f"Result: {data}"
             
        return ChatResponse(response=summary, sql_query=sql)
        
    except Exception as e:
        logger.error(f"SQL Execution Failed: {e}")
        return ChatResponse(response=f"The generated query failed to execute. Error: {str(e)}", sql_query=sql)
