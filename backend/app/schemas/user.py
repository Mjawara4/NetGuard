from pydantic import BaseModel, EmailStr, UUID4, validator, Field
from typing import Optional
from app.models.core import UserRole
import re

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
    full_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=128, description="Password must be at least 8 characters")
    organization_name: str = Field(..., min_length=1, max_length=255)
    
    @validator('password')
    def validate_password_strength(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r'[A-Z]', v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r'[a-z]', v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r'[0-9]', v):
            raise ValueError("Password must contain at least one number")
        return v
    
class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=255)
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    is_active: Optional[bool] = None
    
    @validator('password')
    def validate_password_strength(cls, v):
        """Validate password strength if provided."""
        if v is not None:
            if len(v) < 8:
                raise ValueError("Password must be at least 8 characters long")
            if not re.search(r'[A-Z]', v):
                raise ValueError("Password must contain at least one uppercase letter")
            if not re.search(r'[a-z]', v):
                raise ValueError("Password must contain at least one lowercase letter")
            if not re.search(r'[0-9]', v):
                raise ValueError("Password must contain at least one number")
        return v

class UserResponse(UserBase):
    id: UUID4
    organization_id: Optional[UUID4] = None
    
    class Config:
        from_attributes = True
