import json
import logging
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple

from backend.app.schemas.invoice import MatchStatus, ReconciliationResponse
from backend.app.schemas.supplier_risk import (
    SupplierRiskSignal,
    SupplierRiskProfile,
    SupplierHistoryTrend,
    SupplierHistoryProfile,
)
from backend.app.services.reconciliation_service import (
    SESSION_DATA_CACHE,
    reconcile_demo_dataset,
    DEMO_SUPPLIER_NAMES,
)
from backend.app.database import get_reconciliation_session, get_connection

logger = logging.getLogger(__name__)


def compute_supplier_risk_score(
    total_invoices: int,
    exact_matches: int,
    fuzzy_matches: int,
    tax_mismatches: int,
    missing_in_2b: int,
    duplicate_candidates: int,
    invalid_records: int,
    at_risk_itc: Decimal,
    net_tax_variance: Decimal = Decimal("0.00"),
    missing_2b_tax: Decimal = Decimal("0.00"),
    mismatch_tax: Decimal = Decimal("0.00"),
) -> Tuple[int, str, Dict[str, int], List[SupplierRiskSignal], List[str]]:
    """
    Authoritative deterministic supplier risk scoring engine.
    Zero LLM involvement — 100% deterministic rule-driven scoring.

    Scoring Model Weights:
    - Base: 0
    - Perfect Match Bonus: Score is 0 if total_invoices == exact_matches and at_risk_itc == 0
    - Missing 2B factor: 30 base + min(20, missing_in_2b * 10) [Max: 50]
    - Tax Mismatch factor: 15 base + min(15, tax_mismatches * 5) [Max: 30]
    - Duplicate / Invalid factor: 25 if duplicate_candidates > 0 or invalid_records > 0 [Max: 25]
    - Fuzzy match factor: 5 if fuzzy_matches > 0 [Max: 5]
    - Exposure factor:
        >= 50,000 -> 20 pts
        >= 10,000 -> 10 pts
        > 0       -> 5 pts
    - Cap: max 100, min 0
    - Categories:
        0-24: LOW
        25-49: MEDIUM
        50-74: HIGH
        75-100: CRITICAL
    """
    signals: List[SupplierRiskSignal] = []
    actions: List[str] = []
    breakdown: Dict[str, int] = {
        "missing_2b_factor": 0,
        "tax_mismatch_factor": 0,
        "duplicate_invalid_factor": 0,
        "fuzzy_match_factor": 0,
        "exposure_factor": 0,
    }

    if total_invoices == 0:
        return 0, "LOW", breakdown, signals, ["No invoice activity recorded."]

    if total_invoices == exact_matches and at_risk_itc <= Decimal("0.00") and net_tax_variance == Decimal("0.00"):
        return 0, "LOW", breakdown, signals, ["Supplier in good standing — all invoices match perfectly."]

    # 1. Missing in GSTR-2B Factor
    if missing_in_2b > 0:
        m2b_score = 30 + min(20, missing_in_2b * 10)
        breakdown["missing_2b_factor"] = m2b_score
        signals.append(
            SupplierRiskSignal(
                code="MISSING_2B",
                label="Unreflected in GSTR-2B",
                severity="CRITICAL" if missing_in_2b >= 2 or missing_2b_tax > Decimal("10000.00") else "HIGH",
                reason=f"{missing_in_2b} invoice(s) omitted from counterparty GSTR-2B return under CGST Section 16(2)(aa).",
                count=missing_in_2b,
                amount=missing_2b_tax if missing_2b_tax > 0 else at_risk_itc,
            )
        )
        actions.append("Draft formal Section 16(2)(aa) dispute notice requesting supplier to upload unreflected invoices in GSTR-1.")

    # 2. Tax Mismatch Factor
    if tax_mismatches > 0:
        tm_score = 15 + min(15, tax_mismatches * 5)
        breakdown["tax_mismatch_factor"] = tm_score
        signals.append(
            SupplierRiskSignal(
                code="TAX_MISMATCH",
                label="Tax Amount Variance",
                severity="HIGH" if mismatch_tax > Decimal("1000.00") else "MEDIUM",
                reason=f"{tax_mismatches} invoice(s) exhibit tax variances exceeding statutory ₹1.00 tolerance.",
                count=tax_mismatches,
                amount=mismatch_tax if mismatch_tax > 0 else net_tax_variance,
            )
        )
        actions.append("Request supplier credit/debit note or verify rate classification under Rule 37A.")

    # 3. Duplicate / Invalid Data Factor
    if duplicate_candidates > 0 or invalid_records > 0:
        breakdown["duplicate_invalid_factor"] = 25
        if invalid_records > 0:
            signals.append(
                SupplierRiskSignal(
                    code="INVALID_GSTIN",
                    label="Invalid Counterparty GSTIN",
                    severity="CRITICAL",
                    reason=f"{invalid_records} record(s) failed GSTIN Luhn Mod 36 checksum or structural validation.",
                    count=invalid_records,
                    amount=Decimal("0.00"),
                )
            )
            actions.append("Verify vendor GST registration certificate and active legal status on GST portal.")
        if duplicate_candidates > 0:
            signals.append(
                SupplierRiskSignal(
                    code="DUPLICATE_PATTERN",
                    label="Duplicate Invoice Candidate",
                    severity="HIGH",
                    reason=f"{duplicate_candidates} invoice(s) identified with duplicate numbers or overlapping dates.",
                    count=duplicate_candidates,
                    amount=Decimal("0.00"),
                )
            )
            actions.append("Audit internal purchase register to ensure credit is not availed twice.")

    # 4. Fuzzy Match Factor
    if fuzzy_matches > 0:
        breakdown["fuzzy_match_factor"] = 5
        signals.append(
            SupplierRiskSignal(
                code="FUZZY_MATCH",
                label="Alphanumeric Formatting Variance",
                severity="LOW",
                reason=f"{fuzzy_matches} invoice(s) matched under normalized separators or punctuation rules.",
                count=fuzzy_matches,
                amount=Decimal("0.00"),
            )
        )
        if not actions:
            actions.append("Standardize invoice numbering conventions with supplier to maintain exact matching.")

    # 5. Financial Exposure Factor
    if at_risk_itc >= Decimal("50000.00"):
        breakdown["exposure_factor"] = 20
        signals.append(
            SupplierRiskSignal(
                code="HIGH_ITC_EXPOSURE",
                label="Critical ITC Exposure",
                severity="CRITICAL",
                reason=f"Total at-risk Input Tax Credit exceeds ₹50,000 (₹{at_risk_itc:,.2f}).",
                count=total_invoices,
                amount=at_risk_itc,
            )
        )
    elif at_risk_itc >= Decimal("10000.00"):
        breakdown["exposure_factor"] = 10
        signals.append(
            SupplierRiskSignal(
                code="HIGH_ITC_EXPOSURE",
                label="Substantial ITC Exposure",
                severity="HIGH",
                reason=f"Total at-risk Input Tax Credit exceeds ₹10,000 threshold (₹{at_risk_itc:,.2f}).",
                count=total_invoices,
                amount=at_risk_itc,
            )
        )
    elif at_risk_itc > Decimal("0.00"):
        breakdown["exposure_factor"] = 5

    # Compound Discrepancy Signal
    if len(signals) >= 2:
        signals.append(
            SupplierRiskSignal(
                code="MULTIPLE_DISCREPANCIES",
                label="Compound Discrepancies Detected",
                severity="HIGH",
                reason=f"Supplier exhibits {len(signals)} distinct compliance anomalies across active records.",
                count=len(signals),
                amount=at_risk_itc,
            )
        )

    raw_score = sum(breakdown.values())
    final_score = min(100, max(0, raw_score))

    if final_score >= 75:
        category = "CRITICAL"
    elif final_score >= 50:
        category = "HIGH"
    elif final_score >= 25:
        category = "MEDIUM"
    else:
        category = "LOW"

    if not actions:
        actions.append("Review counterparty filings periodically.")

    return final_score, category, breakdown, signals, actions


