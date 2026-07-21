"""
Vendor model — tracks MSME classification status for Section 43B(h)/37(2)(g) compliance.

Classification pipeline per spec:
  1. Vendor PAN/GSTIN submitted
  2. Self-declaration link sent → vendor uploads Udyam certificate
  3. NIC code extracted:
     - 45, 46, 47 → EXCLUDED_TRADER (Wholesale/Retail — Section 15 protection does NOT apply)
     - Medium enterprise → EXCLUDED_MEDIUM (excluded from MSME-1 but may still hit 43B(h))
     - Micro/Small manufacturer or service provider → ELIGIBLE
  4. Annual re-verification required

Phase 2: replace self-declaration with paid bulk API (Gridlines/Decentro/Deepvue)

Multi-tenancy: every Vendor row is owned by a User (user_id FK).
All API queries MUST filter by current_user.id — see routes/vendors.py.
Scalability note: user_id is indexed so per-user lookups remain O(log n)
regardless of total vendor count across all users.
"""
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Enum as SAEnum, Text, Boolean, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class VendorStatus(str, enum.Enum):
    ELIGIBLE = "ELIGIBLE"                   # Micro/Small manufacturer/service — 43B(h) applies
    EXCLUDED_TRADER = "EXCLUDED_TRADER"     # NIC 45/46/47 Wholesale/Retail — Section 15 does NOT apply
    EXCLUDED_MEDIUM = "EXCLUDED_MEDIUM"     # Medium enterprise — exempt from MSME-1, but 43B(h) may apply
    PENDING_DECLARATION = "PENDING_DECLARATION"  # Self-declaration email sent, awaiting response
    NOT_REGISTERED = "NOT_REGISTERED"      # No Udyam registration found


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True)

    # ── Multi-tenancy: every vendor belongs to exactly one user (company) ──────
    # Indexed for fast per-user lookups even with millions of vendor rows.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    name = Column(String(500), nullable=False, index=True)

    # Identity
    pan = Column(String(10), index=True, nullable=True)
    gstin = Column(String(15), index=True, nullable=True)

    # Udyam registration details
    udyam_number = Column(String(20), index=True, nullable=True)
    nic_code = Column(String(10), nullable=True)            # NIC activity code from Udyam cert
    enterprise_category = Column(String(20), nullable=True) # Micro / Small / Medium

    # Classification result
    status = Column(SAEnum(VendorStatus), nullable=False, default=VendorStatus.PENDING_DECLARATION)

    # Self-declaration
    declaration_email_sent_at = Column(DateTime(timezone=True), nullable=True)
    declaration_link_token = Column(String(64), unique=True, nullable=True)
    certificate_url = Column(Text, nullable=True)  # Stored path/URL of uploaded Udyam cert
    certificate_uploaded_at = Column(DateTime(timezone=True), nullable=True)

    # Verification
    last_verified_at = Column(DateTime(timezone=True), nullable=True)
    next_verification_due = Column(DateTime(timezone=True), nullable=True)  # Annual

    # Contact (for self-declaration email)
    contact_email = Column(String(255), nullable=True)
    contact_name = Column(String(255), nullable=True)

    # Flags
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    invoices = relationship("Invoice", back_populates="vendor")
    owner = relationship("User", foreign_keys=[user_id])

