from pydantic import BaseModel, EmailStr, UUID4
from typing import Optional
from app.models.core import UserRole

# Token
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    id: Optional[UUID4] = None

# User
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole = UserRole.VIEWER
    is_active: Optional[bool] = True

class UserCreate(UserBase):
    password: str
    organization_id: Optional[UUID4] = None

class UserRegister(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    organization_name: str
    
class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase):
    id: UUID4
    organization_id: Optional[UUID4] = None
    
    class Config:
        from_attributes = True
