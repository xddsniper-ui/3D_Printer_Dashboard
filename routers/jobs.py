"""
Jobs router: GCode upload, queue viewing, job cancellation.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, update, func
from sqlalchemy.sql import and_

from core.config import settings
from core.user import User
from core.job import PrintJob
from core.database import AsyncSessionLocal
from routers.auth import get_current_user
from services.prusalink_client import get_all_printer_configs

router = APIRouter()

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)


class JobOut(BaseModel):
    id: str
    printer_id: str
    filename: str
    status: str
    queue_position: int
    progress_pct: float
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    user_id: str
    estimated_print_time_seconds: Optional[int]
    error_message: Optional[str]


def _user_can_access_printer(user: User, printer_id: str) -> bool:
    if user.role == "admin":
        return True
    if user.allowed_printer_ids is None:
        return True
    return printer_id in user.allowed_printer_ids


@router.post("/upload", response_model=JobOut)
async def upload_gcode(
    printer_id: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """Upload a GCode file and add it to the printer's queue."""
    
    # Permission check
    if not _user_can_access_printer(user, printer_id):
        raise HTTPException(status_code=403, detail="You don't have access to this printer")

    configs = get_all_printer_configs()
    if printer_id not in configs:
        raise HTTPException(status_code=404, detail="Printer not found")

    # Validate file
    if not file.filename.endswith((".gcode", ".bgcode", ".gc")):
        raise HTTPException(status_code=400, detail="Only GCode files (.gcode, .bgcode) are accepted")

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.MAX_GCODE_SIZE_MB:
        raise HTTPException(status_code=413, detail=f"File too large (max {settings.MAX_GCODE_SIZE_MB}MB)")

    # Save to disk
    job_id = str(uuid.uuid4())
    safe_name = f"{job_id}_{file.filename.replace(' ', '_')}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as f:
        f.write(content)

    # Get queue position
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(func.count()).where(
                and_(
                    PrintJob.printer_id == printer_id,
                    PrintJob.status == "queued",
                )
            )
        )
        queue_size = result.scalar() or 0

        job = PrintJob(
            id=job_id,
            printer_id=printer_id,
            user_id=user.id,
            filename=file.filename,
            file_path=file_path,
            file_size_bytes=len(content),
            status="queued",
            queue_position=queue_size,
            created_at=datetime.now(timezone.utc),
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

    return JobOut(
        id=job.id,
        printer_id=job.printer_id,
        filename=job.filename,
        status=job.status,
        queue_position=job.queue_position,
        progress_pct=job.progress_pct,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        user_id=job.user_id,
        estimated_print_time_seconds=job.estimated_print_time_seconds,
        error_message=job.error_message,
    )


@router.get("/", response_model=List[JobOut])
async def list_jobs(
    printer_id: Optional[str] = None,
    status: Optional[str] = None,
    user: User = Depends(get_current_user),
):
    """List jobs. Admins see all; users see only their own."""
    async with AsyncSessionLocal() as db:
        query = select(PrintJob)
        
        if user.role != "admin":
            query = query.where(PrintJob.user_id == user.id)
        
        if printer_id:
            query = query.where(PrintJob.printer_id == printer_id)
        
        if status:
            query = query.where(PrintJob.status == status)
        
        query = query.order_by(PrintJob.created_at.desc()).limit(200)
        result = await db.execute(query)
        jobs = result.scalars().all()

    return [
        JobOut(
            id=j.id,
            printer_id=j.printer_id,
            filename=j.filename,
            status=j.status,
            queue_position=j.queue_position,
            progress_pct=j.progress_pct,
            created_at=j.created_at,
            started_at=j.started_at,
            finished_at=j.finished_at,
            user_id=j.user_id,
            estimated_print_time_seconds=j.estimated_print_time_seconds,
            error_message=j.error_message,
        )
        for j in jobs
    ]


@router.delete("/{job_id}")
async def cancel_job(job_id: str, user: User = Depends(get_current_user)):
    """Cancel a queued job. Users can cancel their own; admins can cancel any."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(PrintJob).where(PrintJob.id == job_id))
        job: Optional[PrintJob] = result.scalar_one_or_none()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if user.role != "admin" and job.user_id != user.id:
            raise HTTPException(status_code=403, detail="Cannot cancel another user's job")

        if job.status not in ("queued",):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel job with status '{job.status}'. Use printer cancel for active prints."
            )

        await db.execute(
            update(PrintJob).where(PrintJob.id == job_id).values(status="cancelled")
        )
        await db.commit()

    return {"success": True}