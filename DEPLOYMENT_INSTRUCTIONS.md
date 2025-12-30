# Production Deployment Instructions

## Option 1: Automated Deployment (Recommended)

I've created a deployment script that will handle everything automatically.

### Prerequisites
- `sshpass` installed (for password-based SSH)
  ```bash
  # macOS
  brew install hudochenkov/sshpass/sshpass
  
  # Linux (Ubuntu/Debian)
  sudo apt-get install sshpass
  
  # Linux (CentOS/RHEL)
  sudo yum install sshpass
  ```

### Run Deployment
```bash
./deploy_to_production.sh
```

The script will ask for:
- VPS Host/IP
- SSH Username (default: root)
- SSH Port (default: 22)
- SSH Password

## Option 2: Manual Deployment Steps

If you prefer to deploy manually or the automated script doesn't work:

### Step 1: Connect to VPS
```bash
ssh root@your-vps-ip
# Enter password when prompted
```

### Step 2: Install Docker (if not installed)
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
```

### Step 3: Install Docker Compose (if not installed)
```bash
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

### Step 4: Clone/Update Repository
```bash
mkdir -p /opt/netguard
cd /opt/netguard

# If first time
git clone https://github.com/Mjawara4/NetGuard.git .

# If updating
git pull origin main
```

### Step 5: Copy .env.production to VPS

**From your local machine:**
```bash
scp .env.production root@your-vps-ip:/opt/netguard/.env.production
```

**On VPS:**
```bash
cd /opt/netguard
cp .env.production .env
chmod 600 .env
```

### Step 6: Deploy
```bash
cd /opt/netguard
docker compose down
docker compose up -d --build
```

### Step 7: Verify
```bash
# Check containers
docker compose ps

# Check health
curl http://localhost:8000/health

# View logs
docker compose logs -f
```

## VPS Details Needed

Please provide:
1. **VPS Host/IP**: (e.g., `74.208.167.166`)
2. **SSH Username**: (e.g., `root` or `ubuntu`)
3. **SSH Password**: (you'll provide this securely)
4. **SSH Port**: (default: `22`)

## Post-Deployment

After deployment, verify:
- ✅ All containers running: `docker compose ps`
- ✅ Health endpoint: `curl http://localhost:8000/health`
- ✅ Frontend accessible: `https://app.netguard.fun`
- ✅ SSL certificate issued (check Caddy logs)

## Troubleshooting

### If containers fail to start:
```bash
docker compose logs backend
docker compose logs db
docker compose logs frontend
```

### If database connection fails:
- Check `.env` file has correct `POSTGRES_PASSWORD`
- Verify database container is healthy: `docker compose ps db`

### If WireGuard fails:
- Check WireGuard container logs: `docker compose logs wireguard`
- Verify server public key is set in `.env`

## Ready to Deploy?

Please provide your VPS connection details and I'll help you deploy!
