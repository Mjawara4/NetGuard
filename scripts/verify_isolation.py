
import requests
import uuid
import sys

API_URL = "https://app.netguard.fun/api/v1"

def random_string(length=8):
    import random, string
    return ''.join(random.choices(string.ascii_lowercase, k=length))

def signup_user(name):
    email = f"{name}_{random_string()}@example.com"
    password = "Password123!"
    payload = {
        "email": email,
        "password": password,
        "full_name": name,
        "organization_name": f"{name} Corp"
    }
    try:
        res = requests.post(f"{API_URL}/auth/signup", json=payload)
        res.raise_for_status()
        print(f"✅ Signed up {name} ({email})")
        return email, password
    except Exception as e:
        print(f"❌ Signup failed for {name}: {e}")
        if res.text: print(res.text)
        sys.exit(1)

def login_user(email, password):
    try:
        res = requests.post(f"{API_URL}/auth/login", data={"username": email, "password": password})
        res.raise_for_status()
        return res.json()["access_token"]
    except Exception as e:
        print(f"❌ Login failed for {email}: {e}")
        sys.exit(1)

def create_resource(token, name):
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Create Site
    site_payload = {
        "name": f"{name} Site",
        "address": "123 Test St"
    }
    res = requests.post(f"{API_URL}/inventory/sites", json=site_payload, headers=headers)
    res.raise_for_status()
    site_id = res.json()["id"]
    
    # 2. Create Device
    device_payload = {
        "name": f"{name} Router",
        "ip_address": "192.168.88.1",
        "device_type": "router",
        "site_id": site_id
    }
    res = requests.post(f"{API_URL}/inventory/devices", json=device_payload, headers=headers)
    res.raise_for_status()
    device_id = res.json()["id"]
    
    print(f"✅ {name} created Device {device_id}")
    return device_id

def verify_isolation(token_viewer, viewer_name, target_device_id, owner_name):
    headers = {"Authorization": f"Bearer {token_viewer}"}
    
    # 1. List Devices
    res = requests.get(f"{API_URL}/inventory/devices", headers=headers)
    res.raise_for_status()
    devices = res.json()
    
    found = any(d['id'] == target_device_id for d in devices)
    if found:
        print(f"❌ DATA LEAK: {viewer_name} can see {owner_name}'s device in list!")
        sys.exit(1)
    else:
        print(f"✅ {viewer_name} cannot see {owner_name}'s device in list.")
        
    # 2. Get Device Direct
    res = requests.get(f"{API_URL}/inventory/devices/{target_device_id}", headers=headers)
    if res.status_code == 404:
        print(f"✅ {viewer_name} gets 404 when trying to access {owner_name}'s device directly.")
    else:
        print(f"❌ DATA LEAK: {viewer_name} accessed {owner_name}'s device! Status: {res.status_code}")
        sys.exit(1)

def main():
    print("🧪 Starting Tenant Isolation Verification...")
    
    # 1. Setup User A
    email_a, pass_a = signup_user("UserA")
    token_a = login_user(email_a, pass_a)
    dev_a = create_resource(token_a, "UserA")
    
    # 2. Setup User B
    email_b, pass_b = signup_user("UserB")
    token_b = login_user(email_b, pass_b)
    dev_b = create_resource(token_b, "UserB")
    
    print("\n🕵️  Verifying Isolation...")
    
    # 3. User B tries to access User A's stuff
    verify_isolation(token_b, "UserB", dev_a, "UserA")
    
    # 4. User A tries to access User B's stuff
    verify_isolation(token_a, "UserA", dev_b, "UserB")
    
    print("\n🎉 SUCCESS: Strict Data Isolation Verified!")

if __name__ == "__main__":
    main()
