# Simple Deployment Guide

**Yes, you need Docker installed on your VPS.** We have made this easy.

## Step 1: Prepare your VPS
Log in to your VPS via SSH:
`ssh root@your-vps-ip`

Run these commands to install Docker (copy and paste them):
```bash
# Update and install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
```

## Step 2: Deploy the App
Since you chose **GitHub**, this is very easy. Run these commands on your VPS:

1. **Download the code**:
   ```bash
   git clone https://github.com/Mjawara4/NetGuard.git
   cd NetGuard
   ```

2. **Start the App**:
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

## Step 3: Final Configuration
The app is now running! But you need to set your domain and passwords.

1. **Edit the settings**:
   ```bash
   nano .env
   ```
   *Change `DOMAIN=...` to your actual subdomain (e.g., app.yourdomain.com)*

2. **Apply changes**:
   ```bash
   ./deploy.sh
   ```

**Done!** Your app should be live at your domain.

## Troubleshooting
**"User sessions running outdated binaries" Screen:**
If you see a pink/purple screen listing services like `apt` or `systemd`:
1. Press `Tab` to highlight `<Ok>`.
2. Press `Enter`.
3. Then type `reboot` to restart the server and ensure all updates are applied.
