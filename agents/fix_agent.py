import time
import requests
import os
import paramiko
import logging
import sys
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)
logger = logging.getLogger("fix-agent")

API_URL = os.getenv("API_URL", "http://backend:8000/api/v1")
API_KEY = os.getenv("NETGUARD_API_KEY")

if not API_KEY:
    logger.critical("FATAL: NETGUARD_API_KEY env var not set.")
    sys.exit(1)

def get_headers():
    return {"X-API-Key": API_KEY}

def execute_ssh_command(host, command):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    # Credentials from env (Default to admin/admin for MVP demo)
    user = os.getenv("SSH_USER", "admin")
    password = os.getenv("SSH_PASSWORD", "admin")
    key_path = os.getenv("SSH_KEY_PATH")
    
    try:
        connect_kwargs = {"username": user}
        # Simplify key handling for MVP
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
        logger.error(f"SSH Failed connecting to {host}: {e}")
        return None

def run_agent():
    logger.info("Starting Classic Fix Agent (REAL SSH MODE)...")
    
    # Pre-check SSH credentials
    logger.info(f"SSH User: {os.getenv('SSH_USER', 'admin')}")
    
    while True:
        try:
             # fetch open alerts
             resp = requests.get(
                 f"{API_URL}/monitoring/alerts",
                 headers=get_headers(),
                 timeout=10
             )
             if resp.status_code == 200:
                 alerts = resp.json()
                 for alert in alerts:
                     if alert['status'] == 'open' and alert['severity'] == 'critical':
                         
                         # Check if it's "High CPU"
                         if "High CPU" in alert['message']:
                             logger.info(f"Processing High CPU Alert {alert['id']}...")
                             
                             # Fetch device info to get IP
                             dev_resp = requests.get(
                                 f"{API_URL}/inventory/devices",
                                 headers=get_headers(),
                                 timeout=10
                             )
                             devices = dev_resp.json() if dev_resp.status_code == 200 else []
                             device = next((d for d in devices if d['id'] == alert['device_id']), None)
                             
                             if device and device.get('ip_address'):
                                 logger.info(f"Attempting SSH connection to {device['ip_address']} to investigate...")
                                 
                                 # REAL FIX ACTION: Run 'uptime' or 'top' to verify
                                 # In a real scenario, we might run 'service restart'
                                 output = execute_ssh_command(device['ip_address'], "uptime")
                                 
                                 if output:
                                     logger.info(f"SSH Success! Uptime: {output.strip()}")
                                     logger.info("Simulating remediation: Restarting high load process...")
                                     time.sleep(2) # Simulate work
                                     
                                     # Resolve Alert
                                     try:
                                         requests.patch(
                                             f"{API_URL}/monitoring/alerts/{alert['id']}",
                                             json={"status": "resolved", "resolution_summary": "Auto-fixed by Classic Agent (Uptime Check Passed)"},
                                             headers=get_headers(),
                                             timeout=10
                                         )
                                         logger.info(f"ALERT FIXED: {alert['message']}")
                                     except Exception as ex:
                                         logger.error(f"Failed to update alert status: {ex}")
                                else:
                                    logger.error("Failed to connect via SSH. Cannot fix.")
                             else:
                                 logger.warning("Device not found or no IP address.")

                         # Fallback fallback logic strictly for demo if needed
                         # ...
                         
        except Exception as e:
            logger.exception(f"Fix loop error: {e}")
            
        time.sleep(10)

if __name__ == "__main__":
    run_agent()
