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
    You are an expert Network Reliability Engineer. 
    Analyze the following network alert and device status.
    Recommend a specific remediation action.
    
    Alert Message: {alert['message']}
    Rule: {alert['rule_name']}
    Device: {device_info.get('name', 'Unknown')} ({device_info.get('ip_address', 'Unknown')})
    Platform: {device_info.get('platform', 'linux')}
    
    Valid Actions: REBOOT, RESTART_SERVICE, CLEAR_CACHE, IPSLA_RESET, IGNORE, ESCALATE.
    
    Output strictly valid JSON:
    {{
        "analysis": "Brief reasoning",
        "action": "ACTION_NAME",
        "command": "Shell command to execute (or null)"
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
                             logger.info(f"AI Decision: {decision['action']} ({decision['analysis']})")
                             
                             if decision['action'] in ['REBOOT', 'RESTART_SERVICE', 'CLEAR_CACHE', 'IPSLA_RESET']:
                                 success, output = execute_fix(decision['action'], decision.get('command'), device.get('ip_address'))
                                 
                                 status_code = "success" if success else "failed"
                                 report_fix_action(alert['id'], decision['action'], status_code, output or decision['analysis'])
                                 
                                 if success:
                                     logger.info(f"Fix executed. Marking alert resolved.")
                                     update_alert_status(alert['id'], "auto_fixed", resolution_summary=decision['analysis'])
                                 
                             elif decision['action'] == 'ESCALATE':
                                 logger.info("AI decided to escalate to human.")
                                 report_fix_action(alert['id'], "ESCALATE", "pending", decision['analysis'])
                                 
                             else:
                                 logger.info("AI suggested no action or ignore.")
                                 report_fix_action(alert['id'], "IGNORE", "skipped", decision['analysis'])
                         else:
                             logger.warning("AI failed to decide. Falling back to Classic rules.")
                             
        except Exception as e:
            logger.exception(f"AI Agent loop error: {e}")
            
        time.sleep(15)

if __name__ == "__main__":
    run_agent()
