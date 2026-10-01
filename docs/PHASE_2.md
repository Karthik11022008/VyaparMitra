# Phase 2: Deterministic GST Reconciliation Engine

**Project:** VyaparMitra (व्यापार मित्र)  
**Status:** Phase 2 Complete & Verified  

---

## 1. Deterministic Architecture

VyaparMitra enforces a strict architectural boundary between LLM orchestration and mathematical/accounting computation:
* **The AI Agent (Future Phase):** Will understand user intent, plan tool execution sequences, select relevant tools, explain findings, and draft reviewable communications.
* **Deterministic Python Core (Phase 2):** Performs 100% of the invoice normalization, GSTIN checksum verification, multi-stage matching, financial difference calculations, statutory interest formulas, and compliance rule evaluations.
* **Zero LLM Arithmetic:** Under no circumstances does the system delegate tax arithmetic, rounding, or reconciliation decisions to an LLM.

---

## 2. Multi-Stage Matching Strategy

Reconciliation between the buyer's internal Purchase Register and the auto-drafted GSTR-2B statement proceeds through three deterministic stages:

1. **Pre-Processing & Validation:**
   * Validates supplier GSTIN against the statutory 15-character structure and Luhn Mod 36 checksum.
   * Flags duplicate entries within the purchase register (`DUPLICATE_CANDIDATE`).
   * Normalizes invoice numbers by converting to uppercase, stripping whitespace, and removing harmless punctuation delimiters (`-`, `/`, `\`, `_`, `.`).
2. **Stage A (Exact Matching):**
   * Joins on `(Normalized GSTIN, Normalized Invoice Number)`.
   * Evaluates tax amounts against a configurable tolerance (default `Rs. 1.00`).
   * Classifies as `EXACT_MATCH` (within tolerance) or `AMOUNT_MISMATCH`.
3. **Stage B (Fuzzy Invoice Resolution):**
   * For unmatched records with the same supplier GSTIN, evaluates Levenshtein token similarity via RapidFuzz.
   * If similarity score $\ge 85.0\%$, classifies as `FUZZY_MATCH_REQUIRES_REVIEW`.
   * **Conservative Policy:** Fuzzy matching **never** silently confirms a match; it always flags the record for human verification.
4. **Stage C (Value & Period Correlation):**
   * Identifies transactions with identical taxable values and filing dates from the same supplier where invoice numbering prefixes differ.
5. **Unmatched Reconciliation:**
   * Unmatched purchase records $\rightarrow$ `MISSING_IN_2B`.
   * Unconsumed GSTR-2B records $\rightarrow$ `MISSING_IN_PURCHASE_REGISTER`.

---

## 3. Monetary Calculation & Interest Policy

* **Python Decimal Representation:** All monetary values are parsed and calculated using Python's `Decimal` type to eliminate IEEE 754 floating-point rounding inaccuracies.
* **Rounding Tolerance:** A statutory tolerance of `Rs. 1.00` is applied to absorb allowable rounding variations under GST rules.
* **Section 50 Interest Calculation:**
  $$\text{Interest} = \text{round}\left(\text{Principal} \times \text{Annual Rate} \times \frac{\text{Delay Days}}{365}, 2\right)$$
  Default rate: 18% per annum under Section 50(1) for delayed tax payments. Rate and days are explicitly parameterized.

---

## 4. Statutory Rule Catalog (Non-Legal Advice)

Statutory rules are decoupled into a dedicated configuration layer (`backend/app/tools/statutory_rules.py`):
* `RULE_16_2_AA`: GSTR-2B reflection requirement.
* `RULE_16_4`: Statutory FY claim cutoff horizon.
* `RULE_37A`: Reversal of ITC upon non-payment by supplier.
* `RULE_AMOUNT_MISMATCH`: Taxable / tax variance check.
* `RULE_MISSING_2B`: Unreflected entry in GSTR-2B statement.

> [!IMPORTANT]
> **Statutory Disclaimer:** VyaparMitra is an operational accounting and reconciliation assistant. It generates notices indicating *"Requires accounting/compliance review"* and does **not** provide legal advice or allege fraudulent intent.

---

## 5. Synthetic Demo Data Disclaimer

The datasets located in `data/demo/` (`purchase_register.csv` and `gstr2b.csv`) contain **100% synthetic, fictitious transactions** created specifically for testing and demonstration.
* GSTINs use valid statutory check digits for algorithm verification but do not represent actual taxpayers.
* No confidential, commercial, or personally identifiable information is stored or processed.
* This application has **no direct connection to live GSTN government APIs**.

---

## 6. Human-Review Requirement

All findings, classifications, and auto-generated notices are advisory aids for business owners and tax professionals. Automated actions require human review and explicit approval prior to dispatching supplier communications or submitting GSTR-3B offset filings.
