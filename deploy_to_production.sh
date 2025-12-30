#!/bin/bash

# Production Deployment Script for NetGuard
# This script deploys NetGuard to your VPS

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 NetGuard Production Deployment${NC}"
echo "=================================="
echo ""

# Check if .env.production exists
if [ ! -f .env.production ]; then
    echo -e "${RED}❌ Error: .env.production file not found!${NC}"
    echo "Please create .env.production first."
    exit 1
fi

# Get VPS connection details
echo -e "${YELLOW}📋 VPS Connection Details${NC}"
read -p "VPS Host/IP: " VPS_HOST
read -p "SSH Username (default: root): " SSH_USER
SSH_USER=${SSH_USER:-root}
read -p "SSH Port (default: 22): " SSH_PORT
SSH_PORT=${SSH_PORT:-22}
read -sp "SSH Password: " SSH_PASSWORD
echo ""

# Deployment directory on VPS
DEPLOY_DIR="/opt/netguard"
REPO_URL="https://github.com/Mjawara4/NetGuard.git"

echo ""
echo -e "${GREEN}📦 Step 1: Testing SSH Connection...${NC}"
sshpass -p "$SSH_PASSWORD" ssh -o StrictHostKeyChecking=no -p "$SSH_PORT" "$SSH_USER@$VPS_HOST" "echo 'SSH connection successful!'" || {
    echo -e "${RED}❌ SSH connection failed!${NC}"
    echo "Please check your credentials and try again."
    exit 1
}

echo -e "${GREEN}✅ SSH connection successful!${NC}"
echo ""

echo -e "${GREEN}📦 Step 2: Installing prerequisites on VPS...${NC}"
sshpass -p "$SSH_PASSWORD" ssh -p "$SSH_PORT" "$SSH_USER@$VPS_HOST" << 'ENDSSH'
    # Install Docker if not present
    if ! command -v docker &> /dev/null; then
        echo "Installing Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        rm get-docker.sh
    fi
    
    # Install Docker Compose if not present
    if ! command -v docker-compose &> /dev/null; then
        echo "Installing Docker Compose..."
        curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
    fi
    
    # Install sshpass if not present (for password-based SSH)
    if ! command -v sshpass &> /dev/null; then
        if command -v apt-get &> /dev/null; then
            apt-get update && apt-get install -y sshpass
        elif command -v yum &> /dev/null; then
            yum install -y sshpass
        fi
    fi
    
    echo "✅ Prerequisites installed"
ENDSSH

echo -e "${GREEN}✅ Prerequisites check complete!${NC}"
echo ""

echo -e "${GREEN}📦 Step 3: Setting up deployment directory...${NC}"
sshpass -p "$SSH_PASSWORD" ssh -p "$SSH_PORT" "$SSH_USER@$VPS_HOST" << ENDSSH
    mkdir -p $DEPLOY_DIR
    cd $DEPLOY_DIR
    
    # Clone or update repository
    if [ -d ".git" ]; then
        echo "Updating existing repository..."
        git pull origin main || git pull origin master
    else
        echo "Cloning repository..."
        git clone $REPO_URL .
    fi
    
    echo "✅ Repository ready"
ENDSSH

echo -e "${GREEN}✅ Deployment directory ready!${NC}"
echo ""

echo -e "${GREEN}📦 Step 4: Copying .env.production to VPS...${NC}"
sshpass -p "$SSH_PASSWORD" scp -P "$SSH_PORT" .env.production "$SSH_USER@$VPS_HOST:$DEPLOY_DIR/.env.production"
sshpass -p "$SSH_PASSWORD" ssh -p "$SSH_PORT" "$SSH_USER@$VPS_HOST" "cd $DEPLOY_DIR && cp .env.production .env && chmod 600 .env"
echo -e "${GREEN}✅ Environment file copied and secured!${NC}"
echo ""

echo -e "${GREEN}📦 Step 5: Building and starting containers...${NC}"
sshpass -p "$SSH_PASSWORD" ssh -p "$SSH_PORT" "$SSH_USER@$VPS_HOST" << ENDSSH
    cd $DEPLOY_DIR
    
    # Stop existing containers
    docker compose down || true
    
    # Build and start
    docker compose up -d --build
    
    # Wait for services to be healthy
    echo "Waiting for services to start..."
    sleep 10
    
    # Check container status
    docker compose ps
ENDSSH

echo ""
echo -e "${GREEN}📦 Step 6: Verifying deployment...${NC}"
sshpass -p "$SSH_PASSWORD" ssh -p "$SSH_PORT" "$SSH_USER@$VPS_HOST" << 'ENDSSH'
    cd /opt/netguard
    
    # Check if containers are running
    if docker compose ps | grep -q "Up"; then
        echo "✅ Containers are running"
    else
        echo "⚠️  Some containers may not be running. Check with: docker compose ps"
    fi
    
    # Check health endpoint
    sleep 5
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ Health check passed"
    else
        echo "⚠️  Health check failed. Check logs with: docker compose logs backend"
    fi
ENDSSH

echo ""
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo ""
echo "=================================="
echo -e "${GREEN}🎉 NetGuard is now deployed!${NC}"
echo ""
echo "Next steps:"
echo "1. Check service status: ssh $SSH_USER@$VPS_HOST 'cd $DEPLOY_DIR && docker compose ps'"
echo "2. View logs: ssh $SSH_USER@$VPS_HOST 'cd $DEPLOY_DIR && docker compose logs -f'"
echo "3. Access your app at: https://app.netguard.fun"
echo ""
echo "Useful commands:"
echo "  - View all logs: docker compose logs -f"
echo "  - Restart services: docker compose restart"
echo "  - Stop services: docker compose down"
echo "  - Update and redeploy: git pull && docker compose up -d --build"
echo ""
