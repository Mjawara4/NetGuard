# Production Deployment Guide

## Prerequisites

- ✅ `.env.production` file created and configured
- ✅ All secrets generated and updated
- ✅ VPS access (SSH credentials)

## Deployment Steps

### Step 1: Prepare Deployment Package

The deployment will:
1. Copy `.env.production` to the VPS
2. Ensure Docker and Docker Compose are installed
3. Clone/update the repository
4. Deploy all services

### Step 2: VPS Connection Details Needed

Please provide:
- **VPS Host/IP**: (e.g., `74.208.167.166` or `app.netguard.fun`)
- **SSH User**: (e.g., `root` or `ubuntu`)
- **SSH Password**: (you'll provide this)
- **SSH Port**: (default: `22`)

### Step 3: Deployment Process

The deployment script will:
1. ✅ Connect to VPS via SSH
2. ✅ Install Docker (if not installed)
3. ✅ Install Docker Compose (if not installed)
4. ✅ Create deployment directory
5. ✅ Copy `.env.production` to VPS as `.env`
6. ✅ Clone/update repository
7. ✅ Build and start all containers
8. ✅ Verify services are running
9. ✅ Check health endpoints

## What Will Be Deployed

- **Backend API**: FastAPI application
- **Frontend**: React application
- **Database**: PostgreSQL + TimescaleDB
- **Redis**: Cache/Queue
- **Agents**: Monitor, Diagnoser, Fix, AI Fix
- **WireGuard**: VPN server
- **Caddy**: Reverse proxy with SSL

## Post-Deployment Verification

After deployment, verify:
- ✅ All containers running: `docker compose ps`
- ✅ Health check: `curl http://localhost:8000/health`
- ✅ Database connectivity
- ✅ Frontend accessible at domain
- ✅ SSL certificate issued by Caddy

## Ready to Deploy

Please provide your VPS connection details to proceed with deployment.
