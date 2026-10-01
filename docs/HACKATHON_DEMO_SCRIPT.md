# VyaparMitra (व्यापार मित्र) — Hackathon Presentation & Demonstration Script

**Event:** BHARAT AGENTIC 2026 (12-Hour National Hackathon)  
**Date:** 1 October 2026  
**Problem Category:** Bharat MSME Fintech & Statutory Compliance  
**Solution:** Autonomous MSME GST Reconciliation & Dispute-Resolution Agent  

---

## 1. Executive Summary & Problem Framing

Indian Micro, Small, and Medium Enterprises (MSMEs) run on tight cash flows and lose billions of rupees in blocked working capital due to mismatches between internal purchase books and monthly GSTR-2B returns.

### The Bharat MSME Dilemma:
1. **Section 16(2)(aa) of CGST Act:** A buyer **cannot claim Input Tax Credit (ITC)** unless their supplier uploads the invoice in GSTR-1 and it appears in the buyer's auto-generated GSTR-2B.
2. **Section 50 Interest Penalties:** Inadvertently claiming ITC on unreflected or mismatched invoices triggers statutory interest at **18% to 24% per annum**.
3. **Vendor Delinquency & Friction:** Small business owners lack in-house tax accountants to manually compare thousands of messy spreadsheet rows, track down delinquent vendors, or draft legally sound dispute notices.
4. **LLM Hallucination Risk:** Generic AI agents cannot be trusted with tax math. Calculating tax liabilities or matching invoice values with an LLM leads to numerical hallucinations and statutory non-compliance.

---

## 2. The VyaparMitra Agentic Architecture

VyaparMitra follows the authentic hackathon paradigm:
**Understand $\rightarrow$ Reason $\rightarrow$ Plan $\rightarrow$ Use Tools $\rightarrow$ Act $\rightarrow$ Deliver**

```
┌─────────────────────────────────────────────────────────────────┐
│                    HUMAN-IN-THE-LOOP CONTROL                    │
│   (Accountant / Business Owner Reviews & Approves Actions)      │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│               COGNITIVE LAYER (Gemini 2.5 Flash)                │
│  - Natural Language Intent Understanding                        │
│  - Multi-Step Tool Planning & Tool Sequencing                   │
│  - Statutory Provision Association (CGST Sec 16(2)(aa), Sec 50) │
│  - Context-Aware Dispute Notice Drafting                        │
│  * ZERO ARITHMETIC — DELEGATES ALL MATH TO TOOLS *              │
└────────────────────────────────┬────────────────────────────────┘
                                 │ Registered Tool Calls
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                   DETERMINISTIC TOOLS CORE                      │
│  1. Ingestion Engine: CSV, XLSX, JSON (Official GSTN Schema)   │
│  2. Column Alias Mapper: Normalizes messy ERP headers           │
│  3. Luhn Mod-36 Validator: Validates 15-char GSTIN checksums    │
│  4. Invoice Matching Engine: Multi-stage Exact & RapidFuzz      │
│  5. Tax Calculator: Exact Decimal math with statutory tolerance │
│  6. Interest Calculator: Sec 50 daily accrual @ 18% p.a.        │
│  7. Statutory Rules Engine: Codified CGST provisions            │
│  8. Audit Logger: Cryptographic SQLite chronological trail      │
│  9. Document Exporter: Audit CSV & Certified HTML certificates  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Five-Minute Live Demonstration Walkthrough

### Step 1: System Command Center (Overview Tab)
- **Visuals:** High-density, professional fintech UI with Dual-Theme toggle (Graphite Dark & Crisp Neutral Light).
- **KPI Metrics:**
  - Audited ITC vs. At-Risk ITC prominently highlighted.
  - Overall Compliance Match Rate percentage.
  - Interactive multi-segment reconciliation progress bar.
- **Narrative:** *"VyaparMitra gives MSME owners an immediate birds-eye view of their tax health and trapped working capital."*

### Step 2: Real Multi-Format File Ingestion (Ingestion Tab)
- **Demo Action:** Upload internal Purchase Register (`.csv`/`.xlsx`) and GSTR-2B Statement (`.csv`/`.json`/`.xlsx`), or click **"Load Verified Sample Dataset"**.
- **Key Features Demonstrated:**
  - **Instant Format Detection & Header Normalization:** Handles variances in column names (e.g., `Inv No`, `Invoice Number`, `Document #`).
  - **Luhn Mod-36 GSTIN Verification:** Identifies malformed or checksum-failing supplier GSTINs.
  - **Side-by-Side Previews:** Visual table previews of the first 5 records of both buyer books and portal statements.
  - **Reconciliation Readiness Guard:** Intelligently enables the reconciliation action once both files are validated.

