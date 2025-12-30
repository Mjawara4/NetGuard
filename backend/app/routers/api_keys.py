from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List
from app.core.database import get_db
from app.auth.deps import get_current_user
from app.models import User, APIKey
from app.schemas.api_key import APIKeyCreate, APIKeyResponse
import secrets
import uuid

router = APIRouter()

@router.get("/", response_model=List[APIKeyResponse])
async def get_api_keys(
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    if not current_user.organization_id:
        return []
        
    result = await db.execute(
        select(APIKey).where(
            APIKey.organization_id == current_user.organization_id,
            APIKey.is_active == True
        )
    )
    return result.scalars().all()

@router.post("/", response_model=APIKeyResponse)
async def create_api_key(
    key_in: APIKeyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User must belong to an organization")
        
    # Generate a secure random key
    # Format: ng_sk_<random_hex>
    raw_key = secrets.token_urlsafe(32)
    api_key_str = f"ng_sk_{raw_key}"
    
    new_key = APIKey(
        key=api_key_str,
        description=key_in.description,
        organization_id=current_user.organization_id,
        is_active=True
    )
    
    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)
    return new_key

@router.delete("/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify ownership
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == uuid.UUID(key_id), 
            APIKey.organization_id == current_user.organization_id
        )
    )
    key_obj = result.scalars().first()
    
    if not key_obj:
        raise HTTPException(status_code=404, detail="API Key not found")
        
    await db.delete(key_obj)
    await db.commit()
    return

@router.get("/usage", response_model=List[APIKeyResponse])
async def get_usage_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get API key usage statistics.
    Returns list of API keys with their last_used_at timestamps.
    """
    if not current_user.organization_id:
        return []
        
    result = await db.execute(
        select(APIKey).where(
            APIKey.organization_id == current_user.organization_id,
            APIKey.is_active == True
        ).order_by(APIKey.last_used_at.desc().nulls_last())
    )
    return result.scalars().all()
