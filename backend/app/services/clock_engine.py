"""
Module 3 — 15/45-Day Compliance Clock Engine (core IP)

Rules per Section 43B(h) / Section 37(2)(g), Income Tax Act 2025:

1. CONTRACT TEST (written-agreement branch):
   - Written agreement on file? → deadline = acceptance_date + min(agreed_payment_days, 45)
   - No agreement?             → deadline = acceptance_date + 15
   NOTE: This is a written-agreement branch, NOT a goods-vs-services split.

2. DEEMED ACCEPTANCE:
   - If buyer raises no written objection within 15 days of delivery,
     delivery_date becomes the legal acceptance_date the clock runs from.

3. DISPUTE HANDLING (⚠ CA/lawyer confirmation pending):
   - Written objection raised → clock pauses at dispute_raised_at
   - Config flag DISPUTE_CLOCK_RESET_TRIGGER controls exact behavior
   - Do NOT ship final numbers to auditor until CA confirms trigger/reset-date logic.

4. STATUS:
   GREEN  → > 7 days remaining
   AMBER  → 1–7 days remaining
   RED    → overdue (interest compounding, disallowance active)
   PAID   → cleared (no exposure)
   EXCLUDED → vendor not ELIGIBLE

5. DUAL CITATION: every output carries "Section 43B(h) / Section 37(2)(g), Income Tax Act 2025"
"""

from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass

from app.core.config import settings
from app.models.invoice import ClockStatus


MAX_AGREED_DAYS = 45     # Hard cap per Section 15 of MSMED Act
DEFAULT_PAYMENT_DAYS = 15  # No written agreement
AMBER_THRESHOLD_DAYS = 7  # Show amber warning this many days before deadline


@dataclass
class ClockResult:
    """Immutable result from the clock engine for one invoice."""
    invoice_id: int
    statutory_deadline: datetime
    days_remaining: int          # Negative = overdue
    days_overdue: int            # 0 if not overdue
    clock_status: ClockStatus
    acceptance_date: datetime    # Explicit or deemed
    has_written_agreement: bool
    agreed_days_applied: int     # Actual days used (min of agreed/45 or 15)
    is_in_dispute: bool
    citation: str = settings.SECTION_CITATION_COMBINED


def compute_acceptance_date(
    delivery_date: Optional[datetime],
    explicit_acceptance_date: Optional[datetime],
) -> datetime:
    """
    Deemed acceptance rule: if no explicit acceptance date AND no written objection
    is on file within 15 days of delivery, delivery_date is the acceptance date.
    In the DB we track dispute_raised_at separately — if it's None, delivery_date is deemed.
    """
    if explicit_acceptance_date:
        return explicit_acceptance_date
    if delivery_date:
        return delivery_date  # Delivery date = deemed acceptance
    # Fallback: use invoice_date if nothing else is available (edge case)
    raise ValueError("Cannot compute acceptance date: neither delivery_date nor acceptance_date provided.")


def compute_agreed_days(has_written_agreement: bool, agreed_payment_days: Optional[int]) -> int:
    """Return the effective payment days for deadline calculation."""
    if not has_written_agreement:
        return DEFAULT_PAYMENT_DAYS
    if agreed_payment_days is None:
        return DEFAULT_PAYMENT_DAYS
    return min(agreed_payment_days, MAX_AGREED_DAYS)  # Hard cap at 45


