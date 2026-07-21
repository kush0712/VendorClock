"""
Celery tasks — CSV/Excel ingestion pipeline.

Pipeline steps per spec:
  1. Load raw file from disk
  2. Fuzzy-parse columns → extract invoice rows
  3. For each vendor: get_or_create, trigger self-declaration if new
  4. For each invoice: upsert into DB
  5. Trigger clock computation
  6. Update ingestion status

Pluggable: email/ERP adapters plug in at step 1 with the same output format.
"""

from datetime import datetime, timezone
from decimal import Decimal

from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.ingestion import RawIngestion, IngestionStatus
from app.models.invoice import Invoice, IngestionSource
from app.services.csv_parser import parse_purchase_register
from app.services.vendor_classifier import get_or_create_vendor


@celery_app.task(bind=True, max_retries=3)
def process_csv_upload(self, raw_ingestion_id: int, owner_user_id: int):
    """
    Process a CSV/Excel upload: parse → classify vendors → insert invoices → run clocks.
    owner_user_id: the user who uploaded the file (all vendors/invoices tagged to them).
    """
    db = SessionLocal()
    try:
        ingestion = db.query(RawIngestion).filter(RawIngestion.id == raw_ingestion_id).first()
        if not ingestion:
            return {"error": f"RawIngestion {raw_ingestion_id} not found"}

        ingestion.status = IngestionStatus.PROCESSING
        ingestion.celery_task_id = self.request.id
        db.commit()

        # Load file
        with open(ingestion.stored_path, "rb") as f:
            file_content = f.read()

        # Parse
        records, col_map, parse_errors = parse_purchase_register(
            file_content,
            ingestion.original_filename,
            override_mapping=ingestion.column_mapping,
        )

        ingestion.column_mapping = col_map
        ingestion.total_rows = len(records) + len(parse_errors)
        ingestion.failed_rows = len(parse_errors)
        ingestion.error_details = parse_errors

        processed = 0
        for record in records:
            try:
                # Upsert vendor — always scoped to the uploading user
                vendor, created = get_or_create_vendor(
                    db=db,
                    name=record["vendor_name"],
                    user_id=owner_user_id,
                    pan=record.get("pan"),
                    gstin=record.get("gstin"),
                )

                # If new vendor, trigger declaration email (queued separately)
                if created:
                    send_declaration_email.delay(vendor.id)

                # Upsert invoice (by invoice_number + vendor_id)
                existing = db.query(Invoice).filter(
                    Invoice.invoice_number == record["invoice_number"],
                    Invoice.vendor_id == vendor.id,
                ).first()

                if existing:
                    # Update pending amount and payment status
                    existing.pending_amount = Decimal(str(record["pending_amount"]))
                    existing.is_paid = Decimal(str(record["pending_amount"])) <= 0
                    if record.get("payment_date"):
                        existing.payment_date = record["payment_date"]
                    db.add(existing)
                else:
                    invoice = Invoice(
                        vendor_id=vendor.id,
                        invoice_number=record["invoice_number"],
                        invoice_date=record["invoice_date"],
                        delivery_date=record.get("delivery_date"),
                        amount=Decimal(str(record.get("amount") or record["pending_amount"])),
                        pending_amount=Decimal(str(record["pending_amount"])),
                        gst_amount=Decimal(str(record["gst_amount"])) if record.get("gst_amount") else None,
                        is_capex=record.get("is_capex", False),
                        has_written_agreement=record.get("has_written_agreement", False),
                        agreed_payment_days=record.get("agreed_payment_days"),
                        payment_date=record.get("payment_date"),
                        is_paid=Decimal(str(record["pending_amount"])) <= 0,
                        ingestion_source=IngestionSource.CSV_UPLOAD,
                        raw_ingestion_id=raw_ingestion_id,
                    )
                    db.add(invoice)

                processed += 1
            except Exception as e:
                ingestion.error_details = (ingestion.error_details or []) + [
                    {"row": record.get("source_row"), "error": str(e)}
                ]

        db.commit()

        # Trigger clock refresh for all invoices in this batch
        refresh_ingestion_clocks.delay(raw_ingestion_id)

        ingestion.processed_rows = processed
        ingestion.status = (
            IngestionStatus.COMPLETED if not ingestion.error_details else IngestionStatus.PARTIAL
        )
        ingestion.completed_at = datetime.now(timezone.utc)
        db.commit()

        return {
            "ingestion_id": raw_ingestion_id,
            "processed": processed,
            "failed": len(parse_errors),
            "status": ingestion.status.value,
        }

    except Exception as exc:
        if 'ingestion' in dir() and ingestion:
            ingestion.status = IngestionStatus.FAILED
            ingestion.error_details = [{"error": str(exc)}]
            db.commit()
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()


