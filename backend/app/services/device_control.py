
import paramiko
import os
import logging

logger = logging.getLogger(__name__)

def execute_ssh_command(host, command, user="admin", password="admin", key_path=None):
    """
    Executes a command via SSH on a remote host.
    """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    # In a real app, these should come from the Device record in DB!
    # For MVP, we use the env vars or defaults, assuming consistent credentials.
    # We should look up credentials from DB if stored there, but for now we follow the agent pattern.
    
    if not user:
        user = os.getenv("SSH_USER", "admin")
    if not password:
        password = os.getenv("SSH_PASSWORD", "admin")
    if not key_path:
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
            return f"Output: {output}\nError: {error}"
            
        return output
    except Exception as e:
        logger.error(f"SSH Failed: {e}")
        return f"Error executing command: {str(e)}"
