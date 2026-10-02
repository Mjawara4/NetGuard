import subprocess
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Device
from app.core.config import settings

WG_CONF_DIR = "/etc/wireguard"
WG_CONF_PATH = f"{WG_CONF_DIR}/wg0.conf"
WG_SUBNET = "10.13.13."

# The running server does NOT necessarily read WG_CONF_PATH.
#
# linuxserver/wireguard (the image docker-compose.yml runs) keeps its live
# config in /config/wg_confs/wg0.conf, and migrates a legacy /config/wg0.conf
# into it at container start. Our bind mount makes /config the same directory
# as WG_CONF_DIR, so BOTH files exist and they are different files -- on the
# production host they had distinct inodes, created four seconds apart during
# the same container startup.
#
# Appending a peer only to the legacy file therefore wrote it somewhere nothing
# read: a freshly provisioned router could never complete a handshake, with no
# error anywhere. Peers are written to every candidate so the peer is live
# whichever file the image prefers, and survives a restart that re-migrates.
WG_ACTIVE_CONF_SUBDIR = "wg_confs"

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
        from app.core.config import settings
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
    def conf_targets(conf_dir: str = WG_CONF_DIR) -> list:
        """Every wg0.conf the running server might read, most authoritative first.

        The presence of the wg_confs/ directory is the signal that the image
        migrated to the newer layout; it is never created here, because creating
        it would change which file the server reads on its next start.
        """
        targets = []
        active_dir = os.path.join(conf_dir, WG_ACTIVE_CONF_SUBDIR)
        if os.path.isdir(active_dir):
            targets.append(os.path.join(active_dir, "wg0.conf"))
        targets.append(os.path.join(conf_dir, "wg0.conf"))
        return targets

    @staticmethod
    def add_peer_to_conf(public_key: str, allowed_ip: str, conf_dir: str = WG_CONF_DIR):
        """Append a peer to every conf the server might read, skipping any that has it.

        Writing to one file is what caused a peer to be accepted by the API and
        silently never reach the tunnel; see the note on WG_ACTIVE_CONF_SUBDIR.
        Each file is checked separately, so a conf that is missing the peer gets
        it even when another already has it.
        """
        os.makedirs(conf_dir, exist_ok=True)

        peer_block = f"\n[Peer]\nPublicKey = {public_key}\nAllowedIPs = {allowed_ip}/32\n"

        for conf_path in WireGuardService.conf_targets(conf_dir):
            if not os.path.exists(conf_path):
                with open(conf_path, "w") as f:
                    f.write("# WireGuard Config\n")

            with open(conf_path, "r") as f:
                if public_key in f.read():
                    continue

            with open(conf_path, "a") as f:
                f.write(peer_block)

    @staticmethod
    def generate_mikrotik_script(private_key: str, client_ip: str, server_public_key: str, server_endpoint: str, server_port: int = 51820):
        """
        Generates a MikroTik RouterOS script to configure WireGuard.
        This script is designed to be copy-pasted directly into the terminal.
        All values are validated and populated before script generation.

        Every object created here carries comment="NetGuard", and that string is
        load-bearing, not decoration: the provisioning script's preflight
        (app/services/provisioning/sections.py) refuses any router whose
        `wireguard-netguard` interface has a different comment, on the grounds
        that it was configured by someone else. This script is the one the UI
        tells a customer to run FIRST ("Setup WireGuard VPN", from the 409 that
        provision-script returns), so a mismatch here means a customer who
        follows our own instructions reaches a router the next step refuses, with
        a factory reset as the only exit. Keep the two generators in step --
        test_provision_sections_tunnel.py compares them token by token.
        """
        # Validate all required inputs
        if not private_key:
            raise ValueError("Private key is required for WireGuard script generation")
        if not client_ip:
            raise ValueError("Client IP is required for WireGuard script generation")
        if not server_endpoint:
            raise ValueError("Server endpoint is required for WireGuard script generation")
        
        # If server_public_key was passed as placeholder or invalid, fetch it
        invalid_values = [
            "SERVER_PUBLIC_KEY_PLACEHOLDER",
            "SERVER_PUBLIC_KEY_NOT_FOUND",
            "auto-read-from-volume-or-manual"
        ]
        
        if not server_public_key or server_public_key in invalid_values or len(server_public_key) < 40:
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
add listen-port=13231 mtu=1420 name=wireguard-netguard private-key="{private_key}" comment="NetGuard"

/ip address
add address={client_ip}/24 interface=wireguard-netguard network={WG_SUBNET}0 comment="NetGuard"

/interface wireguard peers
add allowed-address={WG_SUBNET}0/24 endpoint-address={server_endpoint} endpoint-port={server_port} \\
    interface=wireguard-netguard persistent-keepalive=25s public-key="{server_public_key}" comment="NetGuard"

/ip route
add disabled=no distance=1 dst-address={WG_SUBNET}1/32 gateway=wireguard-netguard routing-table=main scope=30 target-scope=10 comment="NetGuard"

# ---------------------------------------------------
# SECURITY & ACCESS SETUP (REQUIRED)
# ---------------------------------------------------

# 1. Enable API Service (Port 8728) and Allow VPN Access
# The API accepts a stored credential, so it is pinned at the service as well
# as in the firewall. Relying on one filter rule's position means a single
# reorder exposes it to the internet.
/ip service
set api disabled=no port=8728 address={WG_SUBNET}0/24

# 2. Allow Input Traffic from NetGuard VPN (Firewall)
# Scoped to the tunnel interface. A bare src-address accept trusts anything that can put
# that source address into the input chain -- observed on a real hEX sitting at input
# position 0, above the stock accept-established and both drop-invalid rules.
# Placed above the first BLOCKING rule rather than at a fixed index: `place-before=0`
# fails with `no such item` on a router whose filter table is empty, and position 0
# outranks the stock rules it should sit below. Guarded on its own comment so pressing
# the button twice does not stack duplicates.
# All on one line on purpose: this script is pasted into the terminal, where :local does
# not persist from one line to the next.
:if ([:len [/ip firewall filter find where comment="Allow NetGuard Monitoring"]] = 0) do={{ :local ngblock [/ip firewall filter find where chain=input and (action=drop or action=reject or action=tarpit) and !dynamic]; :if ([:len $ngblock] > 0) do={{ /ip firewall filter add chain=input in-interface=wireguard-netguard src-address={WG_SUBNET}0/24 action=accept comment="Allow NetGuard Monitoring" place-before=[:pick $ngblock 0] }} else={{ /ip firewall filter add chain=input in-interface=wireguard-netguard src-address={WG_SUBNET}0/24 action=accept comment="Allow NetGuard Monitoring" }} }}

# 3. API user -- deliberately NOT created here, and no placeholder password.
# A password written into a script people paste tends to stay as it was written. The
# one-shot setup script ("Get setup script" in the dashboard) creates the netguard user
# with a generated password and stores it against the device, so monitoring
# authenticates without anyone having to choose a secret. Run that next.
""".strip()
        return script
