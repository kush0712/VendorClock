"""
Module 3/4 — Invoice & Dashboard API Routes

GET /api/invoices                     — list invoices with clock status
GET /api/invoices/{id}                — invoice detail
PATCH /api/invoices/{id}              — update invoice (mark paid, add dispute, etc.)
GET /api/dashboard/summary            — CFO exposure summary
GET /api/dashboard/priority-queue     — ranked cash-priority queue
GET /api/dashboard/by-vendor          — per-vendor exposure breakdown
"""

from typing import Optional
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.core.config import settings
from app.models.invoice import Invoice, ClockStatus
from app.models.vendor import Vendor, VendorStatus
from app.models.user import UserRole
from app.services.cash_priority import build_priority_queue, compute_priority_score, EFFECTIVE_TAX_RATE
from app.services.clock_engine import compute_disallowed_amount

invoice_router = APIRouter(prefix="/api/invoices", tags=["Invoices"])
dashboard_router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


class InvoiceUpdateRequest(BaseModel):
    is_paid: Optional[bool] = None
    payment_date: Optional[datetime] = None
    dispute_raised_at: Optional[datetime] = None
    dispute_resolved_at: Optional[datetime] = None
    dispute_notes: Optional[str] = None
    has_written_agreement: Optional[bool] = None
    agreed_payment_days: Optional[int] = None
    is_capex: Optional[bool] = None
    notes: Optional[str] = None


@invoice_router.get("/")
def list_invoices(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    clock_status: Optional[str] = None,
    vendor_id: Optional[int] = None,
    is_paid: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
):
    """List invoices for the current user's account (scoped by vendor ownership)."""
    q = db.query(Invoice).join(Vendor).filter(Vendor.user_id == current_user.id)

    if clock_status:
        try:
            q = q.filter(Invoice.clock_status == ClockStatus(clock_status))
        except ValueError:
            pass
    if vendor_id:
        q = q.filter(Invoice.vendor_id == vendor_id)
    if is_paid is not None:
        q = q.filter(Invoice.is_paid == is_paid)

    total = q.count()
    invoices = (
        q.order_by(Invoice.statutory_deadline.asc().nullsfirst())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "items": [_serialize_invoice(i) for i in invoices],
        "total": total,
        "citation": settings.SECTION_CITATION_COMBINED,
    }


