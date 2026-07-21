# VendorClock — Product & Engineering Specification
**A buyer-side compliance and cash-priority tool for Section 43B(h) / Section 37(2)(g) of the Income Tax Act**

---

## 1. The Core Problem

Introduced to protect the working capital of Micro and Small Enterprises (MSEs), **Section 43B(h)** of the Income Tax Act mandates that any buyer of goods or services from a registered MSE pay within strict statutory timelines:

- **Within 15 days** if there is no written agreement.
- **Within the agreed period, capped at 45 days**, if there is a written agreement — counted from the date of acceptance, or deemed acceptance if the buyer raises no written objection within 15 days of delivery.

> **Naming note (load-bearing, not cosmetic):** under the Income Tax Act, 2025 (effective April 1, 2026), this same provision carries forward as **Section 37(2)(g)**. FY 2025-26 filings still cite 43B(h); FY 2026-27 onward cite 37(2)(g). The rule is unchanged — only the citation is. Every dashboard label, export, and piece of customer-facing copy must carry **both citations** side by side.

### Financial consequences of a missed deadline
1. **Immediate tax disallowance** — the unpaid expense is added back to taxable income for that financial year; deduction is deferred to the year actually paid.
2. **Compound interest penalty** — 3x the RBI bank rate, compounding monthly, payable to the vendor.
3. **Non-deductible interest** — that penalty interest cannot itself be claimed as a business expense.
4. **Two separate mandatory disclosures** — Form 3CD (tax audit, all delayed MSE dues) and Form MSME-1 (ROC half-yearly filing, dues to Micro/Small suppliers outstanding beyond 45 days; **Medium enterprises are excluded from MSME-1**).

### Why this doesn't get handled today
Most companies run SAP, Oracle, Tally, or Zoho with default credit cycles of 60–120 days. These systems are blind to:
- Which vendors are Udyam-registered, and whether they're Micro/Small (Medium is exempt) or excluded traders (see below)
- Exactly when the 15- or 45-day clock started on each invoice
- Which registered "MSMEs" are actually **wholesale/retail traders under NIC codes 45, 46, 47** — these are Udyam-eligible for Priority Sector Lending only, and are **explicitly excluded from Section 15 payment protection**, so 43B(h)/37(2)(g) does not apply to their invoices at all

Finance teams currently reconstruct all of this by hand in Excel every quarter.

### The competitive reality (be honest about this before building)
This space is not empty. Tally already ships ageing reports built around this rule; ERPNext's India Compliance app has an open feature request for the same tracking plus MSME-1 export; free public calculators already do invoice-level 15/45-day math; and at least one GST-invoicing tool already bundles "43B(h) tracking" as a feature. Basic clock-tracking is becoming commodity. **The defensible product sits one layer up: cash-priority optimization and the audit-export workflow, not the vendor tagging.**

---

## 2. The Solution: VendorClock

VendorClock is a lightweight, read-only compliance and cash-priority overlay sold directly to CFOs, Controllers, and tax heads at companies that buy from MSE vendors. It ingests the purchase register, runs a live statutory clock on every invoice, and tells treasury exactly **who to pay first** when cash is limited — then generates the audit paperwork the CA needs at filing time.

By targeting the **buyer**, the product reaches the party with both the budget and the authority to fix the problem — not the vendor, who has neither.

**Where the product actually differentiates**, given the competitive landscape above:
- The **cash-priority optimizer** (Module 4) — ranking invoices by tax-plus-interest saved per rupee released. Nothing free does this well.
- The **Form 3CD + MSME-1 one-click export** (Modules 6, 8) — the primary hook for CA firms managing dozens of clients.
- The **CFO escalation and exposure dashboard** (Module 4/5) — built for multi-thousand-invoice enterprises, not the SMB self-serve segment the free calculators serve.

---

## 3. Product Specification & Features