def compute_clock(
    invoice_id: int,
    invoice_date: datetime,
    delivery_date: Optional[datetime],
    acceptance_date: Optional[datetime],
    has_written_agreement: bool,
    agreed_payment_days: Optional[int],
    payment_date: Optional[datetime],
    is_paid: bool,
    is_capex: bool,
    dispute_raised_at: Optional[datetime],
    dispute_resolved_at: Optional[datetime],
    vendor_status: str,
    now: Optional[datetime] = None,
) -> ClockResult:
    """
    Run the compliance clock for a single invoice.
    Returns a ClockResult with status and all fields needed for dashboard + exports.
    """
    from app.models.vendor import VendorStatus

    now = now or datetime.now(timezone.utc)

    # Excluded vendors — clock doesn't apply
    if vendor_status != VendorStatus.ELIGIBLE:
        return ClockResult(
            invoice_id=invoice_id,
            statutory_deadline=invoice_date + timedelta(days=15),
            days_remaining=999,
            days_overdue=0,
            clock_status=ClockStatus.EXCLUDED,
            acceptance_date=acceptance_date or delivery_date or invoice_date,
            has_written_agreement=has_written_agreement,
            agreed_days_applied=0,
            is_in_dispute=False,
        )

    # Paid invoices — no more exposure
    if is_paid and payment_date:
        return ClockResult(
            invoice_id=invoice_id,
            statutory_deadline=invoice_date + timedelta(days=15),
            days_remaining=999,
            days_overdue=0,
            clock_status=ClockStatus.PAID,
            acceptance_date=acceptance_date or delivery_date or invoice_date,
            has_written_agreement=has_written_agreement,
            agreed_days_applied=compute_agreed_days(has_written_agreement, agreed_payment_days),
            is_in_dispute=False,
        )

    # Capex invoices excluded from disallowance engine (but still track)
    # Clock still runs so we know the date — filtering happens in exposure calc

    # Compute acceptance date
    try:
        eff_acceptance_date = compute_acceptance_date(delivery_date, acceptance_date)
    except ValueError:
        # Fallback to invoice_date if no delivery/acceptance data
        eff_acceptance_date = invoice_date

    # Effective agreed days
    agreed_days = compute_agreed_days(has_written_agreement, agreed_payment_days)

    # Statutory deadline
    deadline = eff_acceptance_date + timedelta(days=agreed_days)

    # Dispute handling
    # ⚠ CA/lawyer confirmation pending for exact reset logic.
    # Current: clock pauses on dispute_raised_at; resumes when resolved.
    is_in_dispute = False
    effective_now = now
    if dispute_raised_at and not dispute_resolved_at:
        is_in_dispute = True
        # Clock is paused — compute remaining as of dispute_raised_at
        effective_now = dispute_raised_at

    # Compute days remaining (from effective_now to deadline)
    # Compare as plain dates to avoid timezone-induced off-by-one errors (UTC vs IST)
    deadline_date = deadline.date() if hasattr(deadline, 'date') else deadline
    now_date = effective_now.date() if hasattr(effective_now, 'date') else effective_now
        
    days_remaining = (deadline_date - now_date).days
    days_overdue = max(0, -days_remaining)

    # Determine status
    if days_remaining > AMBER_THRESHOLD_DAYS:
        status = ClockStatus.GREEN
    elif days_remaining > 0:
        status = ClockStatus.AMBER
    else:
        status = ClockStatus.RED

    return ClockResult(
        invoice_id=invoice_id,
        statutory_deadline=deadline,
        days_remaining=days_remaining,
        days_overdue=days_overdue,
        clock_status=status,
        acceptance_date=eff_acceptance_date,
        has_written_agreement=has_written_agreement,
        agreed_days_applied=agreed_days,
        is_in_dispute=is_in_dispute,
    )


def compute_compound_interest(
    principal: Decimal,
    days_overdue: int,
    rbi_bank_rate_percent: float = settings.RBI_BANK_RATE_PERCENT,
) -> Decimal:
    """
    Compute non-deductible compound interest per MSMED Act Section 16.
    Rate = 3 × RBI Bank Rate, compounding monthly.
    ⚠ This interest is NOT deductible as a business expense.
    """
    if days_overdue <= 0 or principal <= 0:
        return Decimal("0.00")

    annual_rate = Decimal(str(rbi_bank_rate_percent * 3)) / Decimal("100")
    monthly_rate = annual_rate / Decimal("12")
    months = Decimal(str(days_overdue)) / Decimal("30")

    # Compound monthly
    compound_factor = (1 + monthly_rate) ** months
    interest = principal * (compound_factor - 1)
    return interest.quantize(Decimal("0.01"))


def compute_disallowed_amount(
    pending_amount: Decimal,
    gst_amount: Optional[Decimal],
    gst_included_in_taxable_base: bool = settings.GST_INCLUDED_IN_TAXABLE_BASE,
) -> Decimal:
    """
    Amount added back to taxable income = pending principal (possibly excluding GST).
    ⚠ GST_INCLUDED_IN_TAXABLE_BASE pending CA confirmation — defaulting to False (GST excluded).
    """
    if gst_included_in_taxable_base or gst_amount is None:
        return pending_amount
    return max(Decimal("0.00"), pending_amount - gst_amount)
