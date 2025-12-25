import asyncio
from app.database import AsyncSessionLocal
from app.models import Organization, Site, User
from sqlalchemy import select

async def seed_data():
    async with AsyncSessionLocal() as db:
        print("Seeding initial data...")
        
        # 1. Get Admin User
        result = await db.execute(select(User).where(User.email == "admin@netguard.ai"))
        admin = result.scalars().first()
        
        if not admin:
            print("Admin user not found! Run seed_user.py first.")
            return

        # 2. Create Organization
        # Check if exists
        result = await db.execute(select(Organization).where(Organization.name == "NetGuard HQ"))
        org = result.scalars().first()
        
        if not org:
            print("Creating Organization...")
            org = Organization(name="NetGuard HQ")
            db.add(org)
            await db.commit()
            await db.refresh(org)
        
        # Link admin to org
        if not admin.organization_id:
            print("Linking Admin to Org...")
            admin.organization_id = org.id
            db.add(admin)
            await db.commit()
            
        # 3. Create Default Site
        result = await db.execute(select(Site).where(Site.name == "Main Office"))
        site = result.scalars().first()
        
        if not site:
            print("Creating Default Site...")
            site = Site(
                name="Main Office",
                location="New York, NY",
                organization_id=org.id,
                auto_fix_enabled=True # Enable auto-fix by default for demo
            )
            db.add(site)
            await db.commit()
            
        print("Seeding complete.")
        print(f"Org ID: {org.id}")
        print(f"Site ID: {site.id}")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(seed_data())