### Module 1 — Ledger & Invoice Ingestion
- **CSV/Excel parser**: mapping-free upload of the purchase/payables register (exported from Tally/Zoho/SAP), with fuzzy-match column detection for Vendor Name, PAN/GSTIN, Invoice Number, Invoice Date, Pending Amount. This alone is sellable as MVP.
- **Inbound email inbox**: a dedicated address vendors/AP staff forward invoice PDFs to; OCR + LLM extraction pulls Invoice Date, Amount, Vendor GSTIN, Delivery Date.
- **Phase 2**: direct ERP sync (Tally ODBC/XML, Zoho Books API, SAP Business One Service Layer) — add once there are paying customers asking for it.

### Module 2 — Vendor MSME-Status & Exclusions Engine
Multi-step validation for every vendor:

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
[CONFIRMED ELIGIBLE SUPPLIER] → Add to Active Compliance Clock Engine
```

- **Self-declaration flow (primary, free)**: one-time emailed link, vendor uploads Udyam certificate, stored, re-verified annually.
- **The trader filter is a hard requirement, not an edge case**: NIC codes 45/46/47 are Udyam-eligible for Priority Sector Lending only — Section 15 protection, and therefore 43B(h)/37(2)(g), does not extend to them. Parse the NIC code off the uploaded certificate (or ask the vendor to state it) and exclude automatically.
- **Manual spot-check path**: periodic sampling against the free public search at udyamregistration.gov.in for audit defense.
- **Phase 2 upgrade**: swap in a paid bulk-verification API (Gridlines / Decentro / Deepvue — all offer instant Udyam lookup by PAN/GSTIN/URN) once revenue justifies it. This removes the self-declaration lag; nothing else in the architecture changes.

### Module 3 — The 15/45-Day Compliance Clock Engine (core IP)
1. **Contract test**: written agreement on file? → deadline = acceptance date + agreed term, capped at 45 days. No agreement? → deadline = acceptance date + 15 days. (This is a written-agreement branch, **not** a goods-vs-services split.)
2. **Deemed acceptance**: if the buyer raises no written objection within 15 days of delivery, the delivery date becomes the legal acceptance date the clock runs from.
3. **Dispute handling**: if a written objection is raised, the clock pauses until the dispute is resolved. **⚠ Dev note: get a CA/lawyer to confirm the exact trigger and reset-date logic here before this ships — it's the one piece of clock behavior not fully settled in public guidance.**
4. **Live status**: green (safe) / amber (approaching deadline) / red (overdue — interest compounding, disallowance active).
5. **Dual citation**: every date, label, and export carries both "Section 43B(h)" and "Section 37(2)(g), Income Tax Act 2025" — never one alone.

### Module 4 — CFO Cash-Priority & Exposure Dashboard
- Total ₹ exposure at risk of disallowance by March 31.
- Effective tax cost of that exposure (amount × applicable rate).
- Running non-deductible compound-interest accrual per vendor/invoice (3x RBI rate, compounding monthly).
- **Cash-Priority Optimizer** — ranks unpaid invoices by tax-and-interest saved per rupee of cash released:

  ```
  Score = (Invoice Amount × Effective Tax Rate + Accrued Non-Deductible Interest) / Amount Required to Clear Invoice
  ```

- **Capex exclusion**: invoices tagged as asset purchases are excluded from the disallowance engine.
- **⚠ Dev note**: whether GST is included or excluded from the taxable base in this calculation needs CA confirmation before the number ships to a customer's auditor — don't hard-code an assumption here.

### Module 5 — Internal Alerts & Escalation (buyer-side only)
- Daily email/Slack nudges to the AP owner: "these N invoices cross the deadline in 5 days, ₹X exposure."
- Weekly CFO/Controller escalation report, intensifying as March 31 approaches.
- Never vendor-facing nagging — alerts are internal only.

### Module 6 — Form 3CD Audit Export
One-click, tax-audit-ready export: vendor name, Udyam number, invoice date, (deemed) acceptance date, due date, actual payment date, days delayed, disallowed principal, MSMED compound interest — with both statutory citations printed on the export.

### Module 7 — Vendor-Facing Status Page (optional, light-touch)
A simple link a vendor can check: "your invoice is on file, due on [date]." Pure status visibility — not a dunning/chasing mechanism, so it doesn't strain the buyer-vendor relationship.

### Module 8 — Form MSME-1 ROC Export
Half-yearly disclosure of dues to Micro/Small suppliers outstanding beyond 45 days, generated from the same underlying data as Module 6. **Medium enterprises are excluded from this filing** — confirmed, not a gray area, so no special handling is needed for them beyond correct Udyam classification in Module 2.

---

## 4. Tech Stack (fully free)

| Layer | Technology | Why / Free-Tier Reality |
|---|---|---|
| **Frontend** | Next.js (React) + TailwindCSS + shadcn/ui | Rapid component-driven UI; deploy free on **Vercel** or **Cloudflare Pages** |
| **Backend** | Python (FastAPI) | Async-native, integrates cleanly with Pandas and OCR/LLM wrappers |
| **Backend hosting** | **Self-hosted on an Oracle Cloud "Always Free" Ampere VM** | Free-forever compute (2 OCPU / 12GB RAM as of mid-2026 — Oracle silently halved this from 4/24 in June 2026, and regional capacity isn't guaranteed, so verify availability first). Avoids Render/Railway's free-tier spin-down-on-idle behavior, which would break a background clock engine that needs to run continuously |
| **Database** | PostgreSQL, self-hosted on the same free VM | Avoids Supabase's 500MB / Neon's 0.5GB free-tier ceilings — up to 200GB block storage included instead. You own backups/patching in exchange |
| **Task queue** | Celery + Redis, self-hosted on the same VM | Handles async Udyam checks, OCR jobs, email ingestion — no managed-service bill |
| **OCR** | **Tesseract** (open source) | Free forever; weaker than paid Document-AI-style services on messy scans — build a manual-correction fallback into the UI for low-confidence extractions |
| **LLM extraction** | **Groq free tier** (Llama/Qwen, fast, rate-limited) primary; **Google AI Studio / Gemini 2.5 Flash free tier** as fallback only | **Read this before wiring it up**: Gemini's free tier trains on submitted prompts by default — a real privacy concern when the data is vendor invoices with GSTINs and amounts. Prefer Groq (no-training default) for anything with real customer data; route only non-sensitive/test traffic to Gemini, or run a small model locally via **Ollama** for anything sensitive |
| **Vendor KYC** | Self-declaration + certificate upload (free) | No free bulk/live Udyam verification API exists — every provider (Gridlines, Decentro, Deepvue) charges per lookup. Self-declaration is the correct free substitute; budget for the annual re-verification workflow it implies |
| **Internal alerts** | Free SMTP email (Gmail/Workspace) + **Slack free tier** | WhatsApp Business API is **no longer meaningfully free** since Meta's 2025 pricing change — only customer-initiated "service" conversations are free, and even those usually sit behind a paid BSP subscription. Excluded from the free MVP; reintroduce as a paid Phase 2 add-on only on customer request |
| **Inbound invoice email** | Free Gmail account + **Gmail API** (free read access), or **Cloudflare Email Routing** (free) | Free quotas comfortably cover MVP invoice volume |
| **Domain** | — | The one unavoidable cost, ~$8–12/year. Use a free Vercel/Render subdomain while pre-revenue if even this is out of budget |
| **Monitoring** | **UptimeRobot free tier** | Sufficient at this scale |
| **CI/CD & source control** | **GitHub free tier + GitHub Actions free minutes** | Generous enough for a solo build |

**Phase 2 spend priority** (first two things to pay for once there's revenue): (1) a paid Udyam bulk-verification API — removes self-declaration lag; (2) managed Postgres — removes self-hosting/backup risk. Everything else can stay free indefinitely.

---

## 5. System Architecture & Data Pipeline

### Architecture (modular monolith — right-sized for a solo build)

```
                 [VENDORS / INVOICES DATA INPUT]
                               │
       ┌───────────────────────┼───────────────────────┐
       ▼                       ▼                       ▼
 [Manual CSV Upload]     [ERP Sync — Phase 2]    [Free Gmail Inbox]
  (React Dropzone)       (Tally ODBC / APIs)     (Gmail API polling)
       │                       │                       │
       └───────────────────────┼───────────────────────┘
                               ▼
                  [Self-hosted Redis Queue / Celery]
                    (on the Oracle free VM)
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
 [Self-Declaration + NIC Trader Filter]   [Tesseract OCR → Groq/Gemini
  (vendor upload, manual spot-check)       structured field extraction]
            │                                     │
            └──────────────────┬──────────────────┘
                               ▼
              [Self-hosted PostgreSQL (same free VM)]
                               │
                      [Smart Clock Engine]
          (15/45-day milestone calc, dual-cited 43B(h) / 37(2)(g))
                               │
                     [Cash-Priority Optimizer]
              (ranks unpaid invoices by tax+interest saved/₹)
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
 [CFO/Accountant Dashboard]              [Compliance Exports]
  (Next.js on Vercel/Cloudflare)          (Form 3CD + MSME-1)
