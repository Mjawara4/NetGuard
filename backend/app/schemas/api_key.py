from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class APIKeyCreate(BaseModel):
    description: Optional[str] = None

class APIKeyResponse(BaseModel):
    id: UUID
    key: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None
    organization_id: Optional[UUID]

    class Config:
        from_attributes = True  # Updated from orm_mode (Pydantic v2)
