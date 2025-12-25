from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.auth.security import settings
from app.models import User
from sqlalchemy import select

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login", auto_error=False)

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        if token is None:
            raise credentials_exception
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if user is None:
        raise credentials_exception
    return user

    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

from fastapi import Header, Security
from fastapi.security import APIKeyHeader
from app.models import APIKey

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_api_key(
    api_key_header: str = Security(api_key_header),
    db: AsyncSession = Depends(get_db)
) -> APIKey:
    if not api_key_header:
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key",
        )
    
    result = await db.execute(select(APIKey).where(APIKey.key == api_key_header, APIKey.is_active == True))
    api_key = result.scalars().first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )
    return api_key

from typing import Union

async def get_authorized_actor(
    api_key_header: Optional[str] = Security(api_key_header),
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> Union[User, APIKey]:
    # 1. Try API Key
    if api_key_header:
        result = await db.execute(select(APIKey).where(APIKey.key == api_key_header, APIKey.is_active == True))
        api_key = result.scalars().first()
        if api_key:
            return api_key
    
    # 2. Try User Token
    if token:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id:
                result = await db.execute(select(User).where(User.id == user_id))
                user = result.scalars().first()
                if user and user.is_active:
                    return user
        except JWTError:
            pass
            
    # 3. Fail
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated (User or API Key required)",
        headers={"WWW-Authenticate": "Bearer"},
    )

from app.models.core import UserRole

async def get_current_super_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user

