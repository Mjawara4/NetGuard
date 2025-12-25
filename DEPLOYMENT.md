# Deploying NetGuard

NetGuard is a containerized application designed to be deployed using Docker. This guide covers deploying to a generic Linux server (Ubuntu/Debian recommended).

## Prerequisites
- A Linux server (VPS or dedicated)
- **Docker** and **Docker Compose** installed
- A domain name (optional but recommended)

## 1. Quick Start (Automated Script)

### Option A: You have the code on GitHub/GitLab
1. **Clone the code**:
   ```bash
   git clone <repo_url> netguard
   cd netguard
   ```
2. **Run Deploy**: `./deploy.sh`

### Option B: Upload from Local Machine (No Git)
If your code is only on your computer, use `scp` to copy it to your VPS.

1. **Run this command on your LOCAL machine**:
   *(Replace `your-vps-ip` with your actual IP)*
   ```bash
   # Copy all files to the server
   scp -r . root@your-vps-ip:~/netguard
   ```

2. **Connect to your VPS**:
   ```bash
   ssh root@your-vps-ip
   cd netguard
   ```

3. **Run the Deploy Script**:
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

3. **Configure Secrets**:
   After the first run, edit `.env` to set your real passwords and domains.
   ```bash
   nano .env
   ./deploy.sh # Restart to apply changes
   ```

## 2. Manual Docker Compose
If you prefer manual control:

1. **Clone or Copy the Code** to your server:
   ```bash
   git clone <your-repo-url> netguard
   cd netguard
   ```

2. **Configure Environment Variables**:
   Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and set strict production values:
   - `POSTGRES_PASSWORD`: Set a strong database password.
   - `SECRET_KEY`: Generate a random string (e.g., `openssl rand -hex 32`).
   - `DOMAIN`: Set your actual domain name.

3. **Start the Application**:
   ```bash
   docker-compose up -d --build
   ```

## 2. Ports & Firewall
Ensure the following ports are open on your server's firewall (e.g., `ufw`):
- **80/443**: Web access (Frontend)
- **8000**: Backend API (if not reverse proxied)

## 3. Production Hardening (Recommended)
Running on public ports 80/443 directly is possible but using a Reverse Proxy like **Caddy** or **Nginx** is recommended for SSL (https://).

### Option A: Caddy (Easiest - Automatic HTTPS)
Install Caddy on your VPS, then point your subdomain `app.yourdomain.com` to the server IP.

**Caddyfile:**
```
netguard.yourdomain.com {
    reverse_proxy localhost:80
}

api.netguard.yourdomain.com {
    reverse_proxy localhost:8000
}
```

### Option B: Nginx
If using Nginx, create a server block:
```nginx
server {
    server_name app.yourdomain.com;
    location / {
        proxy_pass http://localhost:80;
    }
}
```

## 4. Updates
To update the application to the latest version:
```bash
git pull                   # Get latest code
docker-compose up -d --build # Rebuild containers
docker image prune -f      # Clean up old images
```

## 5. Security Checklist for VPS
1. **Firewall**: Enable UFW.
   `ufw allow 80; ufw allow 443; ufw allow ssh; ufw enable`
2. **Database Password**: Ensure `POSTGRES_PASSWORD` in `.env` is complex.
3. **CORS**: In `backend/app/main.py`, update `allow_origins=["*"]` to your specific domains if strict security is required.
