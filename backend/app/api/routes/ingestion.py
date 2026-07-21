"""
Module 1 — Ingestion API Routes

POST /api/ingestion/upload        — upload CSV/Excel file
GET  /api/ingestion/{id}/status   — check job status
GET  /api/ingestion/               — list all ingestion jobs
POST /api/ingestion/{id}/remap    — re-run with corrected column mapping
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.core.config import settings
from app.models.ingestion import RawIngestion, IngestionStatus
from app.models.vendor import Vendor
from app.models.user import UserRole

router = APIRouter(prefix="/api/ingestion", tags=["Ingestion"])


class RemapRequest(BaseModel):
    column_mapping: dict[str, Optional[str]]


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.ACCOUNTANT, UserRole.ADMIN)),
):
    """
    Upload a purchase register CSV or Excel file.
    Returns ingestion job ID for status polling.
    Accepted formats: .csv, .xlsx, .xls
    """
    allowed_extensions = (".csv", ".xlsx", ".xls")
    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Upload a .csv, .xlsx, or .xls file.",
        )

    # Save file to disk
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}{ext}"
    stored_path = os.path.join(settings.UPLOAD_DIR, unique_name)

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50 MB limit
        raise HTTPException(status_code=400, detail="File too large. Maximum upload size is 50 MB.")

    with open(stored_path, "wb") as f:
        f.write(content)

    # Create ingestion record
    ingestion = RawIngestion(
        source="CSV_UPLOAD",
        status=IngestionStatus.QUEUED,
        original_filename=filename,
        stored_path=stored_path,
        uploaded_by_id=current_user.id,
    )
    db.add(ingestion)
    db.commit()
    db.refresh(ingestion)

    # Try Celery first; fall back to synchronous processing if Redis isn't running
    try:
        from app.tasks.ingestion_tasks import process_csv_upload
        task = process_csv_upload.delay(ingestion.id, current_user.id)
        ingestion.celery_task_id = task.id
        db.commit()
        mode = "async"
    except Exception:
        # Redis not running — process synchronously (fine for local dev)
        _run_ingestion_sync(ingestion.id, current_user.id)
        db.refresh(ingestion)
        mode = "sync"

    return {
        "ingestion_id": ingestion.id,
        "status": ingestion.status.value,
        "filename": filename,
        "mode": mode,
        "message": "File processed successfully." if mode == "sync" else "File queued for processing. Poll /status for updates.",
    }


def _run_ingestion_sync(raw_ingestion_id: int, owner_user_id: int):
    """
    Run the full ingestion pipeline synchronously (no Celery needed).
    Used automatically when Redis is unavailable (local dev without Docker).
    owner_user_id: the user who uploaded the file — all created vendors/invoices are tagged to them.
    """
    from decimal import Decimal
    from datetime import datetime, timezone
    from app.core.database import SessionLocal
    from app.models.ingestion import RawIngestion, IngestionStatus
    from app.models.invoice import Invoice, IngestionSource
    from app.services.csv_parser import parse_purchase_register
    from app.services.vendor_classifier import get_or_create_vendor
    from app.tasks.ingestion_tasks import _refresh_single_invoice_clock

    db = SessionLocal()
    try:
        ingestion = db.query(RawIngestion).filter(RawIngestion.id == raw_ingestion_id).first()
        if not ingestion:
            return

        ingestion.status = IngestionStatus.PROCESSING
        db.commit()

        with open(ingestion.stored_path, "rb") as f:
            file_content = f.read()

        records, col_map, parse_errors = parse_purchase_register(
            file_content,
            ingestion.original_filename,
            override_mapping=ingestion.column_mapping,
        )

        ingestion.column_mapping = col_map
        ingestion.total_rows = len(records) + len(parse_errors)
        ingestion.failed_rows = len(parse_errors)
        ingestion.error_details = parse_errors if parse_errors else None

        processed = 0
        for record in records:
            try:
                vendor, created = get_or_create_vendor(
                    db=db,
                    name=record["vendor_name"],
                    user_id=owner_user_id,  # tag vendor to the uploading user
                    pan=record.get("pan"),
                    gstin=record.get("gstin"),
                )

                # If new vendor, trigger declaration email (same as Celery path)
                if created and vendor.contact_email:
                    try:
                        from app.tasks.ingestion_tasks import send_declaration_email
                        send_declaration_email.delay(vendor.id)
                    except Exception:
                        pass  # Redis not running in sync mode — skip gracefully

                existing = db.query(Invoice).filter(
                    Invoice.invoice_number == record["invoice_number"],
                    Invoice.vendor_id == vendor.id,
                ).first()

                if existing:
                    existing.pending_amount = Decimal(str(record["pending_amount"]))
                    existing.is_paid = Decimal(str(record["pending_amount"])) <= 0
                    if record.get("payment_date"):
                        existing.payment_date = record["payment_date"]
                    inv = existing
                else:
                    inv = Invoice(
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
                    db.add(inv)
                    db.flush()  # get id before clock refresh

                _refresh_single_invoice_clock(inv, db)
                processed += 1

            except Exception as e:
                ingestion.failed_rows = (ingestion.failed_rows or 0) + 1
                ingestion.error_details = (ingestion.error_details or []) + [
                    {"row": record.get("source_row"), "error": str(e)}
                ]

        ingestion.processed_rows = processed
        ingestion.status = (
            IngestionStatus.COMPLETED if not ingestion.error_details else IngestionStatus.PARTIAL
        )
        ingestion.completed_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as exc:
        if ingestion:
            ingestion.status = IngestionStatus.FAILED
            ingestion.error_details = [{"error": str(exc)}]
            db.commit()
        raise
    finally:
        db.close()


@router.get("/{ingestion_id}/status")
def get_ingestion_status(
    ingestion_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get the current status of an ingestion job (ownership checked)."""
    ingestion = db.query(RawIngestion).filter(
        RawIngestion.id == ingestion_id,
        RawIngestion.uploaded_by_id == current_user.id,
    ).first()
    if not ingestion:
        raise HTTPException(status_code=404, detail="Ingestion not found")

    return {
        "ingestion_id": ingestion.id,
        "status": ingestion.status.value,
        "filename": ingestion.original_filename,
        "total_rows": ingestion.total_rows,
        "processed_rows": ingestion.processed_rows,
        "failed_rows": ingestion.failed_rows,
        "column_mapping": ingestion.column_mapping,
        "error_details": ingestion.error_details,
        "created_at": ingestion.created_at.isoformat() if ingestion.created_at else None,
        "completed_at": ingestion.completed_at.isoformat() if ingestion.completed_at else None,
    }