### Step 3: Deterministic Reconciliation Ledger (Reconciliation Tab)
- **Demo Action:** Filter discrepancies by status:
  - `MATCHED`: Identical invoice number, GSTIN, and taxable/tax values.
  - `REVIEW`: Normalized invoice formatting matches (e.g., stripping slashes/prefixes) or RapidFuzz string similarity $\ge 85\%$.
  - `MISMATCH`: Supplier reported invoice with divergent taxable or tax amounts.
  - `MISSING_IN_2B`: Buyer paid tax to vendor, but vendor failed to report supply $\rightarrow$ **100% ITC at risk**.
  - `INVALID / DUPLICATE`: Flagged duplicate billings or invalid tax IDs.
- **Side-Over Evidence Inspector Drawer:** Click any invoice row to open the side-over inspector comparing Buyer Books vs. GSTN Portal side-by-side with statutory reasoning.

### Step 4: AI Copilot Execution & Lifecycle (AI Agent Tab)
- **Demo Action:** Select one of the quick prompt chips or enter:
  > *"Reconcile recent purchase invoices against GSTR-2B, identify at-risk ITC discrepancies, and draft supplier dispute notices."*
- **Visuals:**
  - Watch the **Linear 6-Stage Execution Lifecycle** animate:  
    `STAGE 1: UNDERSTAND` $\rightarrow$ `STAGE 2: ANALYZE` $\rightarrow$ `STAGE 3: MATCH` $\rightarrow$ `STAGE 4: VERIFY` $\rightarrow$ `STAGE 5: RISK` $\rightarrow$ `STAGE 6: ACTION`
  - **Executive Briefing:** Structured natural-language analysis explaining total trapped ITC, Section 50 interest risk, and priority actions.
  - **Deterministic Tools Executed Tags:** Lists the exact deterministic tools called during orchestration.

### Step 5: Human-in-the-Loop Dispute Center (AI Agent Tab)
- **Core Principle:** AI drafts, Human decides.
- **Demo Action:**
  - Review the generated **Draft Supplier Dispute Notices**.
  - Inspect statutory provisions: explicitly cites **Section 16(2)(aa) of CGST Act, 2017** and **Rule 36(4)**.
  - Click **"Edit Notice"** to modify draft wording inline.
  - Click **"Approve Notice"** or **"Reject Notice"**.
  - Status updates to `APPROVED FOR DISPATCH` and logs permanently to the SQLite audit trail.

### Step 6: Immutable Compliance Audit Trail (Audit Tab)
- **Demo Action:** Switch to the Audit Trail tab.
- **Key Features:** Chronological, cryptographic timeline of every single system event:
  - `FILE_UPLOADED`
  - `FILE_VALIDATED`
  - `RECONCILIATION_COMPLETED`
  - `AGENT_ANALYSIS_COMPLETED`
  - `NOTICE_APPROVED` / `NOTICE_REJECTED`
- Demonstrates institutional accountability required by tax authorities and external auditors.

### Step 7: Audit-Ready Document Export (Reports & Export Tab)
- **Demo Action:**
  - **Before Reconciliation:** Polite empty state showing *"No completed reconciliation"* with direct navigation button.
  - **After Reconciliation:** Active session banner displaying active session ID, total records reconciled, and at-risk ITC amount.
  - Click **"Download CSV Export"** $\rightarrow$ instant discrepancy ledger with statutory disclaimers.
  - Click **"Download HTML Audit Report"** $\rightarrow$ standalone, beautifully styled audit certificate printable directly to PDF.

---

## 4. Technical Rigor & Verification Matrix

| Metric | Verification Standard | Result |
|---|---|---|
| **Backend Test Suite** | 54 Pytest automated tests across 13 test suites | **54 Passed (100%)** |
| **Arithmetic Integrity** | Python `Decimal` with 2 decimal precision | **Zero floating-point errors** |
| **GSTIN Validation** | Luhn Mod-36 state code & checksum algorithm | **100% deterministic** |
| **Interest Rate Accuracy** | Section 50 CGST Act ($18\%$ per annum daily calculation) | **Verified against statutory formula** |
| **Frontend Production Build** | Vite v8.3.1 client bundle packaging | **Zero errors, 160ms build** |
| **API Endpoints** | RESTful FastAPI with CORS, size guards & path sanitation | **All endpoints healthy & verified** |

---

## 5. Summary Pitch for the Judges

> *"VyaparMitra bridges the gap between complex tax law and MSME survival in Bharat. By combining the conversational intelligence of Gemini for planning and communication with an uncompromised, 100% deterministic Python engine for statutory math and matching, VyaparMitra ensures Indian business owners never lose a single rupee of rightful Input Tax Credit while remaining completely audit-ready."*
