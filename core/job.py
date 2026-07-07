from sqlalchemy import Column, String, Integer, DateTime, Float, JSON
from sqlalchemy.sql import func
from core.database import Base


class PrintJob(Base):
    __tablename__ = "print_jobs"

    id = Column(String, primary_key=True)
    printer_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)       # Path on disk
    file_size_bytes = Column(Integer, default=0)
    
    # Status: queued | uploading | printing | done | failed | cancelled
    status = Column(String, default="queued", index=True)
    queue_position = Column(Integer, default=0)
    
    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    estimated_print_time_seconds = Column(Integer, nullable=True)
    
    # Progress (polled from PrusaLink)
    progress_pct = Column(Float, default=0.0)
    prusalink_job_id = Column(String, nullable=True)  # Job ID returned by PrusaLink
    
    # Metadata from gcode
    meta = Column(JSON, default={})  # filament, layer count, etc.
    error_message = Column(String, nullable=True)