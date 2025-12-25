import asyncio
import httpx
from app.config import settings

# Configuration
BASE_URL = "http://localhost:8000/api/v1"
ADMIN_EMAIL = "admin@netguard.ai"
ADMIN_PASSWORD = "admin123"

async def verify_admin_features():
    async with httpx.AsyncClient() as client:
        print("1. Authenticating as Super Admin...")
        response = await client.post(f"{BASE_URL}/auth/login", data={
            "username": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            print(f"FAILED to login: {response.text}")
            return
        
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("   Success! Token received.")

        # 2. Create a Test User (need a public signup endpoint or just check existing)
        # We will use the signup endpoint
        print("\n2. Creating a Test User...")
        test_email = "testuser@example.com"
        test_password = "password123"
        
        # Cleanup first just in case
        # We can't easily clean up via API if we don't know ID, but we can search list later.
        
        signup_resp = await client.post(f"{BASE_URL}/auth/signup", json={
            "email": test_email,
            "password": test_password,
            "full_name": "Test User",
            "organization_name": "Test Org"
        })
        
        if signup_resp.status_code in [200, 201]: # Or 400 if exists
             print("   User created correctly.")
             test_user = signup_resp.json()
             test_user_id = test_user["id"]
        elif signup_resp.status_code == 400 and "already registered" in signup_resp.text:
             print("   User already exists, finding in list...")
             list_resp = await client.get(f"{BASE_URL}/admin/users", headers=headers)
             users = list_resp.json()
             test_user = next((u for u in users if u["email"] == test_email), None)
             if not test_user:
                 print("   FAILED: Could not find existing user.")
                 return
             test_user_id = test_user["id"]
        else:
            print(f"   FAILED: {signup_resp.text}")
            return

        print(f"   Test User ID: {test_user_id}")

        # 3. List Users
        print("\n3. Listing Users...")
        resp = await client.get(f"{BASE_URL}/admin/users", headers=headers)
        if resp.status_code == 200:
            users = resp.json()
            if any(u['id'] == test_user_id for u in users):
                print(f"   Success! Found test user in list of {len(users)} users.")
            else:
                print("   FAILED: Test user not in list.")
        else:
            print(f"   FAILED: {resp.text}")

        # 4. Deactivate User (Update)
        print("\n4. Deactivating User...")
        resp = await client.put(f"{BASE_URL}/admin/users/{test_user_id}", headers=headers, json={
            "is_active": False,
            "role": "viewer" # Changing role too
        })
        if resp.status_code == 200:
            data = resp.json()
            if data["is_active"] is False and data["role"] == "viewer":
                print("   Success! User deactivated and role changed.")
            else:
                print(f"   FAILED: Response did not match expected values. Got: {data}")
        else:
            print(f"   FAILED: {resp.text}")

        # 5. Reactivate User (Update)
        print("\n5. Reactivating User...")
        resp = await client.put(f"{BASE_URL}/admin/users/{test_user_id}", headers=headers, json={
            "is_active": True,
            "role": "org_admin"
        })
        if resp.status_code == 200:
             print("   Success! User reactivated.")
        else:
             print(f"   FAILED: {resp.text}")

        # 6. Reset Password
        print("\n6. Resetting Password...")
        resp = await client.put(f"{BASE_URL}/admin/users/{test_user_id}/password", headers=headers, json={
            "new_password": "newpassword123"
        })
        if resp.status_code == 200:
            print("   Success! Password reset.")
            # Verify login with new password
            login_check = await client.post(f"{BASE_URL}/auth/login", data={
                "username": test_email,
                "password": "newpassword123"
            })
            if login_check.status_code == 200:
                print("   Verified: Test user can login with new password.")
            else:
                print("   FAILED: Could not login with new password.")
        else:
            print(f"   FAILED: {resp.text}")

        # 7. Check Security Stats
        print("\n7. Checking Security Stats...")
        resp = await client.get(f"{BASE_URL}/admin/security", headers=headers)
        if resp.status_code == 200:
            print(f"   Success! Stats: {resp.json()}")
        else:
            print(f"   FAILED: {resp.text}")

        # 8. Delete User
        print("\n8. Deleting User...")
        resp = await client.delete(f"{BASE_URL}/admin/users/{test_user_id}", headers=headers)
        if resp.status_code == 200:
            print("   Success! User deleted.")
            # Verify gone
            get_check = await client.get(f"{BASE_URL}/admin/users", headers=headers)
            users = get_check.json()
            if not any(u['id'] == test_user_id for u in users):
                print("   Verified: User is gone from list.")
            else:
                print("   FAILED: User still visible in list.")
        else:
            print(f"   FAILED: {resp.text}")

if __name__ == "__main__":
    asyncio.run(verify_admin_features())
