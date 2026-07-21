# VendorClock

> **Buyer-side compliance and cash-priority tool for Section 43B(h) / Section 37(2)(g), Income Tax Act 2025**

VendorClock is a full-stack web application that helps Indian companies stay compliant with statutory MSME payment deadlines. It ingests purchase registers, runs a live statutory clock on every eligible invoice, surfaces which invoices to pay first when cash is limited, and generates the audit paperwork (Form 3CD & MSME-1) your CA needs at filing time — all on a fully self-hostable, free-tier stack.

---

## Table of Contents

- [The Problem it Solves](#the-problem-it-solves)
- [Features](#features)
  - [Authentication & User Management](#1-authentication--user-management)
  - [Module 1 — Ledger & Invoice Ingestion](#2-module-1--ledger--invoice-ingestion)
  - [Module 2 — Vendor MSME-Status & Exclusions Engine](#3-module-2--vendor-msme-status--exclusions-engine)
  - [Module 3 — The 15/45-Day Compliance Clock](#4-module-3--the-1545-day-compliance-clock-engine)
  - [Module 4 — CFO Cash-Priority Dashboard](#5-module-4--cfo-cash-priority--exposure-dashboard)
  - [Module 5 — Internal Alerts & Escalations](#6-module-5--internal-alerts--escalation)
  - [Module 6 — Form 3CD Audit Export](#7-module-6--form-3cd-audit-export)
  - [Module 7 — Vendor Status Portal](#8-module-7--vendor-facing-status-portal)
  - [Module 8 — Form MSME-1 ROC Export](#9-module-8--form-msme-1-roc-export)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Local Development Setup](#local-development-setup)
- [Environment Variables](#environment-variables)
- [RBAC — User Roles](#rbac--user-roles)
- [Registering & Promoting an Admin](#registering--promoting-an-admin)
- [Deployment Notes](#deployment-notes)
- [Legal Disclaimer](#legal-disclaimer)

---

## The Problem it Solves

**Section 43B(h)** of the Income Tax Act (carried forward as **Section 37(2)(g)** from FY 2026-27 onward under the Income Tax Act, 2025) mandates strict payment timelines to Micro and Small Enterprises (MSEs):

- **15 days** if there is no written agreement.
- **Up to 45 days** (capped) if a written agreement exists — from the date of acceptance or deemed acceptance.

Missing these deadlines triggers:

1. **Immediate tax disallowance** — the unpaid expense is added back to taxable income.
2. **Compound interest penalty** — 3× the RBI bank rate, compounding monthly, payable to the vendor.
3. **Non-deductible interest** — the penalty interest cannot itself be claimed as a business expense.
4. **Two mandatory disclosures** — Form 3CD (tax audit) and Form MSME-1 (ROC half-yearly filing).

Most companies run SAP, Oracle, Tally, or Zoho with default 60–120-day credit cycles that are completely blind to vendor MSME status, the 15/45-day clock, and the critical trader exclusion (NIC codes 45/46/47). Finance teams reconstruct all of this manually in Excel every quarter.

VendorClock automates the entire compliance lifecycle from ingestion to audit export.

> **Naming note:** Every dashboard label, export, and piece of copy carries **both citations** — `Section 43B(h)` and `Section 37(2)(g), Income Tax Act 2025` — side by side, covering both FY 2025-26 and FY 2026-27 filings.

---

## Features

### 1. Authentication & User Management

A complete, production-grade auth system built on top of the compliance engine.

- **Secure Registration:** Full sign-up form collecting name, email, company name, and password. Passwords are hashed with **Bcrypt**; sessions use short-lived **JWT tokens**.
- **Rate-Limited Login:** Auth endpoints are protected by `slowapi` to prevent brute-force attacks.
- **Multi-Tenancy & Data Isolation:** Every vendor and invoice is scoped to the authenticated `user_id`. Users can only ever see and compute their own data — complete isolation between companies.
- **Role-Based Access Control (RBAC):** Four distinct roles with different permission levels (see [RBAC section](#rbac--user-roles) below).
- **Promote to Admin CLI:** A `promote_admin.py` script lets you elevate any registered user to `ADMIN` role from the command line without touching the database directly.

---

### 2. Module 1 — Ledger & Invoice Ingestion

The entry point for all invoice data.

- **CSV / Excel parser** with **fuzzy column matching** (powered by `rapidfuzz`) — upload any purchase register exported from Tally, Zoho Books, or SAP. The engine auto-detects columns for Vendor Name, PAN/GSTIN, Invoice Number, Invoice Date, and Pending Amount regardless of exact header names.
- **React Dropzone UI** — drag-and-drop file upload with real-time validation feedback on the frontend.
- **Background processing** — uploads are queued via **Celery + Redis** so the UI never blocks; the user sees live status updates.
- **Async ingestion pipeline** — raw uploads land in `raw_ingestions` before being processed, providing a full audit trail of every file received.
- **Phase 2 (planned):** Direct ERP sync via Tally ODBC/XML, Zoho Books API, and SAP Business One Service Layer.
- **Phase 2 (planned):** Inbound email inbox — forward invoice PDFs to a dedicated address; Tesseract OCR + Groq LLM extraction pulls structured fields automatically.

---

### 3. Module 2 — Vendor MSME-Status & Exclusions Engine

Multi-step validation that determines which vendors are actually covered by the law.

```
[Vendor PAN/GSTIN]
       │
       ▼
[Udyam self-declaration link sent] ──(no response / not registered)──> [EXCLUDE — not MSE-protected]
       │
       ▼ (certificate uploaded)
[NIC Code Check: 45, 46, 47?] ─────(yes — Wholesale/Retail Trader)───> [EXCLUDE — Section 15 does not apply to traders]
       │
       ▼ (no — Manufacturer/Service Provider, Micro or Small)
[CONFIRMED ELIGIBLE SUPPLIER] → Active Compliance Clock
```

- **Self-declaration flow:** A one-time emailed link is sent to each vendor. They upload their Udyam certificate; it is stored and re-verified annually.
- **Hard NIC trader exclusion:** NIC codes 45, 46, 47 (Wholesale/Retail Trade) are Udyam-eligible for Priority Sector Lending **only** — Section 15 payment protection and therefore 43B(h)/37(2)(g) does **not** extend to them. The engine parses the NIC code off the certificate and automatically tags these vendors `EXCLUDED_TRADER`.
- **Vendor Status Tags:** Each vendor is classified as `ELIGIBLE`, `EXCLUDED_TRADER`, `EXCLUDED_MEDIUM`, or `PENDING_DECLARATION`.
- **Vendor portal:** A secure, token-gated public page (`/vendor-status`) where vendors can self-upload their Udyam certificates without needing an account.
- **Manual spot-check path:** Supports periodic sampling against the public udyamregistration.gov.in search for audit defense.
- **Phase 2 upgrade path:** Swap in a paid bulk-verification API (Gridlines / Decentro / Deepvue) once revenue justifies it — no architecture changes required.

---

### 4. Module 3 — The 15/45-Day Compliance Clock Engine

The core IP of VendorClock.

- **Contract test branch:** Does a written agreement exist? → deadline = acceptance date + agreed term (capped at 45 days). No agreement? → deadline = acceptance date + 15 days.
- **Deemed acceptance:** If the buyer raises no written objection within 15 days of delivery, the delivery date legally becomes the acceptance date the clock runs from.
- **Dispute handling:** A written objection pauses the clock until the dispute is resolved (exact trigger is a CA-confirmation item — see [Legal Disclaimer](#legal-disclaimer)).
- **Live status colours:** 🟢 Green (safe) / 🟡 Amber (approaching deadline) / 🔴 Red (overdue — interest compounding, disallowance active).
- **Dual statutory citation:** Every date, status label, and export carries both `Section 43B(h)` and `Section 37(2)(g), Income Tax Act 2025` — never one alone.
- **Capex exclusion:** Invoices tagged as asset purchases are excluded from the disallowance engine.

---

### 5. Module 4 — CFO Cash-Priority & Exposure Dashboard

Built for multi-thousand-invoice enterprises — not a simple calculator.

- **Total ₹ exposure at risk** of tax disallowance by March 31, broken down by vendor and invoice.
- **Effective tax cost** of that exposure (disallowed amount × applicable rate).
- **Running non-deductible compound interest** accrual per vendor/invoice (3× RBI bank rate, compounding monthly).
- **Cash-Priority Optimizer** — ranks all unpaid eligible invoices by tax-and-interest saved per rupee of cash released:

  ```
  Score = (Invoice Amount × Effective Tax Rate + Accrued Non-Deductible Interest) / Amount Required to Clear Invoice
  ```

- **"By Vendor" tab** — aggregated exposure grouped by supplier.
- **Onboarding empty-states** — guides new users from upload to first insights without dead ends.
- **Recharts visualisations** — interactive exposure and priority charts.

---

### 6. Module 5 — Internal Alerts & Escalation

All alerts are **buyer-side only** — VendorClock never contacts vendors directly via alerts.

- **Daily AP nudge emails:** "These N invoices cross the deadline in 5 days, ₹X exposure" — sent to the AP owner.
- **Weekly CFO/Controller escalation report** — intensity increases as March 31 approaches.
- **Slack webhook integration** — posts alert summaries to a configured Slack channel.
- **Celery Beat scheduler** — background scheduler runs alert tasks on configurable cron schedules, managed by admins from the Settings page.
- **Role-based Settings UI:**
  - **Admins** see SMTP configuration, "Send Test Email" utility, Slack webhook setup, and Celery beat schedule management.
  - **Standard users** see a clean "Your Alert Preferences" confirmation card.

---

### 7. Module 6 — Form 3CD Audit Export

One-click, tax-audit-ready Excel export.

- Columns: Vendor Name, Udyam Number, Invoice Date, (Deemed) Acceptance Date, Due Date, Actual Payment Date, Days Delayed, Disallowed Principal, MSMED Compound Interest.
- Both statutory citations printed on the export header.
- Covers **all** delayed MSE dues (Micro, Small, and Medium — for 3CD purposes).
- Generated instantly on demand from the same underlying database tables.

---

### 8. Module 7 — Vendor-Facing Status Portal

A lightweight, relationship-preserving touchpoint for vendors.

- A public, token-gated URL a buyer can share with a vendor: "Your invoice is on file, due on [date]."
- Vendors can also use this page to **upload their Udyam certificate** without needing a VendorClock account.
- Pure status visibility — not a dunning/chasing mechanism, so it doesn't strain the buyer-vendor relationship.

---

### 9. Module 8 — Form MSME-1 ROC Export

Half-yearly ROC disclosure, generated from the same data as Module 6.

- Covers dues to **Micro and Small** suppliers outstanding beyond 45 days.
- **Medium enterprises are excluded** from this filing — correctly handled via Udyam classification in Module 2.
- Excel export, one click, on demand.

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| **Frontend** | Next.js 16 (App Router) + React 19 | TypeScript throughout |
| **UI Components** | shadcn/ui + TailwindCSS v4 | Component-driven, accessible |
| **State & Data Fetching** | TanStack Query (React Query v5) | Optimistic updates, caching |
| **Charts** | Recharts | Dashboard visualisations |
| **HTTP Client** | Axios | API calls from the frontend |
| **Backend** | Python 3 + FastAPI 0.115 | Async-native, auto-generates OpenAPI docs at `/api/docs` |
| **Task Queue** | Celery 5 + Redis 7 | Background ingestion, OCR, scheduled email/Slack alerts |
| **Database** | PostgreSQL 16 (production) / SQLite (dev) | SQLAlchemy ORM + Alembic migrations |
| **OCR** | Tesseract + pdf2image + Pillow | Invoice PDF extraction; manual correction fallback in UI |
| **LLM Extraction** | Groq (primary — Llama/Qwen, no data training) | Safe for real PAN/GSTIN data |
| **LLM Fallback** | Google Gemini (test/synthetic traffic only) | ⚠ Free tier trains on prompts — never use with real vendor data |
| **Auth** | JWT (python-jose) + Bcrypt (passlib) + slowapi rate limiting | Stateless, short-lived tokens |
| **Data Processing** | Pandas + rapidfuzz + openpyxl | Fuzzy column matching, Excel exports |
| **Email** | aiosmtplib + Jinja2 templates | Gmail / Google Workspace SMTP |
| **Containerisation** | Docker + Docker Compose | Full local stack in one command |
| **Hosting (target)** | Oracle Cloud Always-Free Ampere VM | Free-forever compute for backend + DB + Redis |
| **Frontend Hosting** | Vercel / Cloudflare Pages | Free tier |
| **CI/CD** | GitHub Actions | Free minutes |
| **Monitoring** | UptimeRobot | Free tier |

---

## Architecture

```
                [VENDORS / INVOICES DATA INPUT]
                              │
      ┌───────────────────────┼───────────────────────┐
      ▼                       ▼                       ▼
[Manual CSV Upload]     [ERP Sync — Phase 2]    [Inbound Email — Phase 2]
 (React Dropzone)       (Tally ODBC / APIs)     (Gmail API polling)
      │                       │                       │
      └───────────────────────┼───────────────────────┘
                              ▼
                 [Self-hosted Redis Queue / Celery]
                              │
           ┌──────────────────┴──────────────────┐
           ▼                                     ▼
[Self-Declaration + NIC Trader Filter]   [Tesseract OCR → Groq LLM
 (vendor upload, manual spot-check)       structured field extraction]
           │                                     │
           └──────────────────┬──────────────────┘
                              ▼
             [PostgreSQL — user-scoped, multi-tenant]
                              │
                     [Smart Clock Engine]
         (15/45-day deadline calc, dual-cited 43B(h) / 37(2)(g))
                              │
                    [Cash-Priority Optimizer]
             (ranks unpaid invoices by tax+interest saved/₹)
                              │
           ┌──────────────────┴──────────────────┐
           ▼                                     ▼
[CFO/Accountant Dashboard]              [Compliance Exports]
 (Next.js on Vercel/Cloudflare)          (Form 3CD + MSME-1 Excel)
```

### Data Pipeline (Step-by-Step)

1. **Ingest & queue** — a CSV upload writes to `raw_ingestions`; a background job is pushed to Redis.
2. **Vendor classification** — the Celery worker extracts distinct vendor PAN/GSTINs, checks stored Udyam certificates (or triggers a fresh emailed request), applies the NIC 45/46/47 trader filter, and tags each vendor.
3. **Invoice parsing** — for PDF invoices, Tesseract extracts raw text; Groq (primary) structures it into Invoice Date, Amount, GSTIN, Delivery Date.
4. **Clock computation** — the engine calculates the statutory deadline per invoice, applies deemed-acceptance logic, and labels everything with both section citations.
5. **Cash-priority ranking** — the optimizer computes the tax-plus-interest-saved-per-rupee score across all unpaid eligible invoices.
6. **Dashboard & exports** — the CFO dashboard renders exposure and priority; Form 3CD and MSME-1 exports are generated on demand from the same underlying tables.

---

## Project Structure

```
VENDORCLOCK_v2/
├── frontend/                        # Next.js 16 App Router
│   ├── app/
│   │   ├── (app)/                   # Authenticated route group
│   │   │   ├── dashboard/           # CFO exposure & priority dashboard
│   │   │   ├── upload/              # CSV/Excel ingestion page
│   │   │   ├── vendors/             # Vendor list & MSME status management
│   │   │   ├── invoices/            # Invoice list with clock status
│   │   │   ├── exports/             # Form 3CD & MSME-1 export page
│   │   │   └── settings/            # Role-based alerts & SMTP settings
│   │   ├── login/                   # Login page
│   │   └── vendor-status/           # Public vendor self-service portal
│   └── components/                  # Shared UI components
│
├── backend/
│   ├── app/
│   │   ├── api/routes/
│   │   │   ├── auth.py              # Registration, login, JWT
│   │   │   ├── ingestion.py         # CSV/Excel upload & processing
│   │   │   ├── vendors.py           # Vendor CRUD & classification
│   │   │   ├── invoices.py          # Invoice list, dashboard aggregates
│   │   │   ├── exports.py           # Form 3CD & MSME-1 Excel generation
│   │   │   └── settings.py          # SMTP, Slack, alert preferences
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic settings, env vars
│   │   │   ├── database.py          # SQLAlchemy engine & session
│   │   │   └── security.py          # JWT creation/verification
│   │   ├── models/
│   │   │   ├── user.py              # User model + UserRole enum (4 roles)
│   │   │   ├── vendor.py            # Vendor model + classification enums
│   │   │   ├── invoice.py           # Invoice model + clock status enums
│   │   │   └── ingestion.py         # RawIngestion audit trail model
│   │   ├── services/
│   │   │   ├── clock_engine.py      # 15/45-day deadline calculator (core IP)
│   │   │   ├── cash_priority.py     # Cash-Priority Optimizer scoring
│   │   │   ├── vendor_classifier.py # NIC trader exclusion logic
│   │   │   ├── csv_parser.py        # Fuzzy column matching parser
│   │   │   ├── export_service.py    # Form 3CD & MSME-1 Excel builder
│   │   │   ├── email_service.py     # SMTP email templates & sender
│   │   │   └── llm_service.py       # Groq / Gemini LLM extraction
│   │   └── tasks/
│   │       └── celery_app.py        # Celery app, tasks & beat schedule
│   ├── alembic/                     # Database migrations
│   ├── promote_admin.py             # CLI: promote a user to ADMIN role
│   ├── requirements.txt
│   ├── Dockerfile
│   └── docker-compose.yml           # Full local stack (Postgres, Redis, API, Celery)
│
└── VendorClock_Dev_Spec.md          # Full product & engineering specification
```

---

## Local Development Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (for Redis & PostgreSQL) — or use the SQLite dev mode without Docker

### Step 1 — Start Infrastructure

```bash
cd backend
# Starts PostgreSQL and Redis containers
docker compose up -d postgres redis
```

> **SQLite shortcut (no Docker):** Set `DATABASE_URL=sqlite:///./vendorclock.db` in your `.env`. The app auto-creates tables on startup in `development` mode.

### Step 2 — Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # Edit .env with your keys (see Environment Variables below)
```

### Step 3 — Start All Services

You need **three terminal windows** running simultaneously:

**Terminal 1 — FastAPI server:**
```bash
cd backend && source venv/bin/activate
uvicorn app.main:app --reload --port 8000
# API docs available at http://localhost:8000/api/docs
```

**Terminal 2 — Next.js frontend:**
```bash
cd frontend
npm install
npm run dev
# App available at http://localhost:3000
```

**Terminal 3 — Celery worker + beat scheduler:**
```bash
cd backend && source venv/bin/activate
# Worker (processes ingestion, OCR, alert jobs):
celery -A app.tasks.celery_app worker --loglevel=info
# Beat scheduler (runs daily/weekly alert crons) — run in a 4th terminal if needed:
celery -A app.tasks.celery_app beat --loglevel=info
```

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in the values:

| Variable | Description |
|---|---|
| `APP_ENV` | `development` or `production` |
| `SECRET_KEY` | Long random string (≥32 chars) for JWT signing |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT lifetime (default: `60`) |
| `FRONTEND_URL` | e.g. `http://localhost:3000` (for CORS) |
| `DATABASE_URL` | `postgresql://vendorclock:vendorclock@localhost:5432/vendorclock` |
| `REDIS_URL` | `redis://localhost:6379/0` |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) — **PRIMARY, safe for real PAN/GSTIN data** |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) — **FALLBACK / test traffic only** ⚠ |
| `SMTP_HOST` | e.g. `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USERNAME` | Your Gmail address |
| `SMTP_PASSWORD` | 16-character Google App Password |
| `SMTP_FROM_NAME` | Display name (e.g. `VendorClock`) |
| `ALERT_DEFAULT_RECIPIENT` | CFO/Controller email for escalation reports |
| `SLACK_WEBHOOK_URL` | Slack App → Incoming Webhooks URL |
| `RBI_BANK_RATE_PERCENT` | Current RBI bank rate (default: `6.50`) — update when RBI changes it |
| `GST_INCLUDED_IN_TAXABLE_BASE` | `false` (default) — **requires CA confirmation before changing** |
| `DISPUTE_CLOCK_RESET_TRIGGER` | `objection_raised` (default) — **requires CA/lawyer confirmation** |

> ⚠ **Never commit your `.env` file.** It is already in `.gitignore`.

> ⚠ **Gemini privacy warning:** The Gemini free tier trains on submitted prompts by default. Never route real vendor invoices (names, GSTINs, amounts) through it. Use Groq as the primary for all real data; reserve Gemini for test/synthetic traffic only, or run a local model via Ollama.

---

## RBAC — User Roles

VendorClock implements four roles with distinct permissions:

| Role | Who It's For | Permissions |
|---|---|---|
| `ACCOUNTANT` | AP / Finance staff | Default role on registration. Upload CSVs, manage vendors, view dashboard & invoices. |
| `TREASURY_STAFF` | Treasury / read-only finance | Dashboard and invoice read access only — no upload or vendor management. |
| `EXTERNAL_AUDITOR` | CA firm / external auditor | Read-only access to Form 3CD and MSME-1 export views only. |
| `ADMIN` | System administrator | Everything above + SMTP configuration, Slack setup, Celery beat schedule management, and the "Send Test Email" utility. |

New users self-register as `ACCOUNTANT`. Promotion to other roles is done via CLI (see below).

---

## Registering & Promoting an Admin

### 1. Register via the UI

1. Open `http://localhost:3000`
2. Click **Create an account**
3. Fill in your name, email, company name, and password
4. You are now registered as a standard `ACCOUNTANT`

### 2. Promote to Admin

To unlock SMTP configuration and system-level settings, promote your account:

```bash
cd backend
source venv/bin/activate
python promote_admin.py you@company.com
```

Expected output:
```
Success: User you@company.com has been promoted to ADMIN.
```

3. Refresh your browser. You will now see the full **Alerts & Settings** admin panel.

> The same script can promote any registered user — useful for giving a second admin access.

---

## Deployment Notes

The full free-tier production stack runs on:

| Service | Where | Notes |
|---|---|---|
| FastAPI + Celery + Redis + PostgreSQL | Oracle Cloud Always-Free Ampere VM (2 OCPU / 12 GB RAM) | Self-hosted; you own backups and patching. Choose an India-region VM for data residency. |
| Next.js frontend | Vercel or Cloudflare Pages | Free tier; deploy from your GitHub repo. |
| Monitoring | UptimeRobot | Free tier covers uptime pinging. |
| CI/CD | GitHub Actions | Free minutes sufficient for a solo build. |

**The one unavoidable cost:** a domain name (~$8–12/year). Use a free Vercel subdomain while pre-revenue.

**Phase 2 spend priorities (once there's revenue):**
1. A paid Udyam bulk-verification API (Gridlines / Decentro / Deepvue) — removes self-declaration lag.
2. Managed PostgreSQL (Supabase / Neon Pro) — removes self-hosting/backup risk.

---

## Legal Disclaimer

VendorClock is a product and engineering tool — **not legal or tax advice.**

Three items in the clock and calculation logic **must be confirmed with a qualified CA or lawyer** before the numbers they produce reach a customer's tax auditor. Until then, they are controlled by environment-variable flags:

1. **Dispute/objection-reset trigger** (`DISPUTE_CLOCK_RESET_TRIGGER`) — the exact legal trigger and reset-date for the deemed-acceptance clock when a written objection is raised.
2. **GST in taxable base** (`GST_INCLUDED_IN_TAXABLE_BASE`) — whether GST is included or excluded from the disallowed amount used in the cash-priority optimizer.
3. **Section transition handling** — correct treatment of invoices straddling the FY 2025-26 (43B(h)) → FY 2026-27 (37(2)(g)) year-end boundary.

These flags show visible warnings in the UI and on exports until they are confirmed and updated.
