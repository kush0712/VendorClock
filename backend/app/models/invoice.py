"""
Invoice model — core of the 15/45-day compliance clock engine.

Clock logic per Section 43B(h) / Section 37(2)(g), Income Tax Act 2025:
  - Written agreement on file → deadline = acceptance_date + min(agreed_payment_days, 45)
  - No agreement → deadline = delivery_date + 15 (deemed acceptance: no written objection in 15 days)
  - Dispute raised → clock pauses at dispute_raised_at (⚠ CA/lawyer confirmation pending)
  - Dual citation: "Section 43B(h) / Section 37(2)(g)" on every export/label

Clock status:
  GREEN  → > 7 days remaining
  AMBER  → 1–7 days remaining
  RED    → overdue (interest compounding, disallowance active)
"""
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Enum as SAEnum, Text, Boolean, Float, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from app.core.database import Base


class ClockStatus(str, enum.Enum):
    GREEN = "GREEN"    # > 7 days remaining — safe
    AMBER = "AMBER"   # 1–7 days remaining — approaching
    RED = "RED"       # Overdue — interest compounding, disallowance active
    PAID = "PAID"     # Cleared before deadline
    EXCLUDED = "EXCLUDED"  # Vendor not ELIGIBLE (trader/medium/pending)


class IngestionSource(str, enum.Enum):
    CSV_UPLOAD = "CSV_UPLOAD"
    EMAIL_PDF = "EMAIL_PDF"   # Phase 2 — Gmail API
    ERP_SYNC = "ERP_SYNC"     # Phase 2 — Tally/Zoho/SAP


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False, index=True)

    # Invoice identity
    invoice_number = Column(String(100), nullable=False, index=True)
    invoice_date = Column(DateTime(timezone=True), nullable=False)

    # Delivery & acceptance
    delivery_date = Column(DateTime(timezone=True), nullable=True)  # Date goods/services received
    acceptance_date = Column(DateTime(timezone=True), nullable=True)  # Explicit or deemed

    # Contract branch (written-agreement test — NOT goods vs. services split)
    has_written_agreement = Column(Boolean, nullable=False, default=False)
    agreed_payment_days = Column(Integer, nullable=True)  # Capped at 45 in clock engine

    # Financial
    amount = Column(Numeric(15, 2), nullable=False)        # Total invoice amount
    pending_amount = Column(Numeric(15, 2), nullable=False)  # Outstanding unpaid
    gst_amount = Column(Numeric(15, 2), nullable=True)     # GST portion (separate, pending CA decision)
    currency = Column(String(3), default="INR")

    # Payment
    payment_date = Column(DateTime(timezone=True), nullable=True)
    is_paid = Column(Boolean, default=False)

    # Capex flag — excluded from disallowance engine per spec
    is_capex = Column(Boolean, default=False)

    # Dispute handling — clock pauses on objection (⚠ CA/lawyer confirmation pending for reset logic)
    dispute_raised_at = Column(DateTime(timezone=True), nullable=True)
    dispute_resolved_at = Column(DateTime(timezone=True), nullable=True)
    dispute_notes = Column(Text, nullable=True)

    # Clock computation (populated by clock engine)
    statutory_deadline = Column(DateTime(timezone=True), nullable=True)
    days_remaining = Column(Integer, nullable=True)   # Negative = overdue
    days_overdue = Column(Integer, nullable=True)
    clock_status = Column(SAEnum(ClockStatus), nullable=False, default=ClockStatus.GREEN)

    # Financial exposure (populated by clock engine + cash-priority optimizer)
    disallowed_amount = Column(Numeric(15, 2), nullable=True)   # Amount added back to taxable income
    accrued_interest = Column(Numeric(15, 2), nullable=True)    # Non-deductible compound interest
    tax_cost = Column(Numeric(15, 2), nullable=True)            # disallowed_amount × effective_tax_rate
    priority_score = Column(Float, nullable=True)               # Cash-priority optimizer score

    # Source tracking
    ingestion_source = Column(SAEnum(IngestionSource), nullable=False, default=IngestionSource.CSV_UPLOAD)
    raw_ingestion_id = Column(Integer, ForeignKey("raw_ingestions.id"), nullable=True)

    # Notes
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    vendor = relationship("Vendor", back_populates="invoices")
    raw_ingestion = relationship("RawIngestion", back_populates="invoices")
