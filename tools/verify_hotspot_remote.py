
import requests
import sys

# Constants
API_URL = "http://localhost:8000/api/v1"
USERNAME = "admin@netguard.ai"
PASSWORD = "admin123" # Default seeded password
DEVICE_ID = "b917349a-eb31-41ea-8f79-5e80d0195201"

def login():
    try:
        response = requests.post(f"{API_URL}/auth/login", data={
            "username": USERNAME,
            "password": PASSWORD
        })
        response.raise_for_status()
        return response.json()["access_token"]
    except Exception as e:
        print(f"Login failed: {e}")
        if response.text:
            print(f"Response: {response.text}")
        sys.exit(1)

def get_hotspot_users(token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        # Note: Port 8728 is hardcoded in the router API logic if we force it
        url = f"{API_URL}/hotspot/{DEVICE_ID}/users"
        print(f"Fetching: {url}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        users = response.json()
        print(f"Success! Found {len(users)} users.")
        print(users)
    except Exception as e:
        print(f"Hotspot API failed: {e}")
        if response.text:
            print(f"Response: {response.text}")
        sys.exit(1)

if __name__ == "__main__":
    print("Starting verification...")
    token = login()
    print("Login successful.")
    get_hotspot_users(token)
