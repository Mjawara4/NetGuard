#!/bin/bash

# Quick Deployment Helper
# This script provides commands you can copy-paste to deploy

echo "🚀 NetGuard Quick Deployment Helper"
echo "===================================="
echo ""
echo "Please provide your VPS details:"
read -p "VPS Host/IP: " VPS_HOST
read -p "SSH Username (default: root): " SSH_USER
SSH_USER=${SSH_USER:-root}
read -p "SSH Port (default: 22): " SSH_PORT
SSH_PORT=${SSH_PORT:-22}
echo ""

echo "📋 Deployment Commands"
echo "======================"
echo ""
echo "1. Copy .env.production to VPS:"
echo "   scp -P $SSH_PORT .env.production $SSH_USER@$VPS_HOST:/tmp/.env.production"
echo ""
echo "2. Connect to VPS and run these commands:"
echo "   ssh -p $SSH_PORT $SSH_USER@$VPS_HOST"
echo ""
echo "   Then on the VPS, run:"
echo "   mkdir -p /opt/netguard"
echo "   cd /opt/netguard"
echo "   git clone https://github.com/Mjawara4/NetGuard.git . || git pull"
echo "   cp /tmp/.env.production .env"
echo "   chmod 600 .env"
echo "   docker compose down"
echo "   docker compose up -d --build"
echo ""
echo "3. Verify deployment:"
echo "   docker compose ps"
echo "   curl http://localhost:8000/health"
echo ""
