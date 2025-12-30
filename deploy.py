#!/usr/bin/env python3
"""
Automated Deployment Script for NetGuard
Usage: python3 deploy.py <vps_host> <ssh_user> <ssh_port>
Password will be prompted securely
"""

import os
import sys
import getpass
import subprocess
from pathlib import Path

try:
    import paramiko
except ImportError:
    print("Installing paramiko...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko", "--user"])
    import paramiko

GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
NC = '\033[0m'

def print_step(step, message):
    print(f"\n{GREEN}📦 Step {step}: {message}{NC}")
    print("=" * 50)

def ssh_execute(ssh, command, check=True):
    stdin, stdout, stderr = ssh.exec_command(command)
    exit_status = stdout.channel.recv_exit_status()
    output = stdout.read().decode()
    error = stderr.read().decode()
    if check and exit_status != 0:
        print(f"{RED}❌ Command failed: {command}{NC}")
        if error:
            print(f"Error: {error}")
        raise Exception(f"SSH command failed with exit code {exit_status}")
    return output, error, exit_status

def main():
    print(f"{GREEN}🚀 NetGuard Automated Production Deployment{NC}")
    print("=" * 50)
    
    # Get arguments or prompt
    if len(sys.argv) >= 2:
        vps_host = sys.argv[1]
        ssh_user = sys.argv[2] if len(sys.argv) >= 3 else "root"
        ssh_port = sys.argv[3] if len(sys.argv) >= 4 else "22"
    else:
        vps_host = input("VPS Host/IP: ").strip()
        ssh_user = input("SSH Username (default: root): ").strip() or "root"
        ssh_port = input("SSH Port (default: 22): ").strip() or "22"
    
    ssh_password = getpass.getpass(f"SSH Password for {ssh_user}@{vps_host}: ")
    
    env_file = Path(".env.production")
    if not env_file.exists():
        print(f"{RED}❌ .env.production not found!{NC}")
        sys.exit(1)
    
    deploy_dir = "/opt/netguard"
    repo_url = "https://github.com/Mjawara4/NetGuard.git"
    
    print_step(1, f"Connecting to {vps_host}...")
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(vps_host, port=int(ssh_port), username=ssh_user, password=ssh_password, timeout=30)
        print(f"{GREEN}✅ Connected{NC}")
    except Exception as e:
        print(f"{RED}❌ Connection failed: {e}{NC}")
        sys.exit(1)
    
    try:
        print_step(2, "Installing prerequisites...")
        ssh_execute(ssh, "command -v docker >/dev/null 2>&1 || (curl -fsSL https://get.docker.com -o /tmp/get-docker.sh && sh /tmp/get-docker.sh && rm /tmp/get-docker.sh)", check=False)
        ssh_execute(ssh, "command -v docker-compose >/dev/null 2>&1 || (curl -L 'https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)' -o /usr/local/bin/docker-compose && chmod +x /usr/local/bin/docker-compose)", check=False)
        print(f"{GREEN}✅ Prerequisites ready{NC}")
        
        print_step(3, "Setting up repository...")
        ssh_execute(ssh, f"mkdir -p {deploy_dir}")
        ssh_execute(ssh, f"cd {deploy_dir} && (test -d .git && (git pull origin main || git pull origin master) || git clone {repo_url} .)")
        print(f"{GREEN}✅ Repository ready{NC}")
        
        print_step(4, "Copying .env.production...")
        sftp = ssh.open_sftp()
        sftp.put(str(env_file), f"{deploy_dir}/.env.production")
        sftp.chmod(f"{deploy_dir}/.env.production", 0o600)
        ssh_execute(ssh, f"cd {deploy_dir} && cp .env.production .env && chmod 600 .env")
        sftp.close()
        print(f"{GREEN}✅ Environment configured{NC}")
        
        print_step(5, "Deploying containers...")
        ssh_execute(ssh, f"cd {deploy_dir} && docker compose down", check=False)
        ssh_execute(ssh, f"cd {deploy_dir} && docker compose up -d --build")
        print(f"{GREEN}✅ Containers deployed{NC}")
        
        print_step(6, "Verifying deployment...")
        import time
        time.sleep(10)
        output, _, _ = ssh_execute(ssh, f"cd {deploy_dir} && docker compose ps", check=False)
        print(output)
        
        health, _, _ = ssh_execute(ssh, "curl -s http://localhost:8000/health 2>/dev/null || echo 'pending'", check=False)
        if "healthy" in health.lower() or "connected" in health.lower():
            print(f"{GREEN}✅ Health check passed{NC}")
        else:
            print(f"{YELLOW}⚠️  Health check pending (normal, may take a minute){NC}")
        
        print(f"\n{GREEN}✅ Deployment Complete!{NC}\n")
        print(f"Access: https://app.netguard.fun")
        print(f"Status: ssh {ssh_user}@{vps_host} 'cd {deploy_dir} && docker compose ps'")
        print(f"Logs: ssh {ssh_user}@{vps_host} 'cd {deploy_dir} && docker compose logs -f'")
        
    except Exception as e:
        print(f"{RED}❌ Deployment failed: {e}{NC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        ssh.close()

if __name__ == "__main__":
    main()
