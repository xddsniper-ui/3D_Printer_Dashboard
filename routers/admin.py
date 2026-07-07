from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from pydantic import BaseModel

from routers.auth import get_current_user, require_admin

router = APIRouter()


class AdminResponse(BaseModel):
    message: str


@router.get("/status", response_model=AdminResponse)
async def admin_status(current_user=Depends(require_admin)):
    """Admin endpoint to check system status"""
    return {"message": "Admin panel ready"}
