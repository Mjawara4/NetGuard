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
        Reads the server public key from the shared volume.
        """
        key_path = "/etc/wireguard/server/publickey-server"
        if os.path.exists(key_path):
            with open(key_path, "r") as f:
                return f.read().strip()
        return "SERVER_PUBLIC_KEY_NOT_FOUND"

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
        Appends a peer to wg0.conf
        """
        # LinuxServer image usually puts active conf in /config/wg_confs/wg0.conf or /config/wg0.conf
        # Based on ls output: /config/wg_confs/ exists.
        # Let's target /etc/wireguard/wg_confs/wg0.conf inside the container
        # (mapped from ./wireguard-config/wg_confs/wg0.conf)
        
        conf_path = "/etc/wireguard/wg_confs/wg0.conf"
        
        # Fallback if not there (maybe it's in root of config)
        if not os.path.exists(conf_path):
             conf_path = "/etc/wireguard/wg0.conf"

        if not os.path.exists(conf_path):
            print(f"WARNING: {conf_path} not found. Skipping config write.")
            return

        peer_block = f"\n[Peer]\nPublicKey = {public_key}\nAllowedIPs = {allowed_ip}/32\n"
        
        with open(conf_path, "a") as f:
            f.write(peer_block)

    @staticmethod
    def generate_mikrotik_script(private_key: str, client_ip: str, server_public_key: str, server_endpoint: str, server_port: int = 51820):
        """
        Generates a MikroTik RouterOS script to configure WireGuard.
        This script is designed to be copy-pasted directly into the terminal.
        """
        # If server_public_key was passed as placeholder, try to fetch it
        if server_public_key == "SERVER_PUBLIC_KEY_PLACEHOLDER":
             server_public_key = WireGuardService.get_server_public_key()

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
""".strip()
        return script
