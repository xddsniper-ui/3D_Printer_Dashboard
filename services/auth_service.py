"""
Auth service: JWT tokens, password hashing, role checking.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select

from core.config import settings
from core.database import AsyncSessionLocal
from core.user import User


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


async def get_user_by_id(user_id: str) -> Optional[User]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()


async def get_user_by_username(username: str) -> Optional[User]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()


async def authenticate_user(username: str, password: str) -> Optional[User]:
    user = await get_user_by_username(username)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


async def create_default_admin():
    """Creates a default admin on first run if no users exist."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User))
        if result.first():
            return  # Users already exist

        admin = User(
            id="admin-001",
            username="admin",
            hashed_password=hash_password("changeme123"),
            role="admin",
            allowed_printer_ids=None,  # Access to all printers
        )
        db.add(admin)
        await db.commit()
        print("⚠️  Default admin created: username=admin password=changeme123 — CHANGE THIS!")