@celery_app.task
def send_declaration_email(vendor_id: int):
    """Send self-declaration email to a new vendor (async to not block ingestion)."""
    db = SessionLocal()
    try:
        from app.models.vendor import Vendor
        vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
        if not vendor or not vendor.contact_email:
            return

        from app.services.vendor_classifier import get_declaration_link
        link = get_declaration_link(vendor.declaration_link_token)

        from app.services.email_service import send_email
        html = f"""
        <html><body style="font-family:Inter,sans-serif;padding:24px;">
        <h2>Udyam Registration Verification — VendorClock</h2>
        <p>Dear {vendor.contact_name or vendor.name},</p>
        <p>Your buyer is using VendorClock to comply with <strong>{settings.SECTION_CITATION_COMBINED}</strong>.</p>
        <p>Please upload your Udyam certificate at the link below to confirm your MSME registration status:</p>
        <p><a href="{link}" style="background:#1E293B;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;">Upload Udyam Certificate</a></p>
        <p style="font-size:12px;color:#6B7280;">This is a one-time request. Your certificate is stored securely and verified annually.</p>
        </body></html>
        """
        send_email(vendor.contact_email, "Action Required: Upload your Udyam Certificate", html)

        from datetime import datetime, timezone
        vendor.declaration_email_sent_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


@celery_app.task
def refresh_ingestion_clocks(raw_ingestion_id: int):
    """Trigger clock refresh for all invoices from a specific ingestion batch."""
    db = SessionLocal()
    try:
        invoices = db.query(Invoice).filter(Invoice.raw_ingestion_id == raw_ingestion_id).all()
        for invoice in invoices:
            _refresh_single_invoice_clock(invoice, db)
        db.commit()
    finally:
        db.close()


def _refresh_single_invoice_clock(invoice: Invoice, db):
    """Recompute clock for a single invoice and update DB fields."""
    from app.services.clock_engine import compute_clock, compute_compound_interest, compute_disallowed_amount
    from app.models.vendor import VendorStatus

    vendor_status = invoice.vendor.status if invoice.vendor else VendorStatus.PENDING_DECLARATION
    result = compute_clock(
        invoice_id=invoice.id,
        invoice_date=invoice.invoice_date,
        delivery_date=invoice.delivery_date,
        acceptance_date=invoice.acceptance_date,
        has_written_agreement=invoice.has_written_agreement,
        agreed_payment_days=invoice.agreed_payment_days,
        payment_date=invoice.payment_date,
        is_paid=invoice.is_paid,
        is_capex=invoice.is_capex,
        dispute_raised_at=invoice.dispute_raised_at,
        dispute_resolved_at=invoice.dispute_resolved_at,
        vendor_status=vendor_status,
    )

    invoice.statutory_deadline = result.statutory_deadline
    invoice.days_remaining = result.days_remaining
    invoice.days_overdue = result.days_overdue
    invoice.clock_status = result.clock_status
    invoice.acceptance_date = result.acceptance_date

    # Compute financial exposure
    if not invoice.is_capex and result.clock_status.value != "EXCLUDED":
        disallowed = compute_disallowed_amount(invoice.pending_amount, invoice.gst_amount)
        interest = compute_compound_interest(disallowed, result.days_overdue)
        invoice.disallowed_amount = disallowed
        invoice.accrued_interest = interest
        from app.services.cash_priority import EFFECTIVE_TAX_RATE
        invoice.tax_cost = (disallowed * EFFECTIVE_TAX_RATE).quantize(Decimal("0.01"))
    else:
        invoice.disallowed_amount = Decimal("0.00")
        invoice.accrued_interest = Decimal("0.00")
        invoice.tax_cost = Decimal("0.00")

    db.add(invoice)