@invoice_router.get("/{invoice_id}")
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get invoice detail — returns 404 if invoice doesn't belong to current user."""
    inv = (
        db.query(Invoice)
        .join(Vendor)
        .filter(Invoice.id == invoice_id, Vendor.user_id == current_user.id)
        .first()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _serialize_invoice(inv, detail=True)


@invoice_router.patch("/{invoice_id}")
def update_invoice(
    invoice_id: int,
    body: InvoiceUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.ACCOUNTANT, UserRole.ADMIN)),
):
    """Update invoice fields (mark paid, add dispute, change agreement terms)."""
    inv = (
        db.query(Invoice)
        .join(Vendor)
        .filter(Invoice.id == invoice_id, Vendor.user_id == current_user.id)
        .first()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if body.is_paid is not None:
        inv.is_paid = body.is_paid
    if body.payment_date is not None:
        inv.payment_date = body.payment_date
    if body.dispute_raised_at is not None:
        inv.dispute_raised_at = body.dispute_raised_at
    if body.dispute_resolved_at is not None:
        inv.dispute_resolved_at = body.dispute_resolved_at
    if body.dispute_notes is not None:
        inv.dispute_notes = body.dispute_notes
    if body.has_written_agreement is not None:
        inv.has_written_agreement = body.has_written_agreement
    if body.agreed_payment_days is not None:
        inv.agreed_payment_days = body.agreed_payment_days
    if body.is_capex is not None:
        inv.is_capex = body.is_capex
    if body.notes is not None:
        inv.notes = body.notes

    db.commit()

    # Recompute clock after update
    from app.tasks.ingestion_tasks import _refresh_single_invoice_clock
    _refresh_single_invoice_clock(inv, db)
    db.commit()
    db.refresh(inv)

    return _serialize_invoice(inv, detail=True)


# ─── Dashboard ────────────────────────────────────────────────────────────────

@dashboard_router.get("/summary")
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    fy: str = "2025-26",
):
    """CFO exposure summary — total ₹ at risk, tax cost, interest accrued (user-scoped)."""
    eligible_invoices = (
        db.query(Invoice)
        .join(Vendor)
        .filter(
            Vendor.user_id == current_user.id,
            Invoice.is_paid.is_(False),
            Vendor.status == VendorStatus.ELIGIBLE,
            Invoice.is_capex.is_(False),
        )
        .all()
    )

    red = [i for i in eligible_invoices if i.clock_status == ClockStatus.RED]
    amber = [i for i in eligible_invoices if i.clock_status == ClockStatus.AMBER]
    green = [i for i in eligible_invoices if i.clock_status == ClockStatus.GREEN]

    total_exposure = sum(float(i.disallowed_amount or 0) for i in eligible_invoices)
    total_interest = sum(float(i.accrued_interest or 0) for i in eligible_invoices)
    total_tax_cost = sum(float(i.tax_cost or 0) for i in eligible_invoices)
    red_exposure = sum(float(i.disallowed_amount or 0) for i in red)

    # Per-user vendor counts
    total_vendors = db.query(Vendor).filter(Vendor.user_id == current_user.id).count()
    eligible_vendors = db.query(Vendor).filter(Vendor.user_id == current_user.id, Vendor.status == VendorStatus.ELIGIBLE).count()
    pending_vendors = db.query(Vendor).filter(Vendor.user_id == current_user.id, Vendor.status == VendorStatus.PENDING_DECLARATION).count()

    return {
        "fy": fy,
        "citation": settings.SECTION_CITATION_COMBINED,
        "ca_note": (
            "⚠ GST base inclusion and dispute reset logic pending CA confirmation. "
            "Numbers should be validated before filing."
        ),
        "invoices": {
            "total": len(eligible_invoices),
            "red": len(red),
            "amber": len(amber),
            "green": len(green),
        },
        "exposure": {
            "total_disallowed": round(total_exposure, 2),
            "red_disallowed": round(red_exposure, 2),
            "total_tax_cost": round(total_tax_cost, 2),
            "total_interest": round(total_interest, 2),
            "total_at_risk": round(total_exposure + total_interest, 2),
        },
        "vendors": {
            "total": total_vendors,
            "eligible": eligible_vendors,
            "pending_declaration": pending_vendors,
        },
        "effective_tax_rate_used": float(EFFECTIVE_TAX_RATE),
        "rbi_bank_rate_percent": settings.RBI_BANK_RATE_PERCENT,
    }


@dashboard_router.get("/priority-queue")
def get_priority_queue(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    limit: int = 100,
):
    """
    Cash-Priority Optimizer — ranked list of unpaid invoices by tax+interest saved per ₹.
    Score = (disallowed_amount × effective_tax_rate + accrued_interest) / pending_amount
    Higher score = pay this invoice first. Scoped to current user's account.
    """
    invoices = (
        db.query(Invoice)
        .join(Vendor)
        .filter(
            Vendor.user_id == current_user.id,
            Invoice.is_paid.is_(False),
            Vendor.status == VendorStatus.ELIGIBLE,
        )
        .limit(limit)
        .all()
    )

    invoices_data = [
        {
            "invoice_id": i.id,
            "vendor_id": i.vendor_id,
            "vendor_name": i.vendor.name if i.vendor else "",
            "invoice_number": i.invoice_number,
            "pending_amount": float(i.pending_amount),
            "gst_amount": float(i.gst_amount) if i.gst_amount else None,
            "days_remaining": i.days_remaining or 0,
            "days_overdue": i.days_overdue or 0,
            "clock_status": i.clock_status,
            "statutory_deadline": i.statutory_deadline.isoformat() if i.statutory_deadline else None,
            "is_capex": i.is_capex,
            "is_in_dispute": bool(i.dispute_raised_at and not i.dispute_resolved_at),
        }
        for i in invoices
    ]

    queue = build_priority_queue(invoices_data)
    return {
        "items": [
            {
                "invoice_id": e.invoice_id,
                "vendor_name": e.vendor_name,
                "invoice_number": e.invoice_number,
                "pending_amount": float(e.pending_amount),
                "days_remaining": e.days_remaining,
                "days_overdue": e.days_overdue,
                "clock_status": e.clock_status.value,
                "statutory_deadline": e.statutory_deadline,
                "disallowed_amount": float(e.disallowed_amount),
                "accrued_interest": float(e.accrued_interest),
                "tax_cost": float(e.tax_cost),
                "priority_score": e.priority_score,
                "is_capex": e.is_capex,
                "is_in_dispute": e.is_in_dispute,
                "citation": e.citation,
            }
            for e in queue
        ],
        "total": len(queue),
        "citation": settings.SECTION_CITATION_COMBINED,
        "gst_base_note": (
            "⚠ GST inclusion/exclusion from taxable base pending CA confirmation. "
            f"Currently: GST {'included' if settings.GST_INCLUDED_IN_TAXABLE_BASE else 'excluded'} from disallowed amount."
        ),
    }


