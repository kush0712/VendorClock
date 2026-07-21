"""
RawIngestion model — records every ingest event (CSV upload or email PDF).

Designed for extensibility: email/ERP ingestion paths can plug in as new
IngestionSource values without changing the core data pipeline.
"""
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Enum as SAEnum, Text, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class IngestionStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"  # Some rows succeeded, some failed


class RawIngestion(Base):
    __tablename__ = "raw_ingestions"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(20), nullable=False)  # "CSV_UPLOAD" | "EMAIL_PDF" | "ERP_SYNC"
    status = Column(SAEnum(IngestionStatus), nullable=False, default=IngestionStatus.QUEUED)

    # File info (CSV / Excel upload)
    original_filename = Column(String(500), nullable=True)
    stored_path = Column(Text, nullable=True)   # Path on disk or object store

    # Email info (Phase 2 — Gmail API)
    email_message_id = Column(String(255), nullable=True)
    email_sender = Column(String(255), nullable=True)
    email_received_at = Column(DateTime(timezone=True), nullable=True)

    # Column mapping detected by fuzzy parser
    column_mapping = Column(JSON, nullable=True)  # {"vendor_name": "Supplier Name", ...}

    # Processing results
    total_rows = Column(Integer, nullable=True)
    processed_rows = Column(Integer, nullable=True)
    failed_rows = Column(Integer, nullable=True)
    error_details = Column(JSON, nullable=True)  # List of {row, error} dicts

    # Celery job ID
    celery_task_id = Column(String(255), nullable=True)

    # Uploaded by — FK to users.id (indexed for per-user filtering at scale)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    invoices = relationship("Invoice", back_populates="raw_ingestion")
