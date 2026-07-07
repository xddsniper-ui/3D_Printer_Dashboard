from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy import update
from core.database import AsyncSessionLocal
from core.user import User
from services.auth_service import authenticate_user, create_access_token, decode_token, get_user_by_id

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    user_id: str
    username: str


class UserOut(BaseModel):
    id: str
    username: str
    role: str
    allowed_printer_ids: Optional[list]
    is_active: bool


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = await get_user_by_id(payload.get("sub"))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.post("/login", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(form.username, form.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    # Update last login
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(User)
            .where(User.id == user.id)
            .values(last_login=datetime.now(timezone.utc))
        )
        await db.commit()

    token = create_access_token({"sub": user.id, "role": user.role})
    return Token(
        access_token=token,
        token_type="bearer",
        role=user.role,
        user_id=user.id,
        username=user.username,
    )


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut(
        id=user.id,
        username=user.username,
        role=user.role,
        allowed_printer_ids=user.allowed_printer_ids,
        is_active=user.is_active,
    )