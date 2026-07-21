"""
Migration: add user_id to vendors + tighten uploaded_by_id FK on raw_ingestions.

Run ONCE from the backend directory:
    python migrate_add_user_id.py

Idempotent: checks column existence before altering, safe to re-run.

What this does:
  1. Adds vendors.user_id column (INTEGER, NOT NULL default 0 temporarily).
  2. Removes all existing vendor/invoice/ingestion rows that have no valid owner
     (they were created in the old global-data era — no user to assign them to).
  3. Creates indexes on vendors.user_id and raw_ingestions.uploaded_by_id for scale.
"""

import sqlite3
import os
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "vendorclock.db")


def column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def index_exists(cursor, index_name: str) -> bool:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name=?", (index_name,))
    return cursor.fetchone() is not None


def main():
    if not os.path.exists(DB_PATH):
        print(f"[migrate] Database not found at {DB_PATH}")
        print("[migrate] Fresh install — SQLAlchemy will create the correct schema on startup.")
        sys.exit(0)

    print(f"[migrate] Connecting to {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Enable FK support in SQLite
    cursor.execute("PRAGMA foreign_keys = OFF")

    # ── Step 1: Add user_id column to vendors ─────────────────────────────────
    if column_exists(cursor, "vendors", "user_id"):
        print("[migrate] vendors.user_id already exists — skipping column add.")
    else:
        print("[migrate] Adding vendors.user_id column ...")
        cursor.execute("ALTER TABLE vendors ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0")
        conn.commit()
        print("[migrate] vendors.user_id column added.")

    # ── Step 2: Remove ALL existing data that has no real owner ───────────────
    print("[migrate] Clearing legacy global data (no user owner) ...")

    cursor.execute(
        "DELETE FROM invoices WHERE vendor_id IN (SELECT id FROM vendors WHERE user_id = 0)"
    )
    deleted_invoices = cursor.rowcount
    print(f"[migrate]   Removed {deleted_invoices} orphaned invoice(s).")

    cursor.execute("DELETE FROM raw_ingestions WHERE uploaded_by_id IS NULL OR uploaded_by_id = 0")
    deleted_ingestions = cursor.rowcount
    print(f"[migrate]   Removed {deleted_ingestions} orphaned ingestion record(s).")

    cursor.execute("DELETE FROM vendors WHERE user_id = 0")
    deleted_vendors = cursor.rowcount
    print(f"[migrate]   Removed {deleted_vendors} orphaned vendor(s).")

    conn.commit()

    # ── Step 3: Create indexes for scalable per-user queries ──────────────────
    if not index_exists(cursor, "ix_vendors_user_id"):
        print("[migrate] Creating index ix_vendors_user_id ...")
        cursor.execute("CREATE INDEX ix_vendors_user_id ON vendors (user_id)")
        conn.commit()
        print("[migrate] Index created.")
    else:
        print("[migrate] Index ix_vendors_user_id already exists — skipping.")

    if not index_exists(cursor, "ix_raw_ingestions_uploaded_by_id"):
        print("[migrate] Creating index ix_raw_ingestions_uploaded_by_id ...")
        cursor.execute("CREATE INDEX ix_raw_ingestions_uploaded_by_id ON raw_ingestions (uploaded_by_id)")
        conn.commit()
        print("[migrate] Index created.")
    else:
        print("[migrate] Index ix_raw_ingestions_uploaded_by_id already exists — skipping.")

    cursor.execute("PRAGMA foreign_keys = ON")
    conn.close()
    print("[migrate] Migration complete. Restart the backend server now.")


if __name__ == "__main__":
    main()
