import os
import time
import json
import requests
import logging
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)
logger = logging.getLogger("ai-fix-agent")

# Configuration
API_URL = os.getenv("API_URL", "http://backend:8000/api/v1")
API_KEY = os.getenv("NETGUARD_API_KEY")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower() # openai, gemini, anthropic

# Determine LLM Key based on provider
LLM_API_KEY = os.getenv("LLM_API_KEY")
if not LLM_API_KEY:
    if LLM_PROVIDER == "openai":
        LLM_API_KEY = os.getenv("OPENAI_API_KEY")
    elif LLM_PROVIDER == "gemini":
        LLM_API_KEY = os.getenv("GEMINI_API_KEY")

if not LLM_API_KEY:
    logger.warning("LLM Key not found. AI Agent will function in fallback-only mode.")

def get_headers():
    return {"X-API-Key": API_KEY}

import google.generativeai as genai
import openai

def ask_llm(alert, device_info):
    """
    Constructs a prompt and queries the LLM for a remediation strategy.
    Returns a dict with 'action', 'reasoning', 'command'.
    """
    if not LLM_API_KEY:
        logger.warning("No LLM API Key provided.")
        return None

    system_prompt = f"""
    You are an expert Network Reliability Engineer acting as an autonomous agent. 
    Analyze the following network alert and device status to determine the best remediation strategy.
    
    CONTEXT:
    Alert Message: {alert['message']}
    Rule Violated: {alert['rule_name']}
    Device Name: {device_info.get('name', 'Unknown')}
    Device IP: {device_info.get('ip_address', 'Unknown')}
    Platform: {device_info.get('platform', 'linux')}
    
    AVAILABLE ACTIONS:
    1. REBOOT: Restart the device. Use only if critical and unresponsive.
    2. RESTART_SERVICE: Restart a specific service (e.g., nginx, docker). 
    3. CLEAR_CACHE: Clear temporary files or caches if disk is full.
    4. IPSLA_RESET: Reset IP SLA statistics.
    5. IGNORE: False positive or transient issue.
    6. ESCALATE: Issue is complex, unknown, or risky. Requires human intervention.
    
    SAFETY GUIDELINES:
    - PREFER 'RESTART_SERVICE' over 'REBOOT'.
    - If the issue is unclear, choose 'ESCALATE'.
    - If the device is critical (e.g., Core Router), be extremely conservative.
    - Provide a specific shell command for the action if applicable.
    
    RESPONSE FORMAT:
    Output strictly valid JSON:
    {{
        "analysis": "Concise reasoning for your decision (max 1 sentence)",
        "action": "ACTION_NAME",
        "command": "Specific shell command to execute (e.g., 'systemctl restart nginx') or null if not applicable or action is ESCALATE/IGNORE",
        "confidence": "Low/Medium/High"
    }}
    """

    try:
        logger.info(f"Querying {LLM_PROVIDER} for alert {alert['id']}...")
        
        response_text = ""
        
        if LLM_PROVIDER == "gemini":
            genai.configure(api_key=LLM_API_KEY)
            model = genai.GenerativeModel('gemini-pro')
            resp = model.generate_content(system_prompt + "\nResponse (JSON):")
            response_text = resp.text
            
        elif LLM_PROVIDER == "openai":
            client = openai.OpenAI(api_key=LLM_API_KEY)
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a network automation assistant. Output JSON only."},
                    {"role": "user", "content": system_prompt}
                ],
                response_format={"type": "json_object"}
            )
            response_text = completion.choices[0].message.content
            
        else:
            logger.error(f"Unknown provider: {LLM_PROVIDER}")
            return None

        # Parse JSON
        decision = json.loads(response_text)
        return decision

    except Exception as e:
        logger.error(f"LLM Query failed: {e}")
        return None

import paramiko

def execute_ssh_command(host, command):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    # Credentials from env
    user = os.getenv("SSH_USER", "admin")
    password = os.getenv("SSH_PASSWORD", "admin")
    key_path = os.getenv("SSH_KEY_PATH")
    
    try:
        connect_kwargs = {"username": user}
        if key_path and os.path.exists(key_path):
            connect_kwargs["key_filename"] = key_path
        else:
            connect_kwargs["password"] = password
            
        logger.info(f"Connecting to {host} as {user}...")
        ssh.connect(host, **connect_kwargs, timeout=10)
        
        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode()
        error = stderr.read().decode()
        ssh.close()
        
        if error:
            logger.warning(f"SSH Stderr: {error}")
            
        return output
    except Exception as e:
        logger.error(f"SSH Failed: {e}")
        return None

