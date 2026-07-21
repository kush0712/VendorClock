"""
Module 1 — CSV/Excel Purchase Register Parser

Fuzzy-match column detection for common ERP export formats (Tally, Zoho, SAP).
Detects and maps: Vendor Name, PAN/GSTIN, Invoice Number, Invoice Date, 
                  Pending Amount, Delivery Date, Amount, Payment Date.

Design: pluggable — email/ERP ingest paths use the same normalized output schema.
Phase 2: add Gmail API + ERP sync adapters that produce the same dict format.
"""

import io
import re
from datetime import datetime, timezone
from typing import Optional, Union
from decimal import Decimal, InvalidOperation

import pandas as pd
from rapidfuzz import fuzz, process as rfprocess

# ── Target field definitions ─────────────────────────────────────────────────
# Each entry: (canonical_name, [alias keywords])
FIELD_ALIASES = {
    "vendor_name": [
        "vendor", "supplier", "party", "vendor name", "supplier name",
        "party name", "creditor", "payee", "ledger", "account name",
    ],
    "pan": [
        "pan", "pan number", "pan no", "pan card", "permanent account number",
    ],
    "gstin": [
        "gstin", "gst", "gst number", "gstin no", "gst no", "gst reg",
        "tax id", "gstin/uin",
    ],
    "pan_or_gstin": [
        "pan/gstin", "gstin/pan", "tax number", "vendor id", "tax reg no",
    ],
    "invoice_number": [
        "invoice", "invoice no", "invoice number", "inv no", "inv number",
        "bill no", "bill number", "voucher no", "document no", "ref no",
    ],
    "invoice_date": [
        "invoice date", "inv date", "bill date", "date of invoice",
        "transaction date", "document date", "voucher date",
    ],
    "delivery_date": [
        "delivery date", "receipt date", "received date", "goods receipt",
        "gr date", "acceptance date", "service date", "dispatch date",
    ],
    "amount": [
        "amount", "total amount", "invoice amount", "gross amount",
        "total value", "value", "bill amount", "invoice value",
    ],
    "pending_amount": [
        "pending", "pending amount", "outstanding", "balance", "due amount",
        "payable", "unpaid", "amount due", "balance due", "net payable",
    ],
    "payment_date": [
        "payment date", "paid date", "paid on", "cleared on",
        "settlement date", "date of payment",
    ],
    "has_written_agreement": [
        "agreement", "written agreement", "contract", "has contract",
        "has agreement", "written contract", "has written agreement",
    ],
    "agreed_payment_days": [
        "payment days", "credit days", "due days", "terms",
        "agreed days", "credit period", "payment terms", "credit terms",
        "net days", "days credit",
    ],
    "gst_amount": [
        "gst amount", "tax amount", "igst", "cgst", "sgst", "tax",
        "gst value", "total gst",
    ],
    "is_capex": [
        "capex", "capital", "asset", "fixed asset", "capital expenditure",
    ],
}

REQUIRED_FIELDS = {"vendor_name", "invoice_number", "invoice_date", "pending_amount"}

DATE_FORMATS = [
    "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y",
    "%d-%b-%Y", "%d %b %Y", "%b %d, %Y", "%Y/%m/%d",
    "%d.%m.%Y", "%d-%m-%y", "%d/%m/%y",
]


