"""
Module 6 & 8 — Compliance Export Service

Module 6 — Form 3CD Audit Export:
  One-click, tax-audit-ready Excel/CSV:
  Vendor Name, Udyam Number, Invoice Date, (Deemed) Acceptance Date, Due Date,
  Actual Payment Date, Days Delayed, Disallowed Principal, MSMED Compound Interest.
  DUAL CITATION in every export header.

Module 8 — Form MSME-1 ROC Export:
  Half-yearly ROC disclosure: dues to Micro/Small suppliers outstanding > 45 days.
  Medium enterprises are EXCLUDED from this filing (confirmed per spec — no gray area).
  Same underlying data as Form 3CD.
"""

import io
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from app.core.config import settings


HEADER_FILL = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True, size=10)
AMBER_FILL = PatternFill(start_color="FFF3CD", end_color="FFF3CD", fill_type="solid")
RED_FILL = PatternFill(start_color="FFE0E0", end_color="FFE0E0", fill_type="solid")
CITATION_FONT = Font(italic=True, size=9, color="374151")

THIN_BORDER = Border(
    left=Side(style="thin", color="D1D5DB"),
    right=Side(style="thin", color="D1D5DB"),
    top=Side(style="thin", color="D1D5DB"),
    bottom=Side(style="thin", color="D1D5DB"),
)


