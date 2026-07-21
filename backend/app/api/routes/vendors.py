"""
Module 2 — Vendor API Routes

GET  /api/vendors                  — list vendors with MSME status
GET  /api/vendors/{id}             — vendor detail
POST /api/vendors/{id}/declaration — upload Udyam certificate (internal)
GET  /api/vendors/declaration/{token} — public: fetch vendor for declaration form
POST /api/vendors/declaration/{token}/submit — public: submit Udyam cert
"""

import os
import uuid
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.core.config import settings
from app.models.vendor import Vendor, VendorStatus
from app.models.user import UserRole
from app.services.vendor_classifier import process_uploaded_certificate

router = APIRouter(prefix="/api/vendors", tags=["Vendors"])


@router.get("/")
def list_vendors(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """List vendors belonging to the current user's account."""
    q = db.query(Vendor).filter(Vendor.user_id == current_user.id)
    if status_filter:
        try:
            q = q.filter(Vendor.status == VendorStatus(status_filter))
        except ValueError:
            pass
    if search:
        q = q.filter(
            Vendor.name.ilike(f"%{search}%") |
            Vendor.pan.ilike(f"%{search}%") |
            Vendor.gstin.ilike(f"%{search}%")
        )
    total = q.count()
    vendors = q.order_by(Vendor.name).offset(offset).limit(limit).all()

    return {
        "items": [
            {
                "id": v.id,
                "name": v.name,
                "pan": v.pan,
                "gstin": v.gstin,
                "udyam_number": v.udyam_number,
                "nic_code": v.nic_code,
                "enterprise_category": v.enterprise_category,
                "status": v.status.value,
                "certificate_uploaded_at": v.certificate_uploaded_at.isoformat() if v.certificate_uploaded_at else None,
                "last_verified_at": v.last_verified_at.isoformat() if v.last_verified_at else None,
                "next_verification_due": v.next_verification_due.isoformat() if v.next_verification_due else None,
                "declaration_email_sent_at": v.declaration_email_sent_at.isoformat() if v.declaration_email_sent_at else None,
            }
            for v in vendors
        ],
        "total": total,
        "status_summary": {
            "eligible": db.query(Vendor).filter(Vendor.user_id == current_user.id, Vendor.status == VendorStatus.ELIGIBLE).count(),
            "pending": db.query(Vendor).filter(Vendor.user_id == current_user.id, Vendor.status == VendorStatus.PENDING_DECLARATION).count(),
            "excluded_trader": db.query(Vendor).filter(Vendor.user_id == current_user.id, Vendor.status == VendorStatus.EXCLUDED_TRADER).count(),
            "excluded_medium": db.query(Vendor).filter(Vendor.user_id == current_user.id, Vendor.status == VendorStatus.EXCLUDED_MEDIUM).count(),
        },
    }


@router.get("/{vendor_id}")
def get_vendor(
    vendor_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get vendor detail with invoice summary (scoped to current user's account)."""
    vendor = db.query(Vendor).filter(
        Vendor.id == vendor_id,
        Vendor.user_id == current_user.id,  # ownership check — prevents cross-user access
    ).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    from app.models.invoice import Invoice, ClockStatus
    invoices = db.query(Invoice).filter(Invoice.vendor_id == vendor_id).all()
    red_count = sum(1 for i in invoices if i.clock_status == ClockStatus.RED)
    amber_count = sum(1 for i in invoices if i.clock_status == ClockStatus.AMBER)

    return {
        "id": vendor.id,
        "name": vendor.name,
        "pan": vendor.pan,
        "gstin": vendor.gstin,
        "udyam_number": vendor.udyam_number,
        "nic_code": vendor.nic_code,
        "enterprise_category": vendor.enterprise_category,
        "status": vendor.status.value,
        "contact_email": vendor.contact_email,
        "contact_name": vendor.contact_name,
        "certificate_url": vendor.certificate_url,
        "certificate_uploaded_at": vendor.certificate_uploaded_at.isoformat() if vendor.certificate_uploaded_at else None,
        "last_verified_at": vendor.last_verified_at.isoformat() if vendor.last_verified_at else None,
        "next_verification_due": vendor.next_verification_due.isoformat() if vendor.next_verification_due else None,
        "invoice_count": len(invoices),
        "red_invoices": red_count,
        "amber_invoices": amber_count,
        "citation": settings.SECTION_CITATION_COMBINED,
    }


@router.post("/{vendor_id}/declaration")
async def upload_certificate_internal(
    vendor_id: int,
    certificate: UploadFile = File(...),
    udyam_number: str = Form(...),
    nic_code: str = Form(...),
    enterprise_category: str = Form(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.ACCOUNTANT, UserRole.ADMIN)),
):
    """Internal path to manually upload/update a vendor's Udyam certificate (ownership checked)."""
    vendor = db.query(Vendor).filter(
        Vendor.id == vendor_id,
        Vendor.user_id == current_user.id,  # ownership check
    ).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    cert_content = await certificate.read()
    cert_filename = f"udyam_{vendor_id}_{uuid.uuid4().hex}.pdf"
    cert_path = os.path.join(settings.UPLOAD_DIR, cert_filename)
    with open(cert_path, "wb") as f:
        f.write(cert_content)

    vendor = process_uploaded_certificate(
        vendor=vendor,
        udyam_number=udyam_number,
        nic_code=nic_code,
        enterprise_category=enterprise_category,
        certificate_url=cert_path,
        db=db,
    )

    return {
        "vendor_id": vendor.id,
        "status": vendor.status.value,
        "message": f"Vendor classified as {vendor.status.value}",
        "citation": settings.SECTION_CITATION_COMBINED,
    }


# ─── Public declaration endpoints (no auth — vendor-facing) ───────────────────

@router.get("/declaration/{token}")
def get_vendor_for_declaration(token: str, db: Session = Depends(get_db)):
    """Public: fetch vendor info for the self-declaration form (token-gated)."""
    vendor = db.query(Vendor).filter(Vendor.declaration_link_token == token).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Invalid or expired declaration link.")
    return {
        "vendor_name": vendor.name,
        "status": vendor.status.value,
        "certificate_uploaded": vendor.certificate_url is not None,
        "citation": settings.SECTION_CITATION_COMBINED,
    }


@router.post("/declaration/{token}/submit")
async def submit_declaration(
    token: str,
    certificate: UploadFile = File(...),
    udyam_number: str = Form(...),
    nic_code: str = Form(...),
    enterprise_category: str = Form(...),
    db: Session = Depends(get_db),
):
    """Public: vendor submits their Udyam certificate via self-declaration link."""
    vendor = db.query(Vendor).filter(Vendor.declaration_link_token == token).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Invalid or expired declaration link.")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    cert_content = await certificate.read()
    cert_filename = f"udyam_public_{vendor.id}_{uuid.uuid4().hex}.pdf"
    cert_path = os.path.join(settings.UPLOAD_DIR, cert_filename)
    with open(cert_path, "wb") as f:
        f.write(cert_content)

    vendor = process_uploaded_certificate(
        vendor=vendor,
        udyam_number=udyam_number,
        nic_code=nic_code,
        enterprise_category=enterprise_category,
        certificate_url=cert_path,
        db=db,
    )

    return {
        "message": "Thank you! Your Udyam certificate has been received and verified.",
        "status": vendor.status.value,
        "udyam_number": vendor.udyam_number,
    }


# ─── Internal: trigger declaration email from UI ───────────────────────────────

@router.post("/{vendor_id}/send-declaration")
def send_declaration_email_endpoint(
    vendor_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.ACCOUNTANT, UserRole.ADMIN)),
):
    """
    Trigger a Udyam self-declaration email for a vendor.
    Vendor must have a contact_email set and a declaration_link_token.
    If no token exists yet, one is generated.
    """
    vendor = db.query(Vendor).filter(
        Vendor.id == vendor_id,
        Vendor.user_id == current_user.id,
    ).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    if not vendor.contact_email:
        raise HTTPException(
            status_code=400,
            detail="Vendor has no contact email on file. Update the vendor record first.",
        )

    # Ensure token exists
    if not vendor.declaration_link_token:
        from app.services.vendor_classifier import generate_declaration_token
        vendor.declaration_link_token = generate_declaration_token()
        db.add(vendor)
        db.commit()
        db.refresh(vendor)

    # Queue the email via Celery (or run sync if Redis unavailable)
    try:
        from app.tasks.ingestion_tasks import send_declaration_email
        send_declaration_email.delay(vendor.id)
        mode = "queued"
    except Exception:
        # Celery unavailable — run synchronously
        from app.services.vendor_classifier import get_declaration_link
        from app.services.email_service import send_email
        from app.core.config import settings
        from datetime import datetime, timezone

        link = get_declaration_link(vendor.declaration_link_token)
        html = f"""
        <html><body style="font-family:Inter,sans-serif;padding:24px;">
        <h2>Udyam Registration Verification — VendorClock</h2>
        <p>Dear {vendor.contact_name or vendor.name},</p>
        <p>Your buyer is using VendorClock to comply with <strong>{settings.SECTION_CITATION_COMBINED}</strong>.</p>
        <p>Please upload your Udyam certificate at the link below:</p>
        <p><a href="{link}" style="background:#1E293B;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;">Upload Udyam Certificate</a></p>
        <p style="font-size:12px;color:#6B7280;">This is a one-time request. Your certificate is stored securely and verified annually.</p>
        </body></html>
        """
        send_email(vendor.contact_email, "Action Required: Upload your Udyam Certificate", html)
        vendor.declaration_email_sent_at = datetime.now(timezone.utc)
        db.commit()
        mode = "sent_sync"

    return {
        "success": True,
        "vendor_id": vendor.id,
        "vendor_name": vendor.name,
        "sent_to": vendor.contact_email,
        "mode": mode,
        "message": f"Declaration email sent to {vendor.contact_email}",
        "citation": settings.SECTION_CITATION_COMBINED,
    }
