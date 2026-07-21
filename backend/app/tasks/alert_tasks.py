from decimal import Decimal

from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.invoice import Invoice, ClockStatus
from app.models.vendor import Vendor, VendorStatus
from app.models.user import User, UserRole
from app.core.config import settings


@celery_app.task
def send_daily_ap_nudge_task():
    """
    Daily 9 AM IST — send AP owner nudge per user account.
    Multi-tenant: each user only sees their own company's invoices.
    """
    db = SessionLocal()
    try:
        # Get all active users who have at least one eligible vendor
        users = db.query(User).filter(User.is_active.is_(True)).all()

        total_sent = 0
        for user in users:
            # Use per-user email if set, else fall back to global recipient
            recipient = user.email or settings.ALERT_DEFAULT_RECIPIENT
            if not recipient:
                continue

            # Query ONLY this user's at-risk invoices
            at_risk = (
                db.query(Invoice)
                .join(Vendor)
                .filter(
                    Vendor.user_id == user.id,
                    Invoice.is_paid.is_(False),
                    Invoice.clock_status.in_([ClockStatus.AMBER, ClockStatus.RED]),
                    Vendor.status == VendorStatus.ELIGIBLE,
                )
                .all()
            )

            if not at_risk:
                continue

            total_exposure = sum(
                inv.disallowed_amount or Decimal("0") for inv in at_risk
            )
            invoices_data = [
                {
                    "vendor_name": inv.vendor.name,
                    "invoice_number": inv.invoice_number,
                    "days_remaining": inv.days_remaining,
                    "pending_amount": float(inv.pending_amount),
                }
                for inv in at_risk
            ]

            from app.services.email_service import send_daily_ap_nudge
            send_daily_ap_nudge(recipient, invoices_data, total_exposure)
            total_sent += 1

        return {"sent": total_sent, "users_processed": len(users)}
    finally:
        db.close()


@celery_app.task
def send_weekly_cfo_report_task():
    """
    Weekly Monday 8 AM IST — CFO escalation report with Form 3CD draft.
    Multi-tenant: each user only sees their own company's data.
    """
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.is_active.is_(True)).all()

        total_sent = 0
        for user in users:
            recipient = user.email or settings.ALERT_DEFAULT_RECIPIENT
            if not recipient:
                continue

            invoices = (
                db.query(Invoice)
                .join(Vendor)
                .filter(
                    Vendor.user_id == user.id,
                    Invoice.is_paid.is_(False),
                    Vendor.status == VendorStatus.ELIGIBLE,
                )
                .all()
            )

            if not invoices:
                continue

            red = [i for i in invoices if i.clock_status == ClockStatus.RED]
            amber = [i for i in invoices if i.clock_status == ClockStatus.AMBER]
            total_exposure = sum(float(i.disallowed_amount or 0) for i in invoices)
            total_interest = sum(float(i.accrued_interest or 0) for i in invoices)

            summary = {
                "total_invoices": len(invoices),
                "red_count": len(red),
                "amber_count": len(amber),
                "total_exposure": total_exposure,
                "total_interest": total_interest,
            }

            # Generate Form 3CD attachment for this user's data
            from app.services.export_service import generate_form_3cd_export
            invoices_export_data = [
                {
                    "vendor_name": inv.vendor.name,
                    "udyam_number": inv.vendor.udyam_number,
                    "enterprise_category": inv.vendor.enterprise_category,
                    "invoice_number": inv.invoice_number,
                    "invoice_date": inv.invoice_date,
                    "acceptance_date": inv.acceptance_date,
                    "statutory_deadline": inv.statutory_deadline,
                    "payment_date": inv.payment_date,
                    "days_overdue": inv.days_overdue or 0,
                    "pending_amount": inv.pending_amount,
                    "disallowed_amount": inv.disallowed_amount,
                    "accrued_interest": inv.accrued_interest,
                    "clock_status": inv.clock_status.value if inv.clock_status else "GREEN",
                    "is_capex": inv.is_capex,
                }
                for inv in red + amber
            ]
            attachment = generate_form_3cd_export(invoices_export_data) if invoices_export_data else None

            from app.services.email_service import send_weekly_cfo_report
            send_weekly_cfo_report(recipient, summary, attachment=attachment)
            total_sent += 1

        return {"sent": total_sent, "users_processed": len(users)}
    finally:
        db.close()

