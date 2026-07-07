from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel

from core.user import User
from routers.auth import get_current_user, require_admin
from services.prusalink_client import (
    fetch_all_statuses,
    get_client,
    get_all_printer_configs,
    PrinterStatus,
)

router = APIRouter()


class PrinterStatusOut(BaseModel):
    printer_id: str
    name: str
    state: str
    state_text: str
    progress_pct: float
    job_name: Optional[str]
    filament: Optional[str]
    nozzle_temp: Optional[float]
    bed_temp: Optional[float]
    time_remaining_sec: Optional[int]
    camera_url: Optional[str]
    version: Optional[str]
    pi_id: str
    allowed: bool  # Whether the current user can use this printer


def _user_can_access(user: User, printer_id: str) -> bool:
    """Check if user is allowed to use this printer."""
    if user.role == "admin":
        return True
    if user.allowed_printer_ids is None:
        return True  # None = all printers
    return printer_id in user.allowed_printer_ids


@router.get("/", response_model=List[PrinterStatusOut])
async def list_printers(user: User = Depends(get_current_user)):
    """Get status of all printers. Marks which ones the user can access."""
    statuses = await fetch_all_statuses()
    return [
        PrinterStatusOut(
            **{k: v for k, v in status.__dict__.items()},
            allowed=_user_can_access(user, status.printer_id),
        )
        for status in statuses
    ]


@router.get("/{printer_id}", response_model=PrinterStatusOut)
async def get_printer(printer_id: str, user: User = Depends(get_current_user)):
    configs = get_all_printer_configs()
    if printer_id not in configs:
        raise HTTPException(status_code=404, detail="Printer not found")
    
    statuses = await fetch_all_statuses()
    status = next((s for s in statuses if s.printer_id == printer_id), None)
    if not status:
        raise HTTPException(status_code=404, detail="Printer not found")

    return PrinterStatusOut(
        **{k: v for k, v in status.__dict__.items()},
        allowed=_user_can_access(user, printer_id),
    )


@router.post("/{printer_id}/pause")
async def pause_printer(printer_id: str, user: User = Depends(require_admin)):
    client = get_client(printer_id)
    if not client:
        raise HTTPException(status_code=404, detail="Printer not found")
    success = await client.pause_job()
    return {"success": success}


@router.post("/{printer_id}/resume")
async def resume_printer(printer_id: str, user: User = Depends(require_admin)):
    client = get_client(printer_id)
    if not client:
        raise HTTPException(status_code=404, detail="Printer not found")
    success = await client.resume_job()
    return {"success": success}


@router.post("/{printer_id}/cancel")
async def cancel_printer(printer_id: str, user: User = Depends(require_admin)):
    client = get_client(printer_id)
    if not client:
        raise HTTPException(status_code=404, detail="Printer not found")
    success = await client.cancel_job()
    return {"success": success}