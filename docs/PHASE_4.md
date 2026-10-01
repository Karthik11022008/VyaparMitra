# Phase 4: Real File Ingestion, Reconciliation Workflow & Report Export

**Project:** VyaparMitra (व्यापार मित्र)  
**Hackathon:** BHARAT AGENTIC 2026 (12-Hour Challenge)  
**Status:** Phase 4 Complete & Verified  

---

## 1. Architectural Overview

Phase 4 transforms VyaparMitra from a static demo-dataset tool into an authentic, end-to-end MSME reconciliation workflow capable of processing heterogeneous real-world business files:

```
[ User Uploads: Purchase Register (CSV/XLSX) + GSTR-2B (CSV/JSON/XLSX) ]
                                   │
                                   ▼
        ┌──────────────────────────────────────────────────┐
        │   Security & Content Sniffing Guard              │
        │   - Size <= 10MB, Sanitized Filenames (No Path   │
        │     Traversal), Format Verification              │
        └──────────────────────────┬───────────────────────┘
                                   │
                                   ▼
        ┌──────────────────────────────────────────────────┐
        │   Header Normalizer & Column Alias Mapper        │
        │   - Maps ERP variances (e.g. 'Supplier GSTIN' or │
        │     'Invoice No' -> canonical schema keys)       │
        └──────────────────────────┬───────────────────────┘
                                   │
                                   ▼
        ┌──────────────────────────────────────────────────┐
        │   Deterministic Validator & Preprocessor         │
        │   - Luhn Mod 36 Checksum, Decimal Precision,     │
        │     Non-negative constraints, Duplication Checks │
        └──────────────────────────┬───────────────────────┘
                                   │
                                   ▼
        ┌──────────────────────────────────────────────────┐
        │   Reconciliation Session Store (SQLite + Memory) │
        │   - Unique Session ID: sess-<uuid>               │
        │   - Audit Event Log: FILE_UPLOADED, VALIDATED    │
        └──────────────────────────┬───────────────────────┘
                                   │
                  ┌────────────────┴────────────────┐
                  ▼                                 ▼
   ┌──────────────────────────────┐  ┌──────────────────────────────┐
   │ Deterministic Recon Engine   │  │ AI Agent Orchestrator        │
   │ - Exact Matching             │  │ - Operates on real session   │
   │ - Fuzzy RapidFuzz (>= 85%)   │  │ - Evidence-based findings    │
   │ - Section 50 Interest        │  │ - Draft dispute notices      │
   │ - At-Risk ITC Calculations   │  │ - Human-in-the-Loop review   │
   │ *(Zero LLM Arithmetic)*      │  └──────────────┬───────────────┘
   └──────────────┬───────────────┘                 │
                  │                                 │
                  ▼                                 ▼
   ┌──────────────────────────────┐  ┌──────────────────────────────┐
   │ Report Export Engine         │  │ Immutable Audit Trail Log    │
   │ - Audit-friendly CSV Export  │  │ - Records Notice approvals,  │
   │ - Styled HTML Audit Document │  │   rejections, & timestamps   │
   └──────────────────────────────┘  └──────────────────────────────┘
```

---

## 2. Supported File Formats & Ingestion Pipeline

### Purchase Register
* **CSV:** Standard comma-separated or tab-separated text, with support for comment lines (`#`).
* **XLSX:** Microsoft Excel spreadsheets parsed via `pandas` and `openpyxl`.

### GSTR-2B Statement
* **CSV:** Local/ERP exported GSTR-2B representations.
* **JSON:** Dual support for:
  1. Flat arrays of invoice objects (`[{ ... }, { ... }]`).
  2. Official government GST portal schema featuring nested `data.b2b` supplier structures with `ctin`, `inv` arrays, and `items.itm_det` taxable breakdowns.
* **XLSX:** Multi-row tax invoice worksheets.

---

## 3. Dynamic Column Alias Mapping

To accommodate heterogeneous accounting software (Tally, Zoho Books, Busy, Marg, SAP), VyaparMitra implements deterministic alias mapping without guessing:

