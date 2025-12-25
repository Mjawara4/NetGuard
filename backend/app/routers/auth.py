from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.auth.security import verify_password, create_access_token, get_password_hash
from app.models import User
from app.schemas.user import UserCreate, UserRegister, UserResponse, Token
from app.models.core import Organization, UserRole
from app.auth.deps import get_current_user
from pydantic import BaseModel

router = APIRouter()

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    # Find user
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalars().first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(subject=user.id)
    access_token = create_access_token(subject=user.id)
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/signup", response_model=UserResponse)
async def signup(user_in: UserRegister, db: AsyncSession = Depends(get_db)):
    # Check if user exists
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create Organization
    new_org = Organization(name=user_in.organization_name)
    db.add(new_org)
    await db.flush() # Get the ID
    
    hashed_pw = get_password_hash(user_in.password)
    new_user = User(
        email=user_in.email,
        hashed_password=hashed_pw,
        full_name=user_in.full_name,
        role=UserRole.ORG_ADMIN,
        is_active=True,
        organization_id=new_org.id
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

class PasswordChange(BaseModel):
    old_password: str
    new_password: str

@router.post("/change-password")
async def change_password(
    pw_data: PasswordChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not verify_password(pw_data.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect old password")
    
    current_user.hashed_password = get_password_hash(pw_data.new_password)
    await db.commit()
    return {"status": "success", "message": "Password updated"}