@router.get("/")
def list_ingestions(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    limit: int = 20,
    offset: int = 0,
):
    """List ingestion jobs for the current user (most recent first)."""
    items = (
        db.query(RawIngestion)
        .filter(RawIngestion.uploaded_by_id == current_user.id)
        .order_by(RawIngestion.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "id": i.id,
                "filename": i.original_filename,
                "status": i.status.value,
                "source": i.source,
                "total_rows": i.total_rows,
                "processed_rows": i.processed_rows,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in items
        ],
        "total": db.query(RawIngestion).filter(RawIngestion.uploaded_by_id == current_user.id).count(),
    }


@router.post("/{ingestion_id}/remap", status_code=status.HTTP_202_ACCEPTED)
def remap_and_reprocess(
    ingestion_id: int,
    body: RemapRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.ACCOUNTANT, UserRole.ADMIN)),
):
    """Re-run an ingestion with a corrected column mapping (ownership checked)."""
    ingestion = db.query(RawIngestion).filter(
        RawIngestion.id == ingestion_id,
        RawIngestion.uploaded_by_id == current_user.id,  # ownership check
    ).first()
    if not ingestion:
        raise HTTPException(status_code=404, detail="Ingestion not found")
    if not ingestion.stored_path or not os.path.exists(ingestion.stored_path):
        raise HTTPException(status_code=400, detail="Original file not found on disk.")

    ingestion.column_mapping = body.column_mapping
    ingestion.status = IngestionStatus.QUEUED
    db.commit()

    task = process_csv_upload.delay(ingestion.id, current_user.id)
    ingestion.celery_task_id = task.id
    db.commit()

    return {"ingestion_id": ingestion.id, "status": "re-queued"}

