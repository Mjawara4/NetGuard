#!/bin/bash
echo "🔧 Connecting to VPS to repair deployment..."
ssh root@74.208.192.189 "
  set -e
  echo '📂 Entering directory...'
  cd ~/NetGuard

  echo '🔄 Force-Resetting Codebase...'
  git fetch --all
  git reset --hard origin/main
  
  echo '🧹 Resetting Database (Fresh Start)...'
  docker compose down
  
  echo '🚀 Deploying...'
  ./deploy.sh
  
  echo '✅ Deployment Repaired! Go to https://app.netguard.fun'
"