def execute_fix(action, command, device_ip):
    logger.info(f"Executing AI Auto-Fix: {action} on {device_ip}")
    output = None
    
    if action == "IGNORE":
        return True, "Ignored by AI"
        
    if command and device_ip:
        logger.info(f"Running via SSH: {command}")
        output = execute_ssh_command(device_ip, command)
        if output is not None:
             logger.info(f"Command Output: {output}")
             return True, output
        else:
             return False, "SSH Command Failed"
             
    # fallback simulated success for non-ssh actions if any
    time.sleep(2)
    return True, "Simulated Action Success"

def report_fix_action(alert_id, action, status, output):
    """
    Report the action taken to the backend.
    """
    try:
        payload = {
            "action_type": action,
            "status": status,
            "log_output": output
        }
        resp = requests.post(
            f"{API_URL}/monitoring/alerts/{alert_id}/fix-actions",
            json=payload,
            headers=get_headers(),
            timeout=10
        )
        if resp.status_code == 200:
            logger.info(f"Action reported for alert {alert_id}")
        else:
            logger.error(f"Failed to report action: {resp.text}")
    except Exception as e:
        logger.error(f"Error reporting fix action: {e}")

def update_alert_status(alert_id, status, resolution_summary=None):
    """
    Update the alert status in the backend.
    """
    try:
        payload = {
            "status": status,
            "resolution_summary": resolution_summary
        }
        resp = requests.patch(
            f"{API_URL}/monitoring/alerts/{alert_id}",
            json=payload,
            headers=get_headers(),
            timeout=10
        )
        if resp.status_code == 200:
            logger.info(f"Alert {alert_id} marked as {status}")
        else:
            logger.error(f"Failed to update alert status: {resp.text}")
    except Exception as e:
        logger.error(f"Error updating alert status: {e}")

def run_agent():
    logger.info("Starting AI Fix Agent...")
    
    while True:
        try:
             resp = requests.get(
                 f"{API_URL}/monitoring/alerts",
                 headers=get_headers(),
                 timeout=10
             )
             if resp.status_code == 200:
                 alerts = resp.json()
                 for alert in alerts:
                     if alert['status'] == 'open' and alert['severity'] == 'critical':
                         logger.info(f"Processing critical alert {alert['id']}")
                         
                         # Fetch detailed device info
                         dev_resp = requests.get(
                             f"{API_URL}/inventory/devices",
                             headers=get_headers(),
                             timeout=10
                         )
                         devices = dev_resp.json() if dev_resp.status_code == 200 else []
                         device = next((d for d in devices if d['id'] == alert['device_id']), {})
                         
                         # Ask AI
                         decision = ask_llm(alert, device)
                         
                         if decision:
                             logger.info(f"AI Decision: {decision['action']} (Confidence: {decision.get('confidence', 'Unknown')})")
                             logger.info(f"Reasoning: {decision.get('analysis')}")

                             action = decision['action']
                             confidence = decision.get('confidence', 'Low').upper()
                             command = decision.get('command')

                             # SAFETY CHECKS
                             is_safe = True
                             if confidence == "LOW":
                                 logger.warning("Confidence is LOW. Escalating instead of executing.")
                                 is_safe = False
                             elif action == "REBOOT" and confidence != "HIGH":
                                 logger.warning("Reboot requested but confidence is not HIGH. Escalating.")
                                 is_safe = False
                             
                             if is_safe and action in ['REBOOT', 'RESTART_SERVICE', 'CLEAR_CACHE', 'IPSLA_RESET']:
                                 success, output = execute_fix(action, command, device.get('ip_address'))
                                 
                                 status_code = "success" if success else "failed"
                                 report_fix_action(alert['id'], action, status_code, output or decision['analysis'])
                                 
                                 if success:
                                     logger.info(f"Fix executed. Marking alert resolved.")
                                     update_alert_status(alert['id'], "auto_fixed", resolution_summary=decision['analysis'])
                                 
                             elif not is_safe or action == 'ESCALATE':
                                 logger.info("Escalating to human.")
                                 report_fix_action(alert['id'], "ESCALATE", "pending", decision['analysis'])
                                 
                             else:
                                 logger.info("AI suggested IGNORE or no action.")
                                 report_fix_action(alert['id'], "IGNORE", "skipped", decision['analysis'])
                         else:
                             logger.warning("AI failed to decide. Falling back to Classic rules.")
                             
        except Exception as e:
            logger.exception(f"AI Agent loop error: {e}")
            
        time.sleep(15)

if __name__ == "__main__":
    run_agent()
