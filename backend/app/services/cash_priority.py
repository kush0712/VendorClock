"""
Module 4 — Cash-Priority Optimizer

Ranks unpaid invoices by tax-and-interest saved per rupee of cash released.

Score = (Invoice Amount × Effective Tax Rate + Accrued Non-Deductible Interest)
        / Amount Required to Clear Invoice

Higher score = pay this invoice first for maximum tax-savings efficiency.

⚠ GST inclusion in taxable base: pending CA confirmation (config flag GST_INCLUDED_IN_TAXABLE_BASE).
⚠ Capex invoices are excluded from the disallowance engine but still appear in the queue
  (flagged is_capex=True, excluded from score calculation).
"""

from decimal import Decimal
from typing import List, Optional
from dataclasses import dataclass

from app.core.config import settings
from app.services.clock_engine import (
    compute_compound_interest,
    compute_disallowed_amount,
)
from app.models.invoice import ClockStatus


EFFECTIVE_TAX_RATE = Decimal("0.2522")  # 25% base + 2% EC + 1% SHEC ≈ 25.22% effective


@dataclass
class PriorityEntry:
    """A single ranked entry in the cash-priority payment queue."""
    invoice_id: int
    vendor_id: int
    vendor_name: str
    invoice_number: str
    pending_amount: Decimal
    days_remaining: int
    days_overdue: int
    clock_status: ClockStatus
    statutory_deadline: str       # ISO string for serialization
    disallowed_amount: Decimal
    accrued_interest: Decimal
    tax_cost: Decimal
    priority_score: float
    is_capex: bool
    is_in_dispute: bool
    citation: str = settings.SECTION_CITATION_COMBINED


def compute_priority_score(
    pending_amount: Decimal,
    disallowed_amount: Decimal,
    accrued_interest: Decimal,
    effective_tax_rate: Decimal = EFFECTIVE_TAX_RATE,
    is_capex: bool = False,
) -> float:
    """
    Cash-Priority Score per spec:
    Score = (Invoice Amount × Effective Tax Rate + Accrued Non-Deductible Interest)
            / Amount Required to Clear Invoice

    Capex invoices score 0 — excluded from disallowance, no optimization needed.
    """
    if is_capex or pending_amount <= 0:
        return 0.0

    numerator = (disallowed_amount * effective_tax_rate) + accrued_interest
    if numerator <= 0:
        return 0.0

    score = float(numerator / pending_amount)
    return round(score, 6)


def build_priority_queue(invoices_data: List[dict]) -> List[PriorityEntry]:
    """
    Build the ranked cash-priority queue from a list of invoice dicts.

    Each dict must contain:
        invoice_id, vendor_id, vendor_name, invoice_number,
        pending_amount, gst_amount, days_remaining, days_overdue,
        clock_status, statutory_deadline, is_capex, is_in_dispute,
        dispute_raised_at, rbi_bank_rate_percent (optional)

    Returns list sorted by priority_score DESC (highest = pay first).
    Only includes AMBER and RED invoices (GREEN invoices are safe — no urgent need to rank).
    """
    entries = []

    for inv in invoices_data:
        pending = Decimal(str(inv.get("pending_amount", 0)))
        gst = inv.get("gst_amount")
        gst_decimal = Decimal(str(gst)) if gst is not None else None
        days_overdue = int(inv.get("days_overdue", 0))
        clock_status = inv.get("clock_status", ClockStatus.GREEN)
        is_capex = bool(inv.get("is_capex", False))

        # Skip paid, excluded, or green invoices from the priority queue
        if clock_status in (ClockStatus.PAID, ClockStatus.EXCLUDED):
            continue

        disallowed = compute_disallowed_amount(pending, gst_decimal)
        accrued = compute_compound_interest(
            principal=disallowed,
            days_overdue=days_overdue,
            rbi_bank_rate_percent=inv.get("rbi_bank_rate_percent", settings.RBI_BANK_RATE_PERCENT),
        )
        tax_cost = (disallowed * EFFECTIVE_TAX_RATE).quantize(Decimal("0.01"))
        score = compute_priority_score(pending, disallowed, accrued, is_capex=is_capex)

        entries.append(PriorityEntry(
            invoice_id=inv["invoice_id"],
            vendor_id=inv["vendor_id"],
            vendor_name=inv["vendor_name"],
            invoice_number=inv["invoice_number"],
            pending_amount=pending,
            days_remaining=inv.get("days_remaining", 0),
            days_overdue=days_overdue,
            clock_status=clock_status,
            statutory_deadline=str(inv.get("statutory_deadline", "")),
            disallowed_amount=disallowed,
            accrued_interest=accrued,
            tax_cost=tax_cost,
            priority_score=score,
            is_capex=is_capex,
            is_in_dispute=bool(inv.get("is_in_dispute", False)),
        ))

    # Sort: RED first (by score), then AMBER (by score), then GREEN
    def sort_key(e: PriorityEntry):
        status_order = {ClockStatus.RED: 0, ClockStatus.AMBER: 1, ClockStatus.GREEN: 2}
        return (status_order.get(e.clock_status, 9), -e.priority_score)

    return sorted(entries, key=sort_key)
