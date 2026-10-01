# VyaparMitra (व्यापार मित्र)

**Autonomous MSME GST Reconciliation & Dispute-Resolution Agent**  
*Built for BHARAT AGENTIC 2026 (12-Hour Hackathon)*

---

## Problem Statement

Micro, Small, and Medium Enterprises (MSMEs) in Bharat lose billions of rupees in blocked working capital due to mismatches between internal purchase books and GSTR-2B tax returns. Under Section 16(2)(aa) of the CGST Act, buyers cannot claim Input Tax Credit (ITC) if their suppliers fail to report outward supplies, while Section 50 imposes steep interest penalties on incorrect claims. Small business owners lack dedicated tax teams to manually reconcile messy, heterogeneous invoices or navigate protracted dispute communications with delinquent vendors. VyaparMitra is designed as an agentic assistant that understands reconciliation discrepancies, executes deterministic statutory tax calculations, and drafts auditable, human-reviewable supplier dispute communications.

---

## High-Level Architecture (Phase 1)

```
User (Accountant / Business Owner)
               │
               ▼
┌───────────────────────────────────────────────┐
│     Frontend UI (React 19 + Vite @ 5173)      │
│  - Status dashboard & roundtrip health check  │
└──────────────────────┬────────────────────────┘
                       │ HTTP REST (CORS enabled)
                       ▼
┌───────────────────────────────────────────────┐
│        Backend API (FastAPI @ 8000)           │
│  - /api/health endpoint                       │
│  - Structured Pydantic validation             │
└──────────────────────┬────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────┐
│    SQLite Database (data/vyaparmitra.db)      │
│  - Foundation audit sessions table            │
└───────────────────────────────────────────────┘
```

---

## Development Setup

### Prerequisites
* Python 3.14+ with active virtual environment (`.\.venv`)
* Node.js v24+ and npm v11+
* Git 2.55+

### Backend Setup & Execution
1. Ensure the virtual environment is activated or execute using `.\.venv\Scripts\python.exe`.
2. Start the FastAPI development server:
   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
3. Test backend health:
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

## Current Status: Phase 1 (Foundation Complete)

* **Phase 1 Foundation:** Fully built and verified.
* **Backend:** FastAPI service with deterministic SQLite initialization and CORS configured.
* **Frontend:** Vite React application displaying service health and connectivity state.
* **Database:** SQLite schema foundation established (`agent_sessions`).
* **Test Suite:** Automated backend health test passing via `pytest`.

> [!IMPORTANT]
> **Explicit Notice:** Advanced agent functionality (multimodal invoice ingestion, LLM orchestration, fuzzy string matching, Section 50 interest calculations, and automated vendor dispute notice drafting) is **NOT** yet implemented. This repository currently contains only the verified Phase 1 full-stack foundation.