def _get_recon_response_for_session(session_id: Optional[str]) -> Optional[ReconciliationResponse]:
    """Retrieves or restores reconciliation results from memory cache or database."""
    effective_id = session_id or "demo-session"
    if effective_id in SESSION_DATA_CACHE and SESSION_DATA_CACHE[effective_id].get("reconciliation_response"):
        return SESSION_DATA_CACHE[effective_id]["reconciliation_response"]

    # Try demo dataset fallback if session_id is demo-session
    if effective_id in ("demo-session", "default"):
        res = reconcile_demo_dataset()
        SESSION_DATA_CACHE[effective_id] = {
            "reconciliation_response": res,
            "purchase_invoices": [],
            "gstr2b_invoices": []
        }
        return res

    # Recover from database
    row = get_reconciliation_session(effective_id)
    if row and row.get("results_json"):
        try:
            results_dict = json.loads(row["results_json"])
            summary_dict = json.loads(row.get("summary_json") or "{}")
            supplier_dict = json.loads(row.get("supplier_summary_json") or "[]")
            from backend.app.schemas.invoice import (
                ReconciliationResult,
                ReconciliationSummary,
                SupplierSummary,
            )
            recon_res = ReconciliationResponse(
                status=row.get("status", "success"),
                summary=ReconciliationSummary(**summary_dict),
                detailed_results=[ReconciliationResult(**r) for r in results_dict],
                supplier_summaries=[SupplierSummary(**s) for s in supplier_dict],
                session_id=effective_id,
            )
            SESSION_DATA_CACHE[effective_id] = {
                "reconciliation_response": recon_res,
                "purchase_invoices": [],
                "gstr2b_invoices": []
            }
            return recon_res
        except Exception as e:
            logger.warning(f"Failed to recover reconciliation from DB results_json: {e}")

    # Fallback to demo dataset
    return reconcile_demo_dataset()


