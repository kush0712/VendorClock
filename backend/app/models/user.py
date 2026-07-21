"""
User model — supports RBAC with three roles:
  - treasury_staff  : dashboard read-only
  - accountant      : CSV upload + all reads
  - external_auditor: read-only access to Form 3CD / MSME-1 exports only
"""
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SAEnum
from app.core.database import Base


class UserRole(str, enum.Enum):
    TREASURY_STAFF = "treasury_staff"
    ACCOUNTANT = "accountant"
    EXTERNAL_AUDITOR = "external_auditor"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    company_name = Column(String, nullable=True)  # nullable for backward compat with existing rows
    role = Column(SAEnum(UserRole), nullable=False, default=UserRole.ACCOUNTANT)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
