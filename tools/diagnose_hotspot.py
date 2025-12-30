import asyncio
from app.database import AsyncSessionLocal
from sqlalchemy import select
from app.models import Device
from app.routers.hotspot import get_api_pool
from app.models.core import decrypt_device_secrets
import sys

async def test_connection():
    target_ip = '10.13.13.2'
    print(f"--- Diagnosing Connection to {target_ip} ---")
    
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Device).where(Device.ip_address == target_ip))
        device = res.scalars().first()
        if not device:
            print(f'ERROR: Device {target_ip} not found in database.')
            return
            
        print(f"Device Found: {device.name} (ID: {device.id})")
        
        # Check Encryption
        is_encrypted = device.ssh_password and device.ssh_password.startswith("gAAAAAB")
        print(f"Password stored encrypted? {is_encrypted}")
        
        decrypt_device_secrets(device)
        print(f"Credentials: User='{device.ssh_username}' Password_Len={len(device.ssh_password) if device.ssh_password else 0}")
        
        try:
            port = getattr(device, 'ssh_port', 8728) or 8728
            print(f"Attempting API connection to {device.ip_address}:{port}...")
            
            conn = get_api_pool(device.ip_address, device.ssh_username or 'admin', device.ssh_password or 'admin', int(port))
            api = conn.get_api()
            print('SUCCESS: Connection established!')
            
            users = api.get_resource('/ip/hotspot/user').get()
            print(f'SUCCESS: Fetched {len(users)} users.')
            
            profiles = api.get_resource('/ip/hotspot/user/profile').get()
            print(f'SUCCESS: Fetched {len(profiles)} profiles.')
            
            conn.disconnect()
        except Exception as e:
            print(f'FAILURE: {e}')
            # specific hints
            err = str(e)
            if "Authentication failed" in err:
                 print("-> Check Username/Password.")
            elif "timed out" in err or "time out" in err:
                 print("-> Connection Timed Out. Check VPN Status (can you ping it?).")
            elif "No route to host" in err:
                 print("-> No Route to Host. VPN tunnel might be down.")
            elif "Connection refused" in err:
                 print("-> Connection Refused. Is API service enabled on RouterOS (port 8728)?")

if __name__ == "__main__":
    asyncio.run(test_connection())