def build_supplier_risk_profile(
    session_id: Optional[str],
    supplier_gstin: str,
) -> Optional[SupplierRiskProfile]:
    """
    Computes a comprehensive deterministic risk profile for a specific supplier in a session.
    """
    resp = _get_recon_response_for_session(session_id)
    if not resp:
        return None

    target_gstin = supplier_gstin.strip().upper()
    supplier_items = []
    supplier_name = ""

    for r in resp.detailed_results:
        p = r.purchase_invoice
        b = r.matched_2b_invoice
        p_gstin = (p.supplier_gstin if p else "").strip().upper()
        b_gstin = (b.supplier_gstin if b else "").strip().upper()

        if target_gstin in (p_gstin, b_gstin):
            supplier_items.append(r)
            if not supplier_name:
                supplier_name = p.supplier_name if p and p.supplier_name else (b.supplier_name if b and b.supplier_name else "")

    if not supplier_items:
        return None

    if not supplier_name:
        supplier_name = DEMO_SUPPLIER_NAMES.get(target_gstin, f"Vendor {target_gstin[:8]}...")

    total_invoices = len(supplier_items)
    exact_matches = sum(1 for r in supplier_items if r.status == MatchStatus.EXACT_MATCH)
    fuzzy_matches = sum(1 for r in supplier_items if r.status == MatchStatus.FUZZY_MATCH_REQUIRES_REVIEW)
    tax_mismatches = sum(1 for r in supplier_items if r.status == MatchStatus.AMOUNT_MISMATCH)
    missing_in_2b = sum(1 for r in supplier_items if r.status == MatchStatus.MISSING_IN_2B)
    missing_in_pr = sum(1 for r in supplier_items if r.status == MatchStatus.MISSING_IN_PURCHASE_REGISTER)
    duplicate_candidates = sum(1 for r in supplier_items if r.status == MatchStatus.DUPLICATE_CANDIDATE)
    invalid_records = sum(1 for r in supplier_items if r.status == MatchStatus.INVALID_DATA)

    total_purchase_tax = Decimal("0.00")
    at_risk_itc = Decimal("0.00")
    net_tax_variance = Decimal("0.00")
    missing_2b_tax = Decimal("0.00")
    mismatch_tax = Decimal("0.00")

    affected_invoices: List[Dict[str, Any]] = []

    for r in supplier_items:
        p = r.purchase_invoice
        b = r.matched_2b_invoice
        inv_tax = p.total_tax if p else (b.total_tax if b else Decimal("0.00"))
        if p:
            total_purchase_tax += p.total_tax

        if r.status == MatchStatus.MISSING_IN_2B:
            at_risk_itc += inv_tax
            missing_2b_tax += inv_tax
        elif r.status == MatchStatus.AMOUNT_MISMATCH:
            if r.tax_difference > 0:
                at_risk_itc += r.tax_difference
            net_tax_variance += r.tax_difference
            mismatch_tax += r.tax_difference
        elif r.status == MatchStatus.FUZZY_MATCH_REQUIRES_REVIEW:
            if r.tax_difference > 0:
                at_risk_itc += r.tax_difference
                net_tax_variance += r.tax_difference
        elif r.status in (MatchStatus.DUPLICATE_CANDIDATE, MatchStatus.INVALID_DATA):
            if p:
                at_risk_itc += p.total_tax

        # Build affected invoices list
        affected_invoices.append({
            "invoice_number": p.invoice_number if p else (b.invoice_number if b else ""),
            "invoice_date": p.invoice_date if p else (b.invoice_date if b else ""),
            "purchase_tax": float(p.total_tax) if p else None,
            "gstr2b_tax": float(b.total_tax) if b else None,
            "tax_difference": float(r.tax_difference),
            "status": r.status.value,
            "reason": r.reason,
            "statutory_rule": "Section 16(2)(aa)" if r.status == MatchStatus.MISSING_IN_2B else ("Rule 37A" if r.status == MatchStatus.AMOUNT_MISMATCH else "CGST General"),
        })

    score, category, breakdown, signals, actions = compute_supplier_risk_score(
        total_invoices=total_invoices,
        exact_matches=exact_matches,
        fuzzy_matches=fuzzy_matches,
        tax_mismatches=tax_mismatches,
        missing_in_2b=missing_in_2b,
        duplicate_candidates=duplicate_candidates,
        invalid_records=invalid_records,
        at_risk_itc=at_risk_itc,
        net_tax_variance=net_tax_variance,
        missing_2b_tax=missing_2b_tax,
        mismatch_tax=mismatch_tax,
    )

    return SupplierRiskProfile(
        supplier_gstin=target_gstin,
        supplier_name=supplier_name,
        total_invoices=total_invoices,
        exact_matches=exact_matches,
        fuzzy_matches=fuzzy_matches,
        tax_mismatches=tax_mismatches,
        missing_in_2b=missing_in_2b,
        missing_in_purchase_register=missing_in_pr,
        duplicate_candidates=duplicate_candidates,
        invalid_records=invalid_records,
        total_purchase_tax=round(total_purchase_tax, 2),
        at_risk_itc=round(at_risk_itc, 2),
        net_tax_variance=round(net_tax_variance, 2),
        risk_score=score,
        risk_category=category,
        score_breakdown=breakdown,
        signals=signals,
        recommended_actions=actions,
        affected_invoices=affected_invoices,
        last_session_status="ACTIVE",
    )


