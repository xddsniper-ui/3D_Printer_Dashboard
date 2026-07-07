"""
Queue processor: runs in the background and dispatches queued jobs
to printers as they become available.

PrusaLink doesn't have a native queue, so we manage it here:
- Jobs are stored in DB with status=queued
- This loop polls printers every N seconds
- When a printer goes idle and has queued jobs → dispatch next job
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.sql import and_

from core.config import settings
from core.database import AsyncSessionLocal
from core.job import PrintJob
from services.prusalink_client import get_client

logger = logging.getLogger("queue_processor")


class QueueProcessor:
    def __init__(self):
        self._running = False

    def stop(self):
        self._running = False

    async def run(self):
        self._running = True
        logger.info("Queue processor started")
        while self._running:
            try:
                await self._process_all_printers()
            except Exception as e:
                logger.error(f"Queue processor error: {e}")
            await asyncio.sleep(settings.QUEUE_POLL_INTERVAL_SECONDS)

    async def _process_all_printers(self):
        """For each printer, if idle and has queued jobs → dispatch next."""
        async with AsyncSessionLocal() as db:
            # Get all unique printer IDs that have queued jobs
            result = await db.execute(
                select(PrintJob.printer_id)
                .where(PrintJob.status == "queued")
                .distinct()
            )
            printer_ids_with_queue = [row[0] for row in result.fetchall()]

        for printer_id in printer_ids_with_queue:
            await self._try_dispatch(printer_id)

    async def _try_dispatch(self, printer_id: str):
        client = get_client(printer_id)
        if not client:
            return

        # Check if printer is idle
        is_idle = await client.is_idle()
        if not is_idle:
            return

        # Check if printer is already running a job in our DB
        async with AsyncSessionLocal() as db:
            running = await db.execute(
                select(PrintJob).where(
                    and_(
                        PrintJob.printer_id == printer_id,
                        PrintJob.status == "printing",
                    )
                )
            )
            if running.scalar_one_or_none():
                return  # Already dispatched a job to this printer

            # Get next queued job (by queue position then created_at)
            result = await db.execute(
                select(PrintJob)
                .where(
                    and_(
                        PrintJob.printer_id == printer_id,
                        PrintJob.status == "queued",
                    )
                )
                .order_by(PrintJob.queue_position, PrintJob.created_at)
                .limit(1)
            )
            job: Optional[PrintJob] = result.scalar_one_or_none()

            if not job:
                return

            # Mark as uploading
            job.status = "uploading"
            job.started_at = datetime.now(timezone.utc)
            await db.commit()
            job_id = job.id
            filename = job.filename
            file_path = job.file_path

        logger.info(f"Dispatching job {job_id} ({filename}) → {printer_id}")

        # Read file and send to PrusaLink
        try:
            with open(file_path, "rb") as f:
                gcode_bytes = f.read()

            result = await client.upload_and_print(filename, gcode_bytes)

            async with AsyncSessionLocal() as db:
                if result.get("success"):
                    await db.execute(
                        update(PrintJob)
                        .where(PrintJob.id == job_id)
                        .values(status="printing", started_at=datetime.now(timezone.utc))
                    )
                    logger.info(f"Job {job_id} dispatched successfully to {printer_id}")
                else:
                    error = result.get("error", "Unknown error")
                    await db.execute(
                        update(PrintJob)
                        .where(PrintJob.id == job_id)
                        .values(status="failed", error_message=error)
                    )
                    logger.error(f"Job {job_id} failed to dispatch: {error}")
                await db.commit()

        except FileNotFoundError:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(PrintJob)
                    .where(PrintJob.id == job_id)
                    .values(status="failed", error_message="GCode file not found on disk")
                )
                await db.commit()