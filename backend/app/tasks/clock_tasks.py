from decimal import Decimal
from datetime import datetime, timezone, timedelta

from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.invoice import Invoice, ClockStatus
from app.models.vendor import Vendor, VendorStatus


@celery_app.task
def refresh_all_clocks():
    """Hourly task: recompute clock status for all unpaid ELIGIBLE invoices."""
    from app.tasks.ingestion_tasks import _refresh_single_invoice_clock
    db = SessionLocal()
    try:
        invoices = (
            db.query(Invoice)
            .join(Vendor)
            .filter(
                Invoice.is_paid.is_(False),
                Vendor.status == VendorStatus.ELIGIBLE,
            )
            .all()
        )
        for invoice in invoices:
            _refresh_single_invoice_clock(invoice, db)
        db.commit()
        return {"refreshed": len(invoices)}
    finally:
        db.close()


@celery_app.task
def check_vendor_reverification():
    """
    Daily task: find vendors whose annual re-verification is due.
    Sends a new self-declaration email if next_verification_due has passed.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        due_vendors = (
            db.query(Vendor)
            .filter(
                Vendor.status == VendorStatus.ELIGIBLE,
                Vendor.next_verification_due <= now,
            )
            .all()
        )
        for vendor in due_vendors:
            # Reset to PENDING and send new declaration email
            vendor.status = VendorStatus.PENDING_DECLARATION
            from app.services.vendor_classifier import generate_declaration_token
            vendor.declaration_link_token = generate_declaration_token()
            db.add(vendor)
            from app.tasks.ingestion_tasks import send_declaration_email
            send_declaration_email.delay(vendor.id)

        db.commit()
        return {"reverification_sent": len(due_vendors)}
    finally:
        db.close()
