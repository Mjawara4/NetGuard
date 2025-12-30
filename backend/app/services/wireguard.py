import subprocess
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Device
from app.config import settings

WG_CONF_PATH = "/etc/wireguard/wg_confs/wg0.conf"
WG_SUBNET = "10.13.13."

# We will read the key dynamically.

class WireGuardService:
    @staticmethod
    def get_server_public_key():
        """
        Reads the server public key from the shared volume or settings.
        Always returns a valid key, never a placeholder.
        """
        # First try to read from volume
        key_path = "/etc/wireguard/server/publickey-server"
        if os.path.exists(key_path):
            try:
                with open(key_path, "r") as f:
                    key = f.read().strip()
                    if key and key != "SERVER_PUBLIC_KEY_NOT_FOUND":
                        return key
            except Exception:
                pass
        
        # Fallback to settings (from env var)
        from app.config import settings
        if settings.WG_SERVER_PUBLIC_KEY and settings.WG_SERVER_PUBLIC_KEY != "SERVER_PUBLIC_KEY_PLACEHOLDER":
            return settings.WG_SERVER_PUBLIC_KEY
        
        # Last resort: try alternative paths
        alt_paths = [
            "/etc/wireguard/publickey-server",
            "/config/server/publickey-server",
            "./wireguard-config/server/publickey-server"
        ]
        for alt_path in alt_paths:
            if os.path.exists(alt_path):
                try:
                    with open(alt_path, "r") as f:
                        key = f.read().strip()
                        if key:
                            return key
                except Exception:
                    continue
        
        # If still not found, raise error (don't return placeholder)
        raise ValueError("WireGuard server public key not found. Please set WG_SERVER_PUBLIC_KEY in .env or ensure key file exists.")

    @staticmethod
    def generate_keys():
        """
        Generates a private and public key pair using wg command.
        """
        # Generate Private Key
        priv_key = subprocess.check_output("wg genkey", shell=True).decode("utf-8").strip()
        # Generate Public Key
        pub_key = subprocess.check_output(f"echo '{priv_key}' | wg pubkey", shell=True).decode("utf-8").strip()
        return priv_key, pub_key

    @staticmethod
    async def get_available_ip(db: AsyncSession) -> str:
        """
        Finds the next available IP in 10.13.13.0/24 subnet.
        """
        # Get all used IPs
        result = await db.execute(select(Device.wg_ip_address).where(Device.wg_ip_address.isnot(None)))
        used_ips = [ip for ip in result.scalars().all()]
        
        # Simple linear search for MVP (2 to 254)
        for i in range(2, 255):
            candidate = f"{WG_SUBNET}{i}"
            if candidate not in used_ips:
                return candidate
        
        raise Exception("No available IPs in WireGuard subnet")

    @staticmethod
    def add_peer_to_conf(public_key: str, allowed_ip: str):
        """
        Appends a peer to wg0.conf if it does not already exist.
        """
        conf_path = "/etc/wireguard/wg0.conf"

        # Ensure directory exists (should be mounted, but safe to check)
        os.makedirs(os.path.dirname(conf_path), exist_ok=True)

        if not os.path.exists(conf_path):
            # Create empty file if it doesn't exist
            with open(conf_path, "w") as f:
                f.write("# WireGuard Config\n")

        # Check if the public key is already in the file
        with open(conf_path, "r") as f:
            if public_key in f.read():
                # print(f"DEBUG: Peer {public_key} already in {conf_path}. Skipping.")
                return


        peer_block = f"\n[Peer]\nPublicKey = {public_key}\nAllowedIPs = {allowed_ip}/32\n"
        
        with open(conf_path, "a") as f:
            f.write(peer_block)

    @staticmethod
    def generate_mikrotik_script(private_key: str, client_ip: str, server_public_key: str, server_endpoint: str, server_port: int = 51820):
        """
        Generates a MikroTik RouterOS script to configure WireGuard.
        This script is designed to be copy-pasted directly into the terminal.
        All values are validated and populated before script generation.
        """
        # Validate all required inputs
        if not private_key:
            raise ValueError("Private key is required for WireGuard script generation")
        if not client_ip:
            raise ValueError("Client IP is required for WireGuard script generation")
        if not server_endpoint:
            raise ValueError("Server endpoint is required for WireGuard script generation")
        
        # If server_public_key was passed as placeholder or invalid, fetch it
        if not server_public_key or server_public_key == "SERVER_PUBLIC_KEY_PLACEHOLDER" or server_public_key == "SERVER_PUBLIC_KEY_NOT_FOUND":
            server_public_key = WireGuardService.get_server_public_key()
        
        # Validate server_public_key is a valid WireGuard key format
        if not server_public_key or len(server_public_key) < 40:
            raise ValueError(f"Invalid server public key format: {server_public_key}")
        
        # Ensure server_port is valid
        if not server_port or server_port < 1 or server_port > 65535:
            server_port = 51820  # Default

        script = f"""
# WireGuard Setup for NetGuard
# Paste this into the Mikrotik Terminal

/interface wireguard
add listen-port=13231 mtu=1420 name=wireguard-netguard private-key="{private_key}" comment="NetGuard VPN"

/ip address
add address={client_ip}/24 interface=wireguard-netguard network={WG_SUBNET}0

/interface wireguard peers
add allowed-address=0.0.0.0/0 endpoint-address={server_endpoint} endpoint-port={server_port} \\
    interface=wireguard-netguard persistent-keepalive=25s public-key="{server_public_key}" comment="NetGuard Server"

/ip route
add disabled=no distance=1 dst-address={WG_SUBNET}1/32 gateway=wireguard-netguard routing-table=main scope=30 target-scope=10 comment="Route to NetGuard Server"

# ---------------------------------------------------
# SECURITY & ACCESS SETUP (REQUIRED)
# ---------------------------------------------------

# 1. Enable API Service (Port 8728) and Allow VPN Access
/ip service
set api disabled=no port=8728 address=0.0.0.0/0

# 2. Allow Input Traffic from NetGuard VPN (Firewall)
/ip firewall filter
add chain=input src-address={WG_SUBNET}0/24 action=accept place-before=0 comment="Allow NetGuard Monitoring"

# 3. Create NetGuard User (Optional but Recommended)
# Replace 'securepassword' with a strong password!
# /user add name=netguard group=full password="securepassword" comment="NetGuard Agent"
""".strip()
        return script
