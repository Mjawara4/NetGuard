import requests
import json

BASE_URL = "http://localhost:8000/api/v1"
API_KEY = "agent-secret-key-123"
HEADERS = {"X-API-Key": API_KEY}

def test_get_devices():
    print("\n--- Testing GET /inventory/devices ---")
    resp = requests.get(f"{BASE_URL}/inventory/devices", headers=HEADERS)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        devices = resp.json()
        print(f"Found {len(devices)} devices")
        for d in devices:
            print(f" - {d['name']} ({d['id']})")
        return devices[0]['id'] if devices else None
    else:
        print(f"Error: {resp.text}")
        return None

def test_get_hotspot_users(device_id):
    print(f"\n--- Testing GET /hotspot/{device_id}/users ---")
    resp = requests.get(f"{BASE_URL}/hotspot/{device_id}/users", headers=HEADERS)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        users = resp.json()
        print(f"Found {len(users)} users")
    else:
        print(f"Error: {resp.text}")

def test_batch_generate(device_id):
    print(f"\n--- Testing POST /hotspot/{device_id}/users/batch ---")
    payload = {
        "qty": 2,
        "prefix": "testapi",
        "profile": "default",
        "random_mode": True
    }
    resp = requests.post(f"{BASE_URL}/hotspot/{device_id}/users/batch", headers=HEADERS, json=payload)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        users = resp.json()
        print(f"Generated {len(users)} users: {users}")
    else:
        print(f"Error: {resp.text}")

def test_get_sites():
    print("\n--- Testing GET /inventory/sites ---")
    resp = requests.get(f"{BASE_URL}/inventory/sites", headers=HEADERS)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        sites = resp.json()
        print(f"Found {len(sites)} sites")

def test_get_singular_device(device_id):
    print(f"\n--- Testing GET /inventory/devices/{device_id} ---")
    resp = requests.get(f"{BASE_URL}/inventory/devices/{device_id}", headers=HEADERS)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        device = resp.json()
        print(f"Confirmed Device: {device['name']}")

if __name__ == "__main__":
    test_get_sites()
    device_id = test_get_devices()
    if device_id:
        test_get_singular_device(device_id)
        test_get_hotspot_users(device_id)
        test_batch_generate(device_id)
    else:
        print("No device found to test hotspot.")
