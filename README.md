# VyaparMitra (व्यापार मित्र)

**AI-Powered MSME GST Reconciliation, Supplier Risk Intelligence & Dispute Resolution Copilot**<br/>
*Built for Bharat MSMEs • Zero-LLM-Math Architecture • Human-in-the-Loop Governance*

[![Backend Tests](https://img.shields.io/badge/pytest-107%2F107%20passed-brightgreen.svg)]()
[![Frontend Build](https://img.shields.io/badge/vite%20build-clean-brightgreen.svg)]()
[![Architecture](https://img.shields.io/badge/Agentic-Dynamic%20Tools%20%2B%20HITL-blue.svg)]()
[![License](https://img.shields.io/badge/License-MIT-purple.svg)]()

---

## 1. Executive Summary & Problem Statement

MSMEs and finance teams can lose time and working capital when purchase records and GSTR-2B data contain discrepancies.

### Key Statutory Drivers in India
- **Section 16(2)(aa) of the CGST Act:** A taxpayer cannot claim Input Tax Credit (ITC) unless the supplier has accurately reported the invoice in their GSTR-1 / IFF and the details appear in the buyer's auto-generated GSTR-2B.
- **Section 50(1) Interest Liability:** Claiming ineligible or unreflected ITC exposes businesses to 18% per annum mandatory statutory interest penalties from the date of claim until reversal.
- **Rule 37A Reversal:** Failure of suppliers to file GSTR-3B requires buyers to reverse ITC with statutory interest.
- **DRC-01B Intimations:** Discrepancies between ITC claimed in GSTR-3B and available in GSTR-2B trigger automated departmental notices demanding payment or detailed explanation.

### The Problem for Small Businesses
MSMEs rarely have dedicated in-house tax teams. Business owners and bookkeepers grapple with heterogeneous spreadsheets (Tally, Busy, Excel, CSV), inconsistent invoice numbering conventions, rounding variances, and uncooperative or non-compliant suppliers.

---

## 2. The VyaparMitra Solution

**VyaparMitra** is a production-grade, agentic GST reconciliation and counterparty risk intelligence platform designed specifically for Indian MSMEs:

1. **Heterogeneous File Ingestion & Deterministic Matching:** Normalizes varying ERP headers, validates GSTINs with Luhn Mod-36 checksums, and reconciles purchase books against GSTR-2B with sub-penny precision.
2. **Deterministic Supplier Risk Intelligence:** Classifies counterparty risks (0–100 score) into LOW, MEDIUM, HIGH, and CRITICAL risk tiers using 100% deterministic rules—identifying chronic non-compliance without LLM hallucination.
3. **Multi-Step Agentic Reasoning & Tool Selection:** Deconstructs complex compliance inquiries into structured plans, iteratively invoking deterministic tools (max 4 steps) with cycle detection and bounded execution.
4. **Persistent "Ask VyaparMitra" Copilot:** A drawer-based, session-aware conversational assistant backed by SQLite storage that supports multi-turn dialogue, pronoun resolution, and workspace persistence.
5. **Human-in-the-Loop (HITL) Dispute Notices:** Formulates Section 16(2)(aa) / Rule 37A communication notices with strict `DRAFT — REQUIRES HUMAN REVIEW` watermarks, enabling accountants to review, edit, and approve notices before dispatch.

---

## 3. Target Users

- **MSME Business Owners & Founders:** Protect working capital, prevent ITC blockage, and identify risky suppliers before clearing payments.
- **Accountants & Tax Practitioners:** Automate tedious monthly reconciliation runs, generate immutable audit trails, and produce formal dispute notices in seconds.
- **CFOs & Finance Teams:** Monitor enterprise-wide counterparty risk exposure and maintain statutory audit readiness.

---

## 4. Key Architectural Pillars

### The Zero-LLM-Math Principle
> **Architectural Guardrail:** Large Language Models are strictly prohibited from calculating numbers, aggregating tax totals, scoring supplier risks, or computing interest penalties.

All computations—including fuzzy matching, tax difference calculation, Section 50 interest at 18% p.a., and supplier risk scores—are executed in Python with `Decimal` fixed-point arithmetic and deterministic SQL queries. The LLM (Gemini 2.5 Flash) is utilized exclusively for query interpretation, structured tool planning, and natural language explanation grounded strictly in verified tool observations.

### Multi-Step Execution Loop
```
User Question
    │
    ▼
Understand & Intent Classification
    │
    ▼
Create Structured Plan
    │
    ▼
Select Tool & Validate Arguments (Tool Contract Adapter)
    │
    ▼
Execute Deterministic Tool  <─── Cycle Detection (max 4 steps)
    │
    ▼
Store Verified Tool Observation
    │
    ├── Need More Evidence? ──► Select Next Tool
    │
    ▼
Synthesize Answer Grounded in Observations
    │
    ▼
Action / HITL Draft Generation (if applicable)
```

---

## 5. System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                   Frontend UI (React 19 + Vite @ 5173)                 │
│  - Dual Theme: Graphite Dark & Clean Neutral Light                    │
│  - Workspaces: Command Center, Ingestion, Audit Ledger, Suppliers,     │
│                AI Copilot, Compliance Audit Trail, Export Suite       │
│  - Persistent "Ask VyaparMitra" Drawer (Global, multi-turn, SQLite)   │
│  - Supplier Intelligence Drill-Down Drawer (Signals, Score, Trends)    │
│  - Side-Over Evidence Inspector & Statutory Rules Viewer              │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP REST / CORS
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   Backend API (FastAPI @ 8000)                         │
│  - /api/reconciliation/* : File Ingestion, Run, Results, Export        │
│  - /api/suppliers/*      : Counterparty Risk Profiles & Multi-Session   │
│  - /api/agent/*          : Multi-Step Reasoner, HITL Notices, Threads  │
│  - /api/audit/*          : Immutable Event Trail                       │
└───────────────────┬───────────────────────────────┬────────────────────┘
                    │                               │
                    ▼                               ▼
┌──────────────────────────────────────┐  ┌──────────────────────────────┐
│ Deterministic Core & Tool Catalog    │  │ Agentic Reasoner & LLM Core  │
│  - Luhn Mod-36 GSTIN Validator       │  │  - Google GenAI SDK          │
│  - Multi-Stage Invoice Matcher       │  │  - Gemini 2.5 Flash          │
│  - Python Decimal Financial Engine   │  │  - Structured Planning       │
│  - Section 50 Interest Engine (18%)  │  │  - Zero-Math Enforcement     │
│  - Supplier Risk Scorer (0-100)      │  │  - Dynamic Tool Selector     │
│  - Deterministic Tool Registry (14)  │  │  - Context Reuse Resolver    │
└───────────────────┬──────────────────┘  └──────────────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                 Persistent Store (SQLite3 Database)                    │
│  - reconciliation_sessions : Run outputs, summaries, detailed results  │
│  - audit_events            : Immutable audit trail with SHA-256 hashes │
│  - agent_conversations     : Multi-turn chat sessions                  │
│  - agent_messages          : Structured messages, traces, drafts       │
│  - agent_notices           : HITL dispute draft records & review states│
└────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Deterministic Tool Catalog

The orchestrator dynamically chooses from **14 registered deterministic tools** declared in [`backend/app/agent/tools_registry.py`](backend/app/agent/tools_registry.py):

| Tool Name | Category | Purpose | Parameters |
| :--- | :--- | :--- | :--- |
| `tool_run_reconciliation` | Reconciliation | Executes full multi-stage deterministic reconciliation engine | None |
| `tool_validate_gstin` | Validation | Validates 15-char Indian GSTIN structure and Luhn Mod-36 checksum | `gstin` |
| `tool_normalize_invoice` | Normalization | Normalizes invoice number strings by stripping harmless delimiters | `invoice_number` |
| `tool_calculate_tax_differences` | Calculation | Computes monetary variances using Decimal arithmetic | `purchase_*`, `gstr2b_*`, `tolerance` |
| `tool_calculate_section_50_interest` | Calculation | Computes statutory 18% simple interest on delayed tax claims | `principal_tax`, `delay_days`, `annual_rate` |
| `tool_lookup_statutory_rule` | Statutory | Retrieves statutory reference metadata and compliance guidance (Sec 16, 50, Rule 37A) | rule_id |
| `tool_get_session_summary` | Investigation | Retrieves high-level reconciliation KPIs and total at-risk ITC | `session_id` |
| `tool_get_missing_invoices` | Investigation | Identifies invoices missing in GSTR-2B returns or Purchase Register | `session_id` |
| `tool_inspect_invoice` | Investigation | Deep drilldown into tax variances, dates, and match status for an invoice | `session_id`, `invoice_number` |
| `tool_get_supplier_discrepancies` | Investigation | Aggregates and ranks suppliers by total at-risk ITC and missing counts | `session_id` |
| `tool_search_invoices` | Investigation | Free-text search across invoice numbers, GSTINs, and vendor names | `session_id`, `query` |
| `tool_get_supplier_profile` | Risk Intelligence | Retrieves deterministic 0–100 score, signals, and affected invoices | `session_id`, `supplier_gstin` |
| `tool_get_all_supplier_risk_profiles` | Risk Intelligence | Retrieves ranked risk profiles for all counterparties in session | `session_id` |
| `tool_get_supplier_history` | Risk Intelligence | Queries multi-session trends and recurring non-compliance patterns | `supplier_gstin` |

---

## 7. Supplier Risk Scoring Methodology

The supplier risk score is calculated using an explainable, 100% deterministic mathematical model:

$$\text{Risk Score} = \min(100, \text{Sum of Factors})$$

| Component | Logic | Maximum Weight |
| :--- | :--- | :---: |
| **Missing in 2B Factor** | 30 base + min(20, missing count × 10) | 50 pts |
| **Tax Mismatch Factor** | 15 base + min(15, mismatch count × 5) | 30 pts |
| **Duplicate / Invalid Data** | 25 pts if duplicates or invalid records detected | 25 pts |
| **Exposure Magnitude** | ≥ ₹50,000 → 20 pts \| ≥ ₹10,000 → 10 pts \| > ₹0 → 5 pts | 20 pts |
| **Fuzzy Match Review** | 5 pts if fuzzy matches require manual verification | 5 pts |
| **Perfect Match Bonus** | Score is explicitly 0 if all invoices match exactly and exposure is 0 | 0 pts |

### Risk Categories
- **0 – 24:** LOW RISK (Compliant counterparty)
- **25 – 49:** MEDIUM RISK (Minor variances or isolated discrepancies)
- **50 – 74:** HIGH RISK (Chronic unreflected invoices or significant tax difference)
- **75 – 100:** CRITICAL RISK (Severe ITC at risk, immediate payment withholding advised)

---

## 8. Technology Stack

- **Backend:** Python 3.14, FastAPI, Uvicorn, Pydantic v2
- **Agentic Engine:** Google GenAI SDK (`google-genai`), Gemini 2.5 Flash, 14 Deterministic Tools
- **Data & Matching:** Python `Decimal`, Pandas, OpenPyXL, RapidFuzz
- **Storage:** SQLite3 (WAL mode) with cryptographic audit logging
- **Frontend:** React 19, Vite 8, Lucide-style SVG icons, Pure CSS (Zero Tailwind/Bootstrap overhead)
- **Testing:** Pytest (107 unit, integration, and agentic tests), Chrome DevTools Protocol (CDP) headless automation

---

## 9. Comprehensive API Endpoint Catalog

VyaparMitra exposes 22 robust REST endpoints:

### Reconciliation & Ingestion (`/api/reconciliation`)
- `POST /api/reconciliation/demo` — Runs demo synthetic reconciliation.
- `POST /api/reconciliation/upload/purchase-register` — Ingests and validates purchase books (CSV/XLSX).
- `POST /api/reconciliation/upload/gstr2b` — Ingests and validates GSTR-2B inward return (CSV/JSON/XLSX).
- `POST /api/reconciliation/run` — Reconciles active session datasets deterministically.
- `GET /api/reconciliation/history` — Lists historical reconciliation sessions from SQLite.
- `GET /api/reconciliation/session/{id}` — Retrieves session summary status.
- `GET /api/reconciliation/session/{id}/results` — Restores full line-item reconciliation results.
- `GET /api/reconciliation/session/{id}/suppliers` — Retrieves counterparty breakdown summaries.
- `GET /api/reconciliation/export/{id}/csv` — Generates download ready reconciliation CSV.
- `GET /api/reconciliation/export/{id}/html` — Generates printable, standalone audit certificate.
- `GET /api/reconciliation/audit/{id}` — Fetches cryptographic event trail with SHA-256 hashes.

### AI Copilot & Multi-Turn Conversations (`/api/agent`)
- `POST /api/agent/investigate` — Dynamic multi-step agent reasoning with tool execution.
- `POST /api/agent/analyze` — Legacy batch copilot analysis and summary generation.
- `POST /api/agent/notice/{id}/action` — Human-in-the-Loop decision (`APPROVE`, `EDIT`, `REJECT`).
- `POST /api/agent/conversations` — Creates a new persistent conversation thread.
- `GET /api/agent/conversations/{session_id}` — Lists all conversation threads for session.
- `GET /api/agent/conversations/{id}/messages` — Retrieves structured message history and tool traces.
- `DELETE /api/agent/conversations/{id}` — Deletes conversation thread and messages.

### Supplier Risk Intelligence (`/api/suppliers`)
- `GET /api/suppliers/{session_id}/risk` — Returns all suppliers ranked by 0–100 risk score and exposure.
- `GET /api/suppliers/{session_id}/{gstin}/profile` — Returns detailed risk factors, score breakdown, and affected invoices.
- `GET /api/suppliers/{session_id}/{gstin}/history` — Multi-session recurring pattern detection.

### System Health
- `GET /api/health` — Returns application status and active runtime environment.

---

## 10. Installation & Getting Started

### Prerequisites
- Python 3.10+ (tested with Python 3.14)
- Node.js 18+ and npm 9+
- Git

### 1. Clone Repository & Setup Backend
```bash
git clone https://github.com/Karthik11022008/VyaparMitra.git
cd VyaparMitra

# Create and activate virtual environment
python -m venv .venv

# On Windows:
.\.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy the template configuration file:
```bash
cp .env.example .env
```
Edit `.env`:
```env
APP_NAME=VyaparMitra
APP_ENV=development
DATABASE_PATH=data/vyaparmitra.db
GEMINI_API_KEY=your_gemini_api_key_here
```
*(Note: If `GEMINI_API_KEY` is not provided, the system gracefully falls back to deterministic rule-based explanations with full tool execution intact).*

### 3. Setup Frontend
```bash
cd frontend
npm install
cd ..
```

---

## 11. Running the Application

### Start Backend API Server
```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
API Documentation will be available at: `http://localhost:8000/docs`

### Start Frontend Client
In a separate terminal:
```powershell
cd frontend
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 12. Testing & Verification

VyaparMitra maintains a rigorous, automated testing suite covering unit math, API contracts, dynamic tool chains, and persistent storage:

```powershell
# Run the complete backend test suite (107 tests)
.\.venv\Scripts\python.exe -m pytest backend/tests -v

# Verify production frontend build
cd frontend
npm run build
```

---

## 13. Quick Demo Walkthrough

1. **One-Click Demo Reconciliation:** Click the **"Demo Data"** button in the top navigation bar. This loads a realistic MSME dataset featuring exact matches, fuzzy invoice numbers, tax rate differences, and unreflected invoices.
2. **Explore Supplier Risk:** Open the **"Supplier Intelligence"** tab in the sidebar. View ranked counterparties, drill into `Haryana Heavy Fabrication`, view their deterministic 45/100 score, active signals, and inspect affected invoices.
3. **Multi-Turn Investigation:** Click **"Ask VyaparMitra"** or open the assistant drawer.
   - Ask: *"Why is this supplier risky?"* (Observe tool trace: `tool_get_supplier_profile`, `tool_lookup_statutory_rule`).
   - Follow up: *"What invoices caused this?"* (Observe pronoun resolution to the active supplier).
4. **Human-in-the-Loop Dispute Drafting:**
   - Ask: *"Draft a dispute notice for this supplier"*.
   - Verify the `DRAFT — REQUIRES HUMAN REVIEW` watermark.
   - Click **"Edit Draft"** to modify the text inline and save changes.
   - Click **"Approve Notice"** to log formal human authorization in the audit trail.
5. **Session Persistence:** Reload the browser page or navigate between workspaces. Open "Ask VyaparMitra" to see message history restored seamlessly from SQLite.

---

## 14. Important Limitations & Disclaimers

### Data Quality & Telemetry Notice
- **Illustrative Sample Data:** Demo datasets and sample invoices provided in this repository are synthetic and created for evaluation purposes.
- **Local Database Telemetry:** Historical records in the local SQLite database (`data/vyaparmitra.db`) reflect runs recorded during development and automated test executions (`pytest`). In production, this table records true multi-month statutory reconciliation sessions.

### Statutory & Legal Disclaimer
> **IMPORTANT NOTICE:** VyaparMitra is an operational accounting and reconciliation assistant. It does not provide legal, statutory, or chartered accountancy advice. GST laws, statutory rates, and departmental notifications are subject to periodic amendment by the GST Council. All dispute notices, communications, and return filings generated or suggested by this system **strictly require human review and authorization** by a qualified business owner or tax professional before external transmission.

---

## 15. Authorship & Attribution

- **Project:** VyaparMitra (व्यापार मित्र)
- **Author:** Karthik Kumar G ([@Karthik11022008](https://github.com/Karthik11022008))
- **Event:** Built for BHARAT AGENTIC 2026
- **Architecture & Originality:** Original implementation of deterministic multi-stage GST matching, explainable counterparty risk intelligence, and human-governed agentic workflows.

---

## 16. License

Distributed under the MIT License. See `LICENSE` for more information.