@dashboard_router.get("/by-vendor")
def get_exposure_by_vendor(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Per-vendor exposure breakdown for the CFO dashboard (user-scoped)."""
    eligible_vendors = (
        db.query(Vendor)
        .filter(Vendor.user_id == current_user.id, Vendor.status == VendorStatus.ELIGIBLE)
        .all()
    )

    result = []
    for vendor in eligible_vendors:
        invoices = [i for i in vendor.invoices if not i.is_paid and not i.is_capex]
        if not invoices:
            continue

        red = [i for i in invoices if i.clock_status == ClockStatus.RED]
        amber = [i for i in invoices if i.clock_status == ClockStatus.AMBER]
        total_exposure = sum(float(i.disallowed_amount or 0) for i in invoices)
        total_interest = sum(float(i.accrued_interest or 0) for i in invoices)

        result.append({
            "vendor_id": vendor.id,
            "vendor_name": vendor.name,
            "udyam_number": vendor.udyam_number,
            "enterprise_category": vendor.enterprise_category,
            "invoice_count": len(invoices),
            "red_count": len(red),
            "amber_count": len(amber),
            "total_exposure": round(total_exposure, 2),
            "total_interest": round(total_interest, 2),
        })

    result.sort(key=lambda x: x["total_exposure"], reverse=True)
    return {"items": result, "citation": settings.SECTION_CITATION_COMBINED}



def _serialize_invoice(inv: Invoice, detail: bool = False) -> dict:
    score = 0.0
    if inv.clock_status in (ClockStatus.RED, ClockStatus.AMBER) and not inv.is_paid and not inv.is_capex:
        score = compute_priority_score(
            pending_amount=inv.pending_amount or Decimal(0),
            disallowed_amount=inv.disallowed_amount or Decimal(0),
            accrued_interest=inv.accrued_interest or Decimal(0),
            effective_tax_rate=EFFECTIVE_TAX_RATE,
            is_capex=inv.is_capex
        )

    base = {
        "id": inv.id,
        "vendor_id": inv.vendor_id,
        "vendor_name": inv.vendor.name if inv.vendor else None,
        "invoice_number": inv.invoice_number,
        "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
        "delivery_date": inv.delivery_date.isoformat() if inv.delivery_date else None,
        "acceptance_date": inv.acceptance_date.isoformat() if inv.acceptance_date else None,
        "statutory_deadline": inv.statutory_deadline.isoformat() if inv.statutory_deadline else None,
        "payment_date": inv.payment_date.isoformat() if inv.payment_date else None,
        "amount": float(inv.amount),
        "pending_amount": float(inv.pending_amount),
        "clock_status": inv.clock_status.value if inv.clock_status else None,
        "days_remaining": inv.days_remaining,
        "days_overdue": inv.days_overdue,
        "disallowed_amount": float(inv.disallowed_amount) if inv.disallowed_amount else None,
        "accrued_interest": float(inv.accrued_interest) if inv.accrued_interest else None,
        "tax_cost": float(inv.tax_cost) if inv.tax_cost else None,
        "priority_score": score,
        "is_paid": inv.is_paid,
        "is_capex": inv.is_capex,
        "has_written_agreement": inv.has_written_agreement,
        "citation": settings.SECTION_CITATION_COMBINED,
    }
    if detail:
        base.update({
            "gst_amount": float(inv.gst_amount) if inv.gst_amount else None,
            "agreed_payment_days": inv.agreed_payment_days,
            "dispute_raised_at": inv.dispute_raised_at.isoformat() if inv.dispute_raised_at else None,
            "dispute_resolved_at": inv.dispute_resolved_at.isoformat() if inv.dispute_resolved_at else None,
            "dispute_notes": inv.dispute_notes,
            "notes": inv.notes,
            "ingestion_source": inv.ingestion_source.value if inv.ingestion_source else None,
        })
    return base
