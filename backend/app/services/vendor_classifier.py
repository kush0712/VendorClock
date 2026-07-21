"""
Module 2 — Vendor MSME-Status & Exclusions Engine

Classification pipeline:
  [Vendor PAN/GSTIN]
        │
        ▼
  [Udyam self-declaration link sent] ──(no response/not registered)──▶ [NOT_REGISTERED]
        │
        ▼ (certificate uploaded)
  [NIC Code Check: 45, 46, 47?] ──(yes — Wholesale/Retail Trader)──▶ [EXCLUDED_TRADER]
        │                           Section 15 does NOT apply to these vendors.
        │                           43B(h)/37(2)(g) does NOT apply to their invoices.
        ▼ (no — Manufacturer/Service Provider)
  [Enterprise category: Medium?] ──(yes)──▶ [EXCLUDED_MEDIUM]
        │                                    Excluded from MSME-1 ROC filing.
        ▼ (Micro or Small)
  [ELIGIBLE] → Added to Active Compliance Clock Engine

Phase 2: replace self-declaration with paid bulk Udyam API (Gridlines/Decentro/Deepvue).
         Nothing else in the architecture changes — swap verify_vendor() implementation only.
"""

import secrets
import re
from typing import Optional
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.models.vendor import Vendor, VendorStatus
from app.core.config import settings

# NIC codes for Wholesale/Retail Traders — excluded from Section 15 protection
# Udyam-eligible for PSL only. 43B(h)/37(2)(g) does NOT apply.
EXCLUDED_TRADER_NIC_PREFIXES = {"45", "46", "47"}

# Udyam certificate declaration link expiry
DECLARATION_LINK_EXPIRY_DAYS = 30

# Annual re-verification period
ANNUAL_REVERIFICATION_DAYS = 365


def is_trader_nic(nic_code: Optional[str]) -> bool:
    """
    Return True if the NIC code falls under Wholesale/Retail Trade (45, 46, 47).
    These vendors are Udyam-registered but Section 15 of MSMED Act does NOT protect them.
    Therefore Section 43B(h) / Section 37(2)(g) does NOT apply to their invoices.
    """
    if not nic_code:
        return False
    code = nic_code.strip()
    # Check 2-digit prefix
    prefix = code[:2]
    return prefix in EXCLUDED_TRADER_NIC_PREFIXES


def classify_vendor(
    enterprise_category: Optional[str],
    nic_code: Optional[str],
    udyam_number: Optional[str],
) -> VendorStatus:
    """
    Apply classification rules and return the vendor's MSME status.
    Called after a Udyam certificate is uploaded or verified.
    """
    if not udyam_number:
        return VendorStatus.NOT_REGISTERED

    # Trader exclusion — hard requirement per spec
    if is_trader_nic(nic_code):
        return VendorStatus.EXCLUDED_TRADER

    # Medium enterprise
    cat = (enterprise_category or "").strip().lower()
    if cat == "medium":
        return VendorStatus.EXCLUDED_MEDIUM

    # Micro or Small — eligible
    if cat in ("micro", "small"):
        return VendorStatus.ELIGIBLE

    # Unknown category — treat as pending until clarified
    return VendorStatus.PENDING_DECLARATION


def generate_declaration_token() -> str:
    """Generate a secure random token for the self-declaration link."""
    return secrets.token_urlsafe(32)


def get_declaration_link(token: str, base_url: str = settings.FRONTEND_URL) -> str:
    """Build the vendor self-declaration URL."""
    return f"{base_url}/vendor-status/{token}"


def process_uploaded_certificate(
    vendor: Vendor,
    udyam_number: str,
    nic_code: Optional[str],
    enterprise_category: Optional[str],
    certificate_url: str,
    db: Session,
) -> Vendor:
    """
    Called when a vendor submits their Udyam certificate.
    Updates classification and sets next re-verification date.
    """
    vendor.udyam_number = udyam_number.strip().upper()
    vendor.nic_code = nic_code
    vendor.enterprise_category = enterprise_category
    vendor.certificate_url = certificate_url
    vendor.certificate_uploaded_at = datetime.now(timezone.utc)
    vendor.last_verified_at = datetime.now(timezone.utc)
    vendor.next_verification_due = datetime.now(timezone.utc) + timedelta(days=ANNUAL_REVERIFICATION_DAYS)
    vendor.status = classify_vendor(enterprise_category, nic_code, udyam_number)

    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return vendor


def get_or_create_vendor(
    db: Session,
    name: str,
    user_id: int,
    pan: Optional[str] = None,
    gstin: Optional[str] = None,
    contact_email: Optional[str] = None,
) -> tuple[Vendor, bool]:
    """
    Find existing vendor by PAN or GSTIN **within the same user's account**, or create a new one.

    Multi-tenancy guarantee: lookup is always scoped to user_id.
    Two different users who happen to share the same vendor PAN/GSTIN each get their own
    separate Vendor row — their data never mingles.

    Returns (vendor, created: bool).
    """
    # Normalize
    pan = pan.strip().upper() if pan else None
    gstin = gstin.strip().upper() if gstin else None

    # Look up by PAN first, then GSTIN — always scoped to this user
    vendor = None
    if pan:
        vendor = db.query(Vendor).filter(
            Vendor.pan == pan,
            Vendor.user_id == user_id,
        ).first()
    if not vendor and gstin:
        vendor = db.query(Vendor).filter(
            Vendor.gstin == gstin,
            Vendor.user_id == user_id,
        ).first()
    # Fallback: match by name within the same user account
    if not vendor:
        vendor = db.query(Vendor).filter(
            Vendor.name == name,
            Vendor.user_id == user_id,
        ).first()

    if vendor:
        return vendor, False

    # Auto-classify based on name suffix for testing/demo purposes
    test_cat = None
    test_nic = None
    name_lower = name.lower()
    if "(micro)" in name_lower:
        test_cat = "micro"
    elif "(small)" in name_lower:
        test_cat = "small"
    elif "(medium)" in name_lower:
        test_cat = "medium"
    elif "(wholesale)" in name_lower:
        test_nic = "46" # wholesale trader NIC
    elif "(unregistered)" in name_lower:
        pass # stays pending/unregistered

    udyam_val = "UDYAM-DEMO-1234" if (test_cat or test_nic) else None

    # Create new with PENDING_DECLARATION status (or auto-classified), tagged to this user
    token = generate_declaration_token()
    vendor = Vendor(
        user_id=user_id,
        name=name,
        pan=pan,
        gstin=gstin,
        contact_email=contact_email,
        udyam_number=udyam_val,
        enterprise_category=test_cat,
        nic_code=test_nic,
        declaration_link_token=token,
    )
    
    if udyam_val:
        vendor.status = classify_vendor(vendor.enterprise_category, vendor.nic_code, vendor.udyam_number)
    else:
        vendor.status = VendorStatus.PENDING_DECLARATION

    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return vendor, True

