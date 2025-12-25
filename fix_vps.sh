#!/bin/bash
echo "🔧 Connecting to VPS to repair deployment..."
ssh root@74.208.167.166 "
  set -e
  
  if [ ! -d ~/NetGuard ]; then
    echo '📂 NetGuard not found. Cloning...'
    git clone https://github.com/Mjawara4/NetGuard.git ~/NetGuard
  fi

  echo '📂 Entering directory...'
  cd ~/NetGuard

  echo '🔄 Force-Resetting Codebase...'
  git fetch --all
  git reset --hard origin/main
  
  echo '🧹 Resetting Database (Fresh Start)...'
  # Check if docker is available first, if not we might need to install it.
  # Assuming docker is installed or deploy.sh handles it? 
  # Actually deploy.sh assumes docker compose exists.
  # Let's verify if docker is installed.
  
  if ! command -v docker &> /dev/null; then
    echo '🐳 Docker not found. Installing...'
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
  fi

  # Only run down if compose file exists and docker is running
  if [ -f docker-compose.yml ]; then
    docker compose down || true
  fi
  
  echo '🚀 Deploying...'
  # Make sure deploy.sh is executable
  chmod +x deploy.sh
  ./deploy.sh
  
  echo '✅ Deployment Repaired! Go to https://app.netguard.fun'
"