def _normalize_header(h: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", str(h).lower().strip())


def detect_column_mapping(columns: list[str]) -> dict[str, Optional[str]]:
    """
    Fuzzy-match DataFrame column headers to canonical field names.
    Returns: {canonical_field: matched_column_name or None}
    """
    normalized_cols = {c: _normalize_header(c) for c in columns}
    mapping = {}

    for field, aliases in FIELD_ALIASES.items():
        best_col = None
        best_score = 0

        for col, norm_col in normalized_cols.items():
            for alias in aliases:
                score = fuzz.token_sort_ratio(norm_col, alias)
                if score > best_score and score >= 70:  # 70% match threshold
                    best_score = score
                    best_col = col

        mapping[field] = best_col

    return mapping


def _parse_date(value) -> Optional[datetime]:
    """Try multiple date formats and return a timezone-aware datetime."""
    if pd.isna(value) or value is None:
        return None
    if isinstance(value, (datetime,)):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime().replace(tzinfo=timezone.utc)
    s = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _parse_amount(value) -> Optional[Decimal]:
    """Parse numeric/string amounts, removing currency symbols and commas."""
    if pd.isna(value) or value is None:
        return None
    s = re.sub(r"[₹$£,\s]", "", str(value).strip())
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _parse_bool(value) -> bool:
    """Parse boolean-ish column values."""
    if pd.isna(value) or value is None:
        return False
    s = str(value).strip().lower()
    return s in ("yes", "y", "true", "1", "x", "✓", "capex", "capital")


def load_file(file_content: bytes, filename: str) -> pd.DataFrame:
    """Load CSV or Excel into a DataFrame."""
    fname = filename.lower()
    if fname.endswith(".csv"):
        # Try common encodings
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                return pd.read_csv(io.BytesIO(file_content), encoding=enc, dtype=str)
            except Exception:
                continue
        raise ValueError("Could not decode CSV file — try saving as UTF-8.")
    elif fname.endswith((".xlsx", ".xls")):
        engine = "openpyxl" if fname.endswith(".xlsx") else "xlrd"
        return pd.read_excel(io.BytesIO(file_content), engine=engine, dtype=str)
    else:
        raise ValueError(f"Unsupported file format: {filename}. Upload a .csv, .xlsx, or .xls file.")


def parse_purchase_register(
    file_content: bytes,
    filename: str,
    override_mapping: Optional[dict] = None,
) -> tuple[list[dict], dict[str, Optional[str]], list[dict]]:
    """
    Parse a purchase register CSV/Excel file.

    Returns:
        (records, column_mapping, errors)
        - records: list of normalized invoice dicts
        - column_mapping: {canonical_field: detected_column}
        - errors: list of {row, error} dicts for rows that failed
    """
    df = load_file(file_content, filename)

    # Drop fully empty rows/columns
    df = df.dropna(how="all").dropna(axis=1, how="all")
    df.columns = [str(c).strip() for c in df.columns]

    # Detect or use override mapping
    col_map = override_mapping or detect_column_mapping(df.columns.tolist())

    records = []
    errors = []

    for idx, row in df.iterrows():
        row_num = idx + 2  # 1-indexed, +1 for header

        try:
            # Vendor name — required
            vendor_col = col_map.get("vendor_name")
            if not vendor_col or pd.isna(row.get(vendor_col)):
                errors.append({"row": row_num, "error": "Missing vendor name"})
                continue
            vendor_name = str(row[vendor_col]).strip()

            # Invoice number — required
            inv_num_col = col_map.get("invoice_number")
            if not inv_num_col or pd.isna(row.get(inv_num_col)):
                errors.append({"row": row_num, "error": "Missing invoice number"})
                continue
            invoice_number = str(row[inv_num_col]).strip()

            # Invoice date — required
            inv_date_col = col_map.get("invoice_date")
            invoice_date = _parse_date(row.get(inv_date_col)) if inv_date_col else None
            if not invoice_date:
                errors.append({"row": row_num, "error": f"Could not parse invoice_date from column '{inv_date_col}'"})
                continue

            # Pending amount — required
            pending_col = col_map.get("pending_amount")
            pending_amount = _parse_amount(row.get(pending_col)) if pending_col else None
            if pending_amount is None:
                errors.append({"row": row_num, "error": f"Could not parse pending_amount from column '{pending_col}'"})
                continue

            # PAN / GSTIN (optional but strongly encouraged)
            pan = None
            gstin = None
            pan_col = col_map.get("pan")
            gstin_col = col_map.get("gstin")
            pan_or_gstin_col = col_map.get("pan_or_gstin")

            if pan_col and not pd.isna(row.get(pan_col)):
                pan = str(row[pan_col]).strip().upper() or None
            if gstin_col and not pd.isna(row.get(gstin_col)):
                gstin = str(row[gstin_col]).strip().upper() or None
            if pan_or_gstin_col and not pd.isna(row.get(pan_or_gstin_col)):
                val = str(row[pan_or_gstin_col]).strip().upper()
                if len(val) == 15:
                    gstin = val
                elif len(val) == 10:
                    pan = val

            # Optional fields
            delivery_date = _parse_date(row.get(col_map.get("delivery_date"))) if col_map.get("delivery_date") else None
            payment_date = _parse_date(row.get(col_map.get("payment_date"))) if col_map.get("payment_date") else None
            amount = _parse_amount(row.get(col_map.get("amount"))) if col_map.get("amount") else pending_amount
            gst_amount = _parse_amount(row.get(col_map.get("gst_amount"))) if col_map.get("gst_amount") else None
            is_capex = _parse_bool(row.get(col_map.get("is_capex"))) if col_map.get("is_capex") else False

            # Payment terms — agreed_payment_days takes numeric value (e.g. Payment Terms = 45)
            agreed_days = None
            agreed_days_col = col_map.get("agreed_payment_days")
            if agreed_days_col and not pd.isna(row.get(agreed_days_col)):
                try:
                    val = int(float(str(row[agreed_days_col]).strip()))
                    if val > 0:
                        agreed_days = val
                except (ValueError, TypeError):
                    pass

            # has_written_agreement: infer True if numeric days given;
            # only override if there is a SEPARATE explicit boolean column
            has_agreement = bool(agreed_days and agreed_days > 0)
            has_agmt_col = col_map.get("has_written_agreement")
            if has_agmt_col and has_agmt_col != agreed_days_col:
                # Only use the explicit column if it maps to a different source column
                explicit_val = _parse_bool(row.get(has_agmt_col))
                # If explicit says True, honour it; if False and we already have days, keep True
                if explicit_val:
                    has_agreement = True

            records.append({
                "vendor_name": vendor_name,
                "pan": pan,
                "gstin": gstin,
                "invoice_number": invoice_number,
                "invoice_date": invoice_date,
                "delivery_date": delivery_date,
                "payment_date": payment_date,
                "amount": amount,
                "pending_amount": pending_amount,
                "gst_amount": gst_amount,
                "is_capex": is_capex,
                "has_written_agreement": has_agreement,
                "agreed_payment_days": agreed_days,
                "source_row": row_num,
            })

        except Exception as e:
            errors.append({"row": row_num, "error": str(e)})

    return records, col_map, errors