def build_all_supplier_risk_profiles(session_id: Optional[str]) -> List[SupplierRiskProfile]:
    """
    Computes deterministic risk profiles for all unique suppliers in the session,
    ranked by risk score (descending) and at-risk ITC (descending).
    """
    resp = _get_recon_response_for_session(session_id)
    if not resp:
        return []

    unique_gstins = set()
    for r in resp.detailed_results:
        p = r.purchase_invoice
        b = r.matched_2b_invoice
        if p and p.supplier_gstin:
            unique_gstins.add(p.supplier_gstin.strip().upper())
        if b and b.supplier_gstin:
            unique_gstins.add(b.supplier_gstin.strip().upper())

    profiles: List[SupplierRiskProfile] = []
    for gstin in unique_gstins:
        prof = build_supplier_risk_profile(session_id, gstin)
        if prof:
            profiles.append(prof)

    # Sort deterministically: highest risk score first, then highest at-risk ITC
    profiles.sort(key=lambda x: (x.risk_score, x.at_risk_itc, x.total_invoices), reverse=True)
    return profiles


def get_supplier_history_profile(supplier_gstin: str) -> SupplierHistoryProfile:
    """
    Aggregates supplier history and patterns across all persisted sessions in SQLite.
    Zero fabricated data — if seen in < 2 sessions, returns 'Insufficient historical data'.
    """
    target_gstin = supplier_gstin.strip().upper()
    conn = get_connection()
    trends: List[SupplierHistoryTrend] = []
    detected_patterns: List[str] = []
    supplier_name = ""

    try:
        cursor = conn.execute(
            """
            SELECT session_id, created_at, supplier_summary_json, results_json
            FROM reconciliation_sessions
            ORDER BY created_at ASC
            """
        )
        rows = cursor.fetchall()

        for row in rows:
            sid = row["session_id"]
            created_at = row["created_at"]
            sup_json = row["supplier_summary_json"]

            if sup_json:
                try:
                    summaries = json.loads(sup_json)
                    matching_sup = next(
                        (s for s in summaries if s.get("supplier_gstin", "").strip().upper() == target_gstin),
                        None
                    )
                    if matching_sup:
                        if not supplier_name:
                            supplier_name = matching_sup.get("supplier_name", "")
                        at_risk = Decimal(str(matching_sup.get("total_at_risk_itc", "0.00")))
                        m2b = matching_sup.get("missing_in_2b", 0)
                        mm = matching_sup.get("amount_mismatches", 0)
                        fz = matching_sup.get("fuzzy_matches", 0)
                        discrepancies = m2b + mm + fz

                        trends.append(
                            SupplierHistoryTrend(
                                session_id=sid,
                                created_at=created_at,
                                total_invoices=matching_sup.get("total_invoices", 0),
                                discrepancy_count=discrepancies,
                                missing_in_2b=m2b,
                                tax_mismatches=mm,
                                at_risk_itc=round(at_risk, 2),
                            )
                        )
                except Exception as e:
                    logger.debug(f"Failed to parse supplier summary JSON for session {sid}: {e}")

    finally:
        conn.close()

    if not supplier_name:
        supplier_name = DEMO_SUPPLIER_NAMES.get(target_gstin, f"Vendor {target_gstin[:8]}...")

    sessions_seen = len(trends)
    has_sufficient = sessions_seen >= 2

    # Deterministic pattern detection
    if has_sufficient:
        sessions_with_missing = sum(1 for t in trends if t.missing_in_2b > 0)
        sessions_with_mismatch = sum(1 for t in trends if t.tax_mismatches > 0)

        if sessions_with_missing >= 2:
            detected_patterns.append("REPEATEDLY_MISSING_IN_2B: Unreflected invoices detected across multiple reconciliation sessions.")

        if sessions_with_mismatch >= 2:
            detected_patterns.append("RECURRING_TAX_MISMATCHES: Ongoing tax amount variances detected across sessions.")

        if len(trends) >= 2 and trends[-1].at_risk_itc > trends[-2].at_risk_itc:
            detected_patterns.append(f"INCREASING_EXPOSURE: At-risk ITC grew from ₹{trends[-2].at_risk_itc:,.2f} to ₹{trends[-1].at_risk_itc:,.2f} in the latest session.")

    total_invoices = sum(t.total_invoices for t in trends)
    total_discrepancies = sum(t.discrepancy_count for t in trends)
    total_at_risk = sum((t.at_risk_itc for t in trends), Decimal("0.00"))

    return SupplierHistoryProfile(
        supplier_gstin=target_gstin,
        supplier_name=supplier_name,
        sessions_seen_count=sessions_seen,
        has_sufficient_history=has_sufficient,
        total_historical_invoices=total_invoices,
        total_historical_discrepancies=total_discrepancies,
        total_historical_at_risk_itc=round(total_at_risk, 2),
        detected_patterns=detected_patterns,
        trends=trends,
    )
