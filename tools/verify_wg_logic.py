import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from app.services.wireguard import WireGuardService

def test_script_generation():
    print("Testing Mikrotik Script Generation...")
    
    priv_key = "PRIVATE_KEY_EXAMPLE"
    client_ip = "10.13.13.10"
    server_pub = "SERVER_PUB_EXAMPLE"
    server_endpoint = "1.2.3.4"
    
    script = WireGuardService.generate_mikrotik_script(
        private_key=priv_key,
        client_ip=client_ip,
        server_public_key=server_pub,
        server_endpoint=server_endpoint
    )
    
    print("\nGenerated Script:\n")
    print(script)
    
    assert f'private-key="{priv_key}"' in script
    assert f'address={client_ip}/24' in script
    assert f'endpoint-address={server_endpoint}' in script
    
    print("\nVerification Successful!")

if __name__ == "__main__":
    test_script_generation()
