from sqlalchemy import Column, String, Boolean, DateTime, JSON
from sqlalchemy.sql import func
from core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)          # e.g. "123456"
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user")           # "admin" | "user"
    allowed_printer_ids = Column(JSON, default=None)  # None = all printers; list = restricted
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)