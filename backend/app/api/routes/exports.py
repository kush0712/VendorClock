"""
Modules 6 & 8 — Export API Routes

GET /api/exports/form-3cd     — download Form 3CD Excel (tax audit)
GET /api/exports/msme-1       — download Form MSME-1 Excel (ROC filing)
"""

from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.invoice import Invoice, ClockStatus
from app.models.vendor import Vendor, VendorStatus
from app.services.export_service import generate_form_3cd_export, generate_msme1_export

router = APIRouter(prefix="/api/exports", tags=["Exports"])

EXCEL_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _build_export_invoice_data(invoices: list[Invoice]) -> list[dict]:
    return [
        {
            "vendor_name": inv.vendor.name if inv.vendor else "",
            "udyam_number": inv.vendor.udyam_number if inv.vendor else "",
            "enterprise_category": inv.vendor.enterprise_category if inv.vendor else "",
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
        for inv in invoices
    ]


@router.get("/form-3cd")
def export_form_3cd(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    fy: str = "2025-26",
    status_filter: Optional[str] = None,  # RED, AMBER, or all
):
    """
    Module 6 — Form 3CD audit export.
    One-click, tax-audit-ready Excel: all delayed/at-risk MSE dues.
    Both section citations printed in header.
    Only users with external_auditor, accountant, or admin role can download.
    """
    q = (
        db.query(Invoice)
        .join(Vendor)
        .filter(
            Vendor.user_id == current_user.id,  # user-scoped
            Vendor.status == VendorStatus.ELIGIBLE,
        )
    )

    if status_filter in ("RED", "AMBER"):
        q = q.filter(Invoice.clock_status == ClockStatus(status_filter))
    else:
        # Include all non-green (RED + AMBER + paid overdue)
        q = q.filter(Invoice.clock_status.in_([ClockStatus.RED, ClockStatus.AMBER]))

    invoices = q.order_by(Invoice.days_overdue.desc()).all()
    data = _build_export_invoice_data(invoices)
    xlsx_bytes = generate_form_3cd_export(data, fy=fy)

    filename = f"VendorClock_Form3CD_{fy.replace('-','_')}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type=EXCEL_MIME,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/msme-1")
def export_msme1(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    half_year: str = "April–September 2025",
):
    """
    Module 8 — Form MSME-1 ROC half-yearly export.
    Only Micro/Small enterprise dues > 45 days outstanding.
    Medium enterprises are automatically excluded (confirmed — not a gray area).
    """
    invoices = (
        db.query(Invoice)
        .join(Vendor)
        .filter(
            Vendor.user_id == current_user.id,  # user-scoped
            Vendor.status == VendorStatus.ELIGIBLE,
            Invoice.is_paid.is_(False),
            Invoice.is_capex.is_(False),
            Invoice.days_overdue > 45,
        )
        .all()
    )

    data = _build_export_invoice_data(invoices)
    xlsx_bytes = generate_msme1_export(data, half_year=half_year)

    filename = f"VendorClock_MSME1_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type=EXCEL_MIME,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