```

### Data pipeline, step by step

1. **Ingest & queue** — a CSV upload or inbound email writes to a `raw_ingestions` table; a background job is pushed to the self-hosted Redis queue.
2. **Vendor classification** — the worker extracts distinct vendor PAN/GSTINs, checks against stored self-declared Udyam certificates (or triggers a fresh emailed request if none on file), applies the NIC 45/46/47 trader filter, and tags each vendor `ELIGIBLE`, `EXCLUDED_TRADER`, `EXCLUDED_MEDIUM`, or `PENDING_DECLARATION`.
3. **Invoice parsing** — for email-ingested PDFs, Tesseract extracts raw text, then Groq (primary) or Gemini (fallback, non-sensitive only) structures it into Invoice Date, Amount, GSTIN, Delivery Date.
4. **Clock computation** — the engine calculates the statutory deadline per invoice from the contract-test branch (15 vs. 45-day-capped) and applies deemed-acceptance logic, dual-labeled with both section citations.
5. **Cash-priority ranking** — the optimizer computes the tax-plus-interest-saved-per-rupee score across all unpaid eligible invoices and surfaces the ranked payment queue.
6. **Dashboard & exports** — the CFO dashboard renders exposure and priority; Form 3CD and MSME-1 exports are generated on demand from the same underlying tables.

---

## 6. Security & Compliance Posture

- **True read-only architecture** — no payment-aggregator, banking, or NBFC integration; the platform parses and analyzes, it never moves money. No payment-license triggers.
- **Data residency** — self-hosting on your own Oracle free VM keeps all data under your direct control by default (arguably tighter than handing it to a third-party managed service); choose an India-region VM where capacity allows.
- **LLM data-handling caveat (new, specific to the free stack)** — Gemini's free tier trains on submitted prompts by default. Real vendor invoice data (names, GSTINs, amounts) should not routinely pass through it. Default to Groq (no-training) or a locally-run Ollama model for anything containing real customer data; reserve Gemini for test/synthetic traffic only.
- **No autonomous action** — every alert is informational; every export requires a human click.
- **RBAC** — separate roles for Treasury Staff (dashboard read), Accountants (CSV upload), External Tax Auditors (read-only access to the Form 3CD/MSME-1 export view only).

### Legal items requiring CA/lawyer sign-off before shipping (do not code these on assumption)
1. The exact dispute/objection-reset trigger for the deemed-acceptance clock (Module 3).
2. Whether GST is included or excluded from the taxable base used in the disallowance calculation (Module 4).
3. Handling of invoices that straddle the Section 43B(h) → Section 37(2)(g) transition at FY 2025-26 / FY 2026-27 year-end.

*This document is a product and engineering spec, not legal or tax advice — the three items above specifically should be confirmed with a qualified CA or lawyer before the numbers they affect reach a customer's tax auditor.*
