# VyaparMitra (व्यापार मित्र)

**Autonomous MSME GST Reconciliation & Dispute-Resolution Agent**  
*Built for BHARAT AGENTIC 2026 (12-Hour Hackathon)*

---

## Problem Statement

Micro, Small, and Medium Enterprises (MSMEs) in Bharat lose billions of rupees in blocked working capital due to mismatches between internal purchase books and GSTR-2B tax returns. Under Section 16(2)(aa) of the CGST Act, buyers cannot claim Input Tax Credit (ITC) if their suppliers fail to report outward supplies, while Section 50 imposes steep interest penalties on incorrect claims. Small business owners lack dedicated tax teams to manually reconcile messy, heterogeneous invoices or navigate dispute communications with delinquent vendors. VyaparMitra is designed as an agentic assistant that ingests real business spreadsheets/JSON, executes deterministic statutory tax calculations, orchestrates multi-step AI reasoning, and drafts auditable, human-reviewable supplier dispute communications.

---

## High-Level Architecture (Phase 4)

```
User (Accountant / Business Owner)
               │
               ▼
┌────────────────────────────────────────────────────────┐
│         Frontend UI (React 19 + Vite @ 5173)           │
│  - System Health & Active Session Banner               │
│  - Real File Upload: Purchase (CSV/XLSX) & 2B (CSV/JSON)│
│  - Live Validation Status & Ingestion Previews         │
│  - Reconciliation Results Dashboard & Filterable Table │
│  - Export Buttons (CSV & Standalone HTML Audit Report) │
│  - Agent Execution Trace & Evidence-Based Briefings    │
│  - Human-in-the-Loop Controls (Review/Edit/Approve/Reject)
│  - Real-Time Immutable Audit Trail Viewer              │
└──────────────────────────┬─────────────────────────────┘
                           │ HTTP REST (CORS enabled)
                           ▼
┌────────────────────────────────────────────────────────┐
│            Backend API (FastAPI @ 8000)                │
│  - POST /api/reconciliation/upload/purchase-register   │
│  - POST /api/reconciliation/upload/gstr2b              │
│  - POST /api/reconciliation/run                        │
│  - GET  /api/reconciliation/export/{session_id}/csv    │
│  - GET  /api/reconciliation/export/{session_id}/html   │
│  - GET  /api/reconciliation/audit/{session_id}         │
│  - POST /api/agent/analyze                             │
│  - POST /api/agent/notice/{notice_id}/action           │
└──────────────────────────┬─────────────────────────────┘
                           │
            ┌──────────────┴──────────────┐
            ▼                             ▼
┌────────────────────────┐   ┌───────────────────────────┐
│ Gemini Agentic Engine  │   │  Deterministic GST Core   │
│  - google-genai SDK    │   │  - Header Alias Normalizer│
│  - Request Parser      │   │  - Luhn Mod-36 GSTIN Val. │
│  - Workflow Planner    │   │  - Multi-Stage Matcher    │
│  - Dispute Notice Drafter  │  - Python Decimal Tax Calc│
│  *(ZERO ARITHMETIC)*   │   │  - Section 50 Interest    │
└────────────────────────┘   │  - Statutory Rules Catalog│
                             └─────────────┬─────────────┘
                                           │
                                           ▼
                             ┌───────────────────────────┐
                             │ SQLite Database           │
                             │  - Sessions & Audit Trail │
                             └───────────────────────────┘
```

---

## Development Setup

### Prerequisites
* Python 3.14+ with active virtual environment (`.\.venv`)
* Node.js v24+ and npm v11+
* Git 2.55+
* (Optional) `GEMINI_API_KEY` for live Gemini 2.5 Flash orchestration (graceful deterministic fallback if omitted)

### Backend Setup & Execution
1. Activate virtual environment or use `.\.venv\Scripts\python.exe`.
2. Start the FastAPI development server:
   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
3. Test health:
   ```powershell
   curl http://localhost:8000/api/health
   ```

### Frontend Setup & Execution
1. Navigate to the `frontend` directory:
   ```powershell
   cd frontend
   ```
2. Start the Vite development server:
   ```powershell
   npm run dev
   ```
3. Open `http://localhost:5173` in your browser.

---

## Current Status: Production Ready (Phase 4 & UI Redesign Complete)

* **Phase 1 (Foundation):** Full-stack FastAPI + React/Vite baseline established.
* **Phase 2 (Deterministic Core):** Implemented and verified (28 tests).
* **Phase 3 (Agent Orchestration & HITL):** Implemented and verified (36 tests).
* **Phase 4 (Real File Ingestion, Audit Trail & Export):** Fully implemented and verified (54 tests total).
  * **Real File Ingestion:** Supports Purchase Registers in CSV and XLSX, and GSTR-2B in CSV, JSON (including official portal schema), and XLSX.
  * **Dynamic Alias Mapping:** Normalizes real-world ERP column conventions without guessing.
  * **Deterministic Validation:** Enforces structural GSTIN Luhn Mod 36 checksums, positive Decimal amounts, date formats, and duplicate checks.
  * **Unified Matching Engine:** The same deterministic matching engine reconciles both uploaded business records and synthetic demo datasets.
  * **Report Export:** Instant generation of audit-friendly CSV reports and printable HTML audit certificates with state-aware UX and session caching.
  * **Immutable Audit Trail:** Chronological and cryptographic logging of all ingestion, reconciliation, and agent actions in SQLite.
  * **Full Agent Integration:** The AI Agent operates directly on the user's active uploaded session.
  * **Modern 2026 Fintech UI/UX:** Dual theme (Graphite Dark & Crisp Neutral Light), 6 specialized workspaces, interactive side-over Evidence Inspector drawer, and real-time execution lifecycle tracker.

---

## Disclaimers

> **VyaparMitra Statutory Disclaimer:**  
> VyaparMitra is an accounting and reconciliation assistance system. It does not constitute statutory legal advice. All supplier communications require human review and approval.

* **No Live GSTN Connection:** This application does not connect to live GSTN government production APIs.
* **Local Processing:** All uploaded datasets are processed securely and locally.
