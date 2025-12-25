import asyncio
from app.database import AsyncSessionLocal
from app.models import User
from app.auth.security import get_password_hash
from sqlalchemy import select

async def reset_password():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == "admin@netguard.ai"))
        user = result.scalars().first()
        
        if user:
            print(f"User found: {user.email}")
            new_hash = get_password_hash("admin123")
            user.hashed_password = new_hash
            await db.commit()
            print("Password forcefully updated to: admin123")
        else:
            print("User not found!")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(reset_password())