| Canonical Field | Supported Real-World Column Aliases | Mandatory |
| :--- | :--- | :--- |
| `supplier_gstin` | `supplier_gstin`, `supplier gstin`, `gstin`, `vendor_gstin`, `supplier_tin`, `gstin/uin of supplier`, `ctin` | Yes |
| `invoice_number` | `invoice_number`, `invoice no`, `invoice_no`, `inv_no`, `bill_no`, `document_number`, `inum` | Yes |
| `invoice_date` | `invoice_date`, `invoice date`, `inv_date`, `bill_date`, `document_date`, `idt` | Optional |
| `taxable_value` | `taxable_value`, `taxable amount`, `taxable_amount`, `taxable`, `assessable_value`, `txval` | Yes |
| `cgst` | `cgst`, `cgst_amount`, `central_tax`, `central tax`, `camt` | Optional |
| `sgst` | `sgst`, `sgst_amount`, `state_tax`, `state tax`, `utgst`, `samt` | Optional |
| `igst` | `igst`, `igst_amount`, `integrated_tax`, `integrated tax`, `iamt` | Optional |
| `total_value` | `total_value`, `total amount`, `invoice_value`, `val`, `grand total` | Optional |

If required columns (`supplier_gstin`, `invoice_number`, `taxable_value`) are missing, the system returns an informative validation error detailing detected headers vs. required headers.

---

## 4. Rigorous Data Validation Rules

1. **GSTIN Validation:** Verified against the statutory 15-character Indian structure (2-digit state code + 10-char PAN + entity number + 'Z' + Luhn Mod 36 checksum).
2. **Decimal Precision:** Financial amounts are converted strictly using Python's `Decimal` type to prevent binary floating-point rounding errors.
3. **Non-Negative Constraints:** Negative taxable values or taxes are blocked.
4. **Internal Duplicate Detection:** Duplicate entries within the same ledger are flagged before matching.

---

## 5. Security & Safety Controls

* **Path Traversal Protection:** Filenames are stripped of directory separators (`/`, `\`, `..`) via `Path(filename).name` and regex sanitization.
* **Storage Isolation:** Files are stored strictly in `data/uploads/`, which is ignored by `.gitignore`.
* **Zero Path Leakage:** Internal operating system filesystem paths are never returned in API payloads.
* **Upload Size Guard:** Enforces `MAX_UPLOAD_SIZE_BYTES = 10MB`, aborting oversized payloads with HTTP 413.
* **Empty File Guard:** Files with 0 bytes or header-only data are rejected with HTTP 400.

---

## 6. Audit Trail & Session Management

Every reconciliation session is tracked in SQLite (`data/vyaparmitra.db`):
* `reconciliation_sessions`: Records `session_id`, creation timestamp, filenames, row counts, status, and summary JSON.
* `audit_events`: Immutable audit trail recording:
  - `FILE_UPLOADED`
  - `FILE_VALIDATED`
  - `RECONCILIATION_STARTED`
  - `RECONCILIATION_COMPLETED`
  - `AGENT_ANALYSIS_STARTED`
  - `AGENT_ANALYSIS_COMPLETED`
  - `NOTICE_DRAFT_CREATED`
  - `NOTICE_APPROVED`
  - `NOTICE_REJECTED`

---

## 7. Report Export

* **CSV Export (`/api/reconciliation/export/{session_id}/csv`):** Detailed spreadsheet containing metadata, summary metrics, discrepancy breakdown, reason, and statutory provisions.
* **HTML Audit Report (`/api/reconciliation/export/{session_id}/html`):** Standalone, professional printable audit document with metrics cards, discrepancy table, and statutory disclaimer.

---

## 8. Agent Integration on Uploaded Data

When `session_id` is supplied to `POST /api/agent/analyze`:
1. The AI Agent pulls the verified reconciliation results for that exact session.
2. The agent interprets the evidence (at-risk ITC, missing invoices, amount differences) without hallucinating numbers.
3. Drafts supplier dispute notices citing statutory provisions with `DRAFT — REQUIRES HUMAN REVIEW`.
4. Human actions (`Approve`, `Reject`, `Edit`) trigger audit events recorded in SQLite.

---

## 9. Verification & Test Suite

All 50 unit and integration tests pass with 100% success:
* `test_file_ingestion.py` (9 tests)
* `test_reconciliation_workflow.py` (2 tests)
* `test_report_export.py` (2 tests)
* `test_audit_and_agent.py` (1 test)
* `test_agent.py` (8 tests)
* `test_matching_engine.py` (8 tests)
* `test_gstin_validator.py` (6 tests)
* `test_interest_calculator.py` (5 tests)
* `test_normalization.py` (4 tests)
* `test_tax_calculator.py` (3 tests)
* `test_reconciliation_api.py` (1 test)
* `test_health.py` (1 test)

**Frontend Build:** Vite production build passes in 155ms with zero warnings.
