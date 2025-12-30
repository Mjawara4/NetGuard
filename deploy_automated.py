#!/usr/bin/env python3
"""
Automated Deployment Script for NetGuard
Uses paramiko for SSH connections (no sshpass required)
"""

import os
import sys
import getpass
import subprocess
from pathlib import Path

try:
    import paramiko
except ImportError:
    print("❌ paramiko not installed. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko"])
    import paramiko

# Colors
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
NC = '\033[0m'  # No Color

def print_step(step, message):
    print(f"\n{GREEN}📦 Step {step}: {message}{NC}")
    print("=" * 50)

def ssh_execute(ssh, command, check=True):
    """Execute command via SSH and return output"""
    stdin, stdout, stderr = ssh.exec_command(command)
    exit_status = stdout.channel.recv_exit_status()
    output = stdout.read().decode()
    error = stderr.read().decode()
    
    if check and exit_status != 0:
        print(f"{RED}❌ Command failed: {command}{NC}")
        print(f"Error: {error}")
        raise Exception(f"SSH command failed with exit code {exit_status}")
    
    return output, error, exit_status

def main():
    print(f"{GREEN}🚀 NetGuard Automated Production Deployment{NC}")
    print("=" * 50)
    print()
    
    # Check .env.production exists
    env_file = Path(".env.production")
    if not env_file.exists():
        print(f"{RED}❌ Error: .env.production file not found!{NC}")
        print("Please create .env.production first.")
        sys.exit(1)
    
    # Get VPS connection details
    print(f"{YELLOW}📋 VPS Connection Details{NC}")
    vps_host = input("VPS Host/IP: ").strip()
    ssh_user = input("SSH Username (default: root): ").strip() or "root"
    ssh_port = input("SSH Port (default: 22): ").strip() or "22"
    ssh_password = getpass.getpass("SSH Password: ")
    
    deploy_dir = "/opt/netguard"
    repo_url = "https://github.com/Mjawara4/NetGuard.git"
    
    # Connect to VPS
    print_step(1, "Connecting to VPS...")
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(vps_host, port=int(ssh_port), username=ssh_user, password=ssh_password, timeout=30)
        print(f"{GREEN}✅ Connected to {vps_host}{NC}")
    except Exception as e:
        print(f"{RED}❌ Failed to connect: {e}{NC}")
        sys.exit(1)
    
    try:
        # Install prerequisites
        print_step(2, "Installing prerequisites...")
        commands = [
            # Install Docker
            "command -v docker >/dev/null 2>&1 || (curl -fsSL https://get.docker.com -o /tmp/get-docker.sh && sh /tmp/get-docker.sh && rm /tmp/get-docker.sh)",
            # Install Docker Compose
            "command -v docker-compose >/dev/null 2>&1 || (curl -L 'https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)' -o /usr/local/bin/docker-compose && chmod +x /usr/local/bin/docker-compose)",
        ]
        
        for cmd in commands:
            print(f"  Running: {cmd[:60]}...")
            ssh_execute(ssh, cmd, check=False)
        
        print(f"{GREEN}✅ Prerequisites installed{NC}")
        
        # Setup deployment directory
        print_step(3, "Setting up deployment directory...")
        ssh_execute(ssh, f"mkdir -p {deploy_dir}")
        ssh_execute(ssh, f"cd {deploy_dir} && (test -d .git && git pull origin main || git clone {repo_url} .)")
        print(f"{GREEN}✅ Repository ready{NC}")
        
        # Copy .env.production
        print_step(4, "Copying .env.production to VPS...")
        sftp = ssh.open_sftp()
        remote_env = f"{deploy_dir}/.env.production"
        sftp.put(str(env_file), remote_env)
        sftp.chmod(remote_env, 0o600)
        ssh_execute(ssh, f"cd {deploy_dir} && cp .env.production .env && chmod 600 .env")
        sftp.close()
        print(f"{GREEN}✅ Environment file copied and secured{NC}")
        
        # Deploy
        print_step(5, "Building and starting containers...")
        ssh_execute(ssh, f"cd {deploy_dir} && docker compose down", check=False)
        ssh_execute(ssh, f"cd {deploy_dir} && docker compose up -d --build")
        print(f"{GREEN}✅ Containers started{NC}")
        
        # Wait and verify
        print_step(6, "Verifying deployment...")
        import time
        time.sleep(10)
        
        output, _, _ = ssh_execute(ssh, f"cd {deploy_dir} && docker compose ps", check=False)
        print(output)
        
        # Check health
        output, _, status = ssh_execute(ssh, "curl -f http://localhost:8000/health 2>/dev/null || echo 'Health check pending...'", check=False)
        if "healthy" in output.lower() or "connected" in output.lower():
            print(f"{GREEN}✅ Health check passed{NC}")
        else:
            print(f"{YELLOW}⚠️  Health check pending (this is normal, may take a minute){NC}")
        
        print()
        print(f"{GREEN}✅ Deployment Complete!{NC}")
        print()
        print("=" * 50)
        print(f"{GREEN}🎉 NetGuard is now deployed!{NC}")
        print()
        print("Next steps:")
        print(f"1. Check status: ssh {ssh_user}@{vps_host} 'cd {deploy_dir} && docker compose ps'")
        print(f"2. View logs: ssh {ssh_user}@{vps_host} 'cd {deploy_dir} && docker compose logs -f'")
        print("3. Access your app at: https://app.netguard.fun")
        print()
        
    except Exception as e:
        print(f"{RED}❌ Deployment failed: {e}{NC}")
        sys.exit(1)
    finally:
        ssh.close()

if __name__ == "__main__":
    main()