def _fmt_date(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    return dt.strftime("%d-%b-%Y")


def _fmt_amount(val: Optional[Decimal]) -> str:
    if val is None:
        return ""
    return f"₹{val:,.2f}"


def _write_header_block(ws, title: str, fy: str, report_type: str):
    """Write the standard header block with dual citation."""
    ws.merge_cells("A1:M1")
    ws["A1"] = f"VendorClock — {title}"
    ws["A1"].font = Font(bold=True, size=14, color="1E293B")

    ws.merge_cells("A2:M2")
    ws["A2"] = f"Financial Year: {fy}  |  Report Type: {report_type}"
    ws["A2"].font = Font(size=10, color="374151")

    ws.merge_cells("A3:M3")
    ws["A3"] = (
        f"Statutory Reference: {settings.SECTION_CITATION_COMBINED}  "
        f"(FY ≤ 2025-26 → Section 43B(h); FY ≥ 2026-27 → Section 37(2)(g))"
    )
    ws["A3"].font = CITATION_FONT

    ws.merge_cells("A4:M4")
    ws["A4"] = f"Generated: {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M UTC')}  |  This export is informational — confirm with a qualified CA before filing."
    ws["A4"].font = Font(italic=True, size=8, color="6B7280")

    ws.row_dimensions[1].height = 22
    ws.row_dimensions[3].height = 16


def generate_form_3cd_export(invoices: list[dict], fy: str = "2025-26") -> bytes:
    """
    Generate Form 3CD audit export (Module 6).

    Each invoice dict must contain:
        vendor_name, udyam_number, invoice_number, invoice_date,
        acceptance_date, statutory_deadline, payment_date, days_overdue,
        disallowed_amount, accrued_interest, clock_status, is_capex
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Form 3CD — 43B(h)"

    _write_header_block(ws, "Form 3CD — Section 43B(h) / 37(2)(g) Disclosure", fy, "Tax Audit")

    # Column headers (row 6)
    headers = [
        "S.No", "Vendor Name", "Udyam Number", "Invoice No.", "Invoice Date",
        "Acceptance Date", "Due Date (Statutory)", "Payment Date",
        "Days Delayed", "Pending Amount (₹)", "Disallowed Principal (₹)",
        "Compound Interest (₹)", "Status",
    ]

    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=6, column=col_idx, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN_BORDER

    ws.row_dimensions[6].height = 30

    # Data rows — skip Capex invoices (Section 43B(h) disallowance does not apply to capital purchases)
    eligible_invoices = [inv for inv in invoices if not inv.get("is_capex", False)]
    for row_idx, inv in enumerate(eligible_invoices, 1):
        row_num = row_idx + 6
        status = inv.get("clock_status", "")
        fill = RED_FILL if status == "RED" else (AMBER_FILL if status == "AMBER" else None)

        values = [
            row_idx,
            inv.get("vendor_name", ""),
            inv.get("udyam_number") or inv.get("udyam_number", "Pending"),
            inv.get("invoice_number", ""),
            _fmt_date(inv.get("invoice_date")),
            _fmt_date(inv.get("acceptance_date")),
            _fmt_date(inv.get("statutory_deadline")),
            _fmt_date(inv.get("payment_date")),
            inv.get("days_overdue", 0),
            _fmt_amount(inv.get("pending_amount")),
            _fmt_amount(inv.get("disallowed_amount")),
            _fmt_amount(inv.get("accrued_interest")),
            status,
        ]

        for col_idx, value in enumerate(values, 1):
            cell = ws.cell(row=row_num, column=col_idx, value=value)
            cell.border = THIN_BORDER
            cell.alignment = Alignment(vertical="center")
            if fill:
                cell.fill = fill

    # Set column widths
    col_widths = [6, 35, 20, 18, 14, 16, 20, 14, 12, 20, 22, 20, 12]
    for i, width in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width

    # Freeze header rows
    ws.freeze_panes = "A7"

    # Add summary totals row
    total_row = len(eligible_invoices) + 7
    ws.cell(row=total_row, column=1, value="TOTAL").font = Font(bold=True)
    ws.cell(row=total_row, column=11, value=_fmt_amount(
        sum(Decimal(str(inv.get("disallowed_amount", 0) or 0)) for inv in eligible_invoices)
    )).font = Font(bold=True)
    ws.cell(row=total_row, column=12, value=_fmt_amount(
        sum(Decimal(str(inv.get("accrued_interest", 0) or 0)) for inv in eligible_invoices)
    )).font = Font(bold=True)

    # Footer disclaimer
    footer_row = total_row + 2
    ws.merge_cells(f"A{footer_row}:M{footer_row}")
    ws.cell(row=footer_row, column=1, value=(
        f"⚠ Statutory Reference: {settings.SECTION_CITATION_COMBINED}. "
        "Compound interest = 3× RBI Bank Rate, monthly compounding (MSMED Act Section 16). "
        "GST inclusion in disallowance base: pending CA confirmation. "
        "Capex invoices excluded from disallowance calculation. "
        "Confirm with your CA before filing."
    )).font = Font(italic=True, size=8, color="6B7280")

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


def generate_msme1_export(invoices: list[dict], half_year: str = "April–September 2025") -> bytes:
    """
    Generate Form MSME-1 ROC export (Module 8).

    IMPORTANT: Only Micro and Small enterprise dues outstanding > 45 days.
    Medium enterprises are EXCLUDED from this filing (confirmed — not a gray area).

    Each invoice dict must contain:
        vendor_name, udyam_number, enterprise_category, invoice_number,
        invoice_date, statutory_deadline, pending_amount, days_overdue
    Note: enterprise_category must be "Micro" or "Small" — "Medium" filtered out here.
    """
    # Hard filter: Medium enterprises excluded.
    # Vendors without an explicit category are treated as Micro/Small if they are ELIGIBLE.
    # Medium enterprises are hard-excluded per MSMED Act (confirmed — not a gray area).
    eligible = [
        inv for inv in invoices
        if str(inv.get("enterprise_category", "micro") or "micro").strip().lower() in ("micro", "small")
        and int(inv.get("days_overdue", 0)) > 45
    ]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Form MSME-1"

    _write_header_block(ws, f"Form MSME-1 — ROC Half-Yearly Disclosure ({half_year})", half_year, "ROC Filing")

    ws.merge_cells("A5:M5")
    ws["A5"] = (
        "Dues to Micro and Small Enterprise suppliers outstanding beyond 45 days. "
        "Medium enterprises are EXCLUDED from this filing as confirmed under MSMED Act."
    )
    ws["A5"].font = Font(italic=True, size=9, color="B45309")

    headers = [
        "S.No", "Vendor Name", "Udyam Number", "Enterprise Category",
        "Invoice No.", "Invoice Date", "Due Date (Statutory)",
        "Outstanding Amount (₹)", "Days Outstanding", "Principal Overdue (₹)",
    ]
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=7, column=col_idx, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN_BORDER
    ws.row_dimensions[7].height = 30

    for row_idx, inv in enumerate(eligible, 1):
        row_num = row_idx + 7
        values = [
            row_idx,
            inv.get("vendor_name", ""),
            inv.get("udyam_number", ""),
            inv.get("enterprise_category", ""),
            inv.get("invoice_number", ""),
            _fmt_date(inv.get("invoice_date")),
            _fmt_date(inv.get("statutory_deadline")),
            _fmt_amount(inv.get("pending_amount")),
            inv.get("days_overdue", 0),
            _fmt_amount(inv.get("disallowed_amount")),
        ]
        for col_idx, value in enumerate(values, 1):
            cell = ws.cell(row=row_num, column=col_idx, value=value)
            cell.border = THIN_BORDER
            cell.fill = RED_FILL  # All entries here are overdue by definition
            cell.alignment = Alignment(vertical="center")

    # Column widths
    col_widths = [6, 35, 20, 18, 18, 14, 20, 22, 15, 22]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.freeze_panes = "A8"

    # Summary
    total_row = len(eligible) + 8
    ws.cell(row=total_row, column=1, value=f"TOTAL ({len(eligible)} vendors)").font = Font(bold=True)
    ws.cell(row=total_row, column=8, value=_fmt_amount(
        sum(Decimal(str(inv.get("pending_amount", 0) or 0)) for inv in eligible)
    )).font = Font(bold=True)

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()
