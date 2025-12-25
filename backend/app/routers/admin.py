from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
from app.database import get_db
from app.auth.deps import get_current_super_admin
from app.models import User, APIKey, Device, Organization
from app.schemas.user import UserResponse
from pydantic import BaseModel
from uuid import UUID

router = APIRouter()

class UserUpdate(BaseModel):
    is_active: bool
    role: str

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = 0, 
    limit: int = 100, 
    db: AsyncSession = Depends(get_db), 
    admin: User = Depends(get_current_super_admin)
):
    result = await db.execute(select(User).offset(skip).limit(limit))
    return result.scalars().all()

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_super_admin)
):
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = user_update.is_active
    user.role = user_update.role
    await db.commit()
    await db.refresh(user)
    return user

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_super_admin)
):
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.delete(user)
    await db.commit()
    return {"status": "success", "message": "User deleted"}

class PasswordReset(BaseModel):
    new_password: str

@router.put("/users/{user_id}/password")
async def reset_user_password(
    user_id: str,
    pw_data: PasswordReset,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_super_admin)
):
    from app.auth.security import get_password_hash
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.hashed_password = get_password_hash(pw_data.new_password)
    await db.commit()
    return {"status": "success", "message": "Password reset successfully"}

@router.get("/security")
async def get_security_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_super_admin)
):
    # Count Users
    user_count = await db.scalar(select(func.count(User.id)))
    admin_count = await db.scalar(select(func.count(User.id)).where(User.role == "super_admin"))
    
    # Count Keys
    key_count = await db.scalar(select(func.count(APIKey.id)))
    
    # Count Devices
    device_count = await db.scalar(select(func.count(Device.id)))
    
    return {
        "total_users": user_count,
        "super_admins": admin_count,
        "active_api_keys": key_count,
        "monitored_devices": device_count,
        "system_status": "SECURE" # Placeholder for actual security check
    }
