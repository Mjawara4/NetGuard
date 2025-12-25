import asyncio
from app.database import AsyncSessionLocal
from app.models import User, UserRole
from app.auth.security import get_password_hash
from sqlalchemy import select

async def seed_user():
    async with AsyncSessionLocal() as db:
        # Check if user exists
        result = await db.execute(select(User).where(User.email == "admin@netguard.ai"))
        user = result.scalars().first()
        
        # Check/Create Organization
        from app.models import Organization
        result = await db.execute(select(Organization).where(Organization.name == "NetGuard Default"))
        org = result.scalars().first()
        
        if not org:
            print("Creating default organization...")
            org = Organization(name="NetGuard Default")
            db.add(org)
            await db.commit()
            await db.refresh(org)
        
        if not user:
            print("Creating default admin user...")
            hashed_pw = get_password_hash("admin123")
            new_user = User(
                email="admin@netguard.ai",
                hashed_password=hashed_pw,
                full_name="NetGuard Admin",
                role=UserRole.SUPER_ADMIN,
                is_active=True,
                organization_id=org.id
            )
            db.add(new_user)
            await db.commit()
            print("User properties: email=admin@netguard.ai, password=admin123")
        elif user.organization_id != org.id:
             print(f"Correcting admin user organization to {org.name}...")
             user.organization_id = org.id
             db.add(user)
             await db.commit()
        else:
            print("Admin user verified.")

        # Seed API Key
        from app.models import APIKey
        result = await db.execute(select(APIKey).where(APIKey.key == "agent-secret-key-123"))
        api_key = result.scalars().first()
        
        if not api_key:
            print("Creating default API Key...")
            new_key = APIKey(
                key="agent-secret-key-123",
                description="Default Agent Key",
                is_active=True,
                organization_id=org.id
            )
            db.add(new_key)
            await db.commit()
            print("API Key created: agent-secret-key-123")
        else:
            print("API Key already exists.")
            
        # Seed Site and Device
        # from app.models import Site, Device
        
        # # Check Site
        # result = await db.execute(select(Site).where(Site.name == "Headquarters", Site.organization_id == org.id))
        # site = result.scalars().first()
        
        # if not site:
        #     print("Creating default Site...")
        #     # site = Site(name="Headquarters", location="New York, NY", organization_id=org.id)
        #     # db.add(site)
        #     # await db.commit()
        #     # await db.refresh(site)
            
        # # Check Device
        # # result = await db.execute(select(Device).where(Device.ip_address == "192.168.88.1", Device.site_id == site.id))
        # # device = result.scalars().first()
        
        # # if not device:
        # #     print("Creating default Device...")
        # #     device = Device(
        # #         name="Core Router",
        # #         ip_address="192.168.88.1",
        # #         device_type="router",
        # #         site_id=site.id,
        # #         is_active=True,
        # #         ssh_username="admin",
        # #         ssh_password="password"
        # #     )
        # #     db.add(device)
        # #     await db.commit()
        # #     print("Default Site 'Headquarters' and Device 'Core Router' created.")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(seed_user())
