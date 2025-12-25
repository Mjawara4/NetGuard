import subprocess
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Device
from app.config import settings

WG_CONF_PATH = "/etc/wireguard/wg0.conf"
WG_SUBNET = "10.13.13."
WG_SERVER_PUBKEY = "SERVER_PUBLIC_KEY_PLACEHOLDER" # Should be fetched or configured
# In a real setup, we might read the server's public key from a file or env.
# For this MVP, we might need to assume it's known or readable.

class WireGuardService:
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
        if not os.path.exists(WG_CONF_PATH):
            # If running locally without volume mount or valid path, warn but don't crash dev
            print(f"WARNING: {WG_CONF_PATH} not found. Skipping config write.")
            return

        peer_block = f"\n[Peer]\nPublicKey = {public_key}\nAllowedIPs = {allowed_ip}/32\n"
        
        with open(WG_CONF_PATH, "a") as f:
            f.write(peer_block)
            
        # Reload wireguard if possible?
        # In docker, we might share a pid namespace or trigger it externally.
        # For now, we assume simple config append is step 1.
        # Ideally: subprocess.run(["wg", "syncconf", "wg0", ...]) inside the wg container.
        # But we are in backend container.
        # Common pattern: The WG container watches the file or reloads periodically, 
        # or we just rely on restart. For MVP, we just write the file.
        pass

    @staticmethod
    def generate_mikrotik_script(private_key: str, client_ip: str, server_public_key: str, server_endpoint: str, server_port: int = 51820):
        """
        Generates a MikroTik RouterOS script to configure WireGuard.
        """
        # Note: MikroTik WireGuard implementation details
        # Interface name: wireguard1
        # Peer endpoint: server_endpoint:server_port
        
        script = f"""
# WireGuard Setup for NetGuard
/interface wireguard
add listen-port=13231 mtu=1420 name=wireguard-netguard private-key="{private_key}"

/ip address
add address={client_ip}/24 interface=wireguard-netguard network=10.13.13.0

/interface wireguard peers
add allowed-address=0.0.0.0/0 endpoint-address={server_endpoint} endpoint-port={server_port} \\
    interface=wireguard-netguard persistent-keepalive=25s public-key="{server_public_key}"

/ip route
add disabled=no distance=1 dst-address=10.13.13.1/32 gateway=wireguard-netguard routing-table=main scope=30 target-scope=10
""".strip()
        return script
