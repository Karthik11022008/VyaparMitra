from decimal import Decimal
from typing import List, Dict, Set, Tuple
from rapidfuzz import fuzz

from backend.app.schemas.invoice import (
    PurchaseInvoice,
    GSTR2BInvoice,
    ReconciliationResult,
    MatchStatus,
)
from backend.app.tools.normalization import normalize_invoice_number, normalize_gstin
from backend.app.tools.gstin_validator import validate_gstin
from backend.app.tools.tax_calculator import calculate_tax_differences, DEFAULT_TOLERANCE
from backend.app.tools.rules_engine import evaluate_statutory_rules

FUZZY_CONFIDENCE_THRESHOLD = 85.0

class InvoiceMatchingEngine:
    def __init__(
        self,
        fuzzy_threshold: float = FUZZY_CONFIDENCE_THRESHOLD,
        amount_tolerance: Decimal = DEFAULT_TOLERANCE,
    ):
        self.fuzzy_threshold = fuzzy_threshold
        self.amount_tolerance = amount_tolerance

    def reconcile(
        self,
        purchase_invoices: List[PurchaseInvoice],
        gstr2b_invoices: List[GSTR2BInvoice],
    ) -> List[ReconciliationResult]:
        """
        Executes multi-stage deterministic reconciliation between Purchase Register and GSTR-2B.
        """
        results: List[ReconciliationResult] = []
        
        # 1. Check for duplicates in Purchase Register
        seen_purchase_keys: Dict[Tuple[str, str], int] = {}
        for inv in purchase_invoices:
            key = (normalize_gstin(inv.supplier_gstin), normalize_invoice_number(inv.invoice_number))
            seen_purchase_keys[key] = seen_purchase_keys.get(key, 0) + 1
            
        duplicate_purchase_keys: Set[Tuple[str, str]] = {
            k for k, count in seen_purchase_keys.items() if count > 1
        }

        # 2. Index GSTR-2B records
        # Track consumed 2B indices
        consumed_2b_indices: Set[int] = set()

        # Build lookup tables for 2B
        exact_2b_index: Dict[Tuple[str, str], List[int]] = {}
        by_gstin_2b_index: Dict[str, List[int]] = {}

        for idx, inv in enumerate(gstr2b_invoices):
            gstin_norm = normalize_gstin(inv.supplier_gstin)
            inv_norm = normalize_invoice_number(inv.invoice_number)
            
            exact_key = (gstin_norm, inv_norm)
            exact_2b_index.setdefault(exact_key, []).append(idx)
            by_gstin_2b_index.setdefault(gstin_norm, []).append(idx)

        # 3. Match each purchase invoice
        for p_inv in purchase_invoices:
            gstin_norm = normalize_gstin(p_inv.supplier_gstin)
            inv_norm = normalize_invoice_number(p_inv.invoice_number)
            exact_key = (gstin_norm, inv_norm)

            # Check GSTIN validity
            gstin_val = validate_gstin(p_inv.supplier_gstin)
            if not gstin_val.is_valid:
                results.append(
                    ReconciliationResult(
                        status=MatchStatus.INVALID_DATA,
                        purchase_invoice=p_inv,
                        matched_2b_invoice=None,
                        taxable_difference=p_inv.taxable_value,
                        tax_difference=p_inv.total_tax,
                        confidence=0.0,
                        reason=f"Invalid Supplier GSTIN: {'; '.join(gstin_val.errors)}",
                        rules_flagged=["RULE_INVALID_GSTIN"]
                    )
                )
                continue

            # Check if this invoice is a duplicate entry in buyer's books
            if exact_key in duplicate_purchase_keys:
                results.append(
                    ReconciliationResult(
                        status=MatchStatus.DUPLICATE_CANDIDATE,
                        purchase_invoice=p_inv,
                        matched_2b_invoice=None,
                        taxable_difference=p_inv.taxable_value,
                        tax_difference=p_inv.total_tax,
                        confidence=0.5,
                        reason="Duplicate entry identified in purchase books for same supplier and invoice number.",
                        rules_flagged=["RULE_DUPLICATE_PURCHASE"]
                    )
                )
                continue

            # Stage A: Exact Match on (GSTIN, Normalized Invoice Number)
            matched_idx = None
            if exact_key in exact_2b_index:
                # Find first unconsumed matching 2B invoice
                for candidate_idx in exact_2b_index[exact_key]:
                    if candidate_idx not in consumed_2b_indices:
                        matched_idx = candidate_idx
                        break

            if matched_idx is not None:
                consumed_2b_indices.add(matched_idx)
                b2b_inv = gstr2b_invoices[matched_idx]
                
                comparison = calculate_tax_differences(
                    p_inv.taxable_value, p_inv.cgst, p_inv.sgst, p_inv.igst,
                    b2b_inv.taxable_value, b2b_inv.cgst, b2b_inv.sgst, b2b_inv.igst,
                    self.amount_tolerance
                )

                if comparison.is_within_tolerance:
                    status = MatchStatus.EXACT_MATCH
                    reason = "Exact match on GSTIN, normalized invoice number, and tax amounts."
                else:
                    status = MatchStatus.AMOUNT_MISMATCH
                    reason = f"Tax values differ (Taxable Diff: Rs. {comparison.taxable_diff}, Tax Diff: Rs. {comparison.total_tax_diff})."

                rules = evaluate_statutory_rules(status, p_inv, b2b_inv, comparison.total_tax_diff)
                results.append(
                    ReconciliationResult(
                        status=status,
                        purchase_invoice=p_inv,
                        matched_2b_invoice=b2b_inv,
                        taxable_difference=comparison.taxable_diff,
                        tax_difference=comparison.total_tax_diff,
                        confidence=1.0,
                        reason=reason,
                        rules_flagged=[r.rule_id for r in rules]
                    )
                )
                continue

            # Stage B: Fuzzy Matching on Invoice Number for Same GSTIN
            best_fuzzy_idx = None
            best_score = 0.0

            if gstin_norm in by_gstin_2b_index:
                for candidate_idx in by_gstin_2b_index[gstin_norm]:
                    if candidate_idx in consumed_2b_indices:
                        continue
                    candidate_inv = gstr2b_invoices[candidate_idx]
                    cand_inv_norm = normalize_invoice_number(candidate_inv.invoice_number)
                    
                    score = fuzz.ratio(inv_norm, cand_inv_norm)
                    if score > best_score and score >= self.fuzzy_threshold:
                        best_score = score
                        best_fuzzy_idx = candidate_idx

            if best_fuzzy_idx is not None:
                consumed_2b_indices.add(best_fuzzy_idx)
                b2b_inv = gstr2b_invoices[best_fuzzy_idx]
                
                comparison = calculate_tax_differences(
                    p_inv.taxable_value, p_inv.cgst, p_inv.sgst, p_inv.igst,
                    b2b_inv.taxable_value, b2b_inv.cgst, b2b_inv.sgst, b2b_inv.igst,
                    self.amount_tolerance
                )

                confidence = round(best_score / 100.0, 2)
                if comparison.is_within_tolerance:
                    status = MatchStatus.FUZZY_MATCH_REQUIRES_REVIEW
                    reason = f"Fuzzy invoice match ({best_score:.1f}% similarity: '{p_inv.invoice_number}' vs '{b2b_inv.invoice_number}'). Amounts match within tolerance."
                else:
                    status = MatchStatus.AMOUNT_MISMATCH
                    reason = f"Fuzzy invoice match ({best_score:.1f}% similarity), but amounts also differ (Tax Diff: Rs. {comparison.total_tax_diff})."

                rules = evaluate_statutory_rules(status, p_inv, b2b_inv, comparison.total_tax_diff)
                results.append(
                    ReconciliationResult(
                        status=status,
                        purchase_invoice=p_inv,
                        matched_2b_invoice=b2b_inv,
                        taxable_difference=comparison.taxable_diff,
                        tax_difference=comparison.total_tax_diff,
                        confidence=confidence,
                        reason=reason,
                        rules_flagged=[r.rule_id for r in rules]
                    )
                )
                continue

            # Stage C: Value & Period Match for Same GSTIN (Alternate invoice numbering)
            stage_c_idx = None
            if gstin_norm in by_gstin_2b_index:
                for candidate_idx in by_gstin_2b_index[gstin_norm]:
                    if candidate_idx in consumed_2b_indices:
                        continue
                    candidate_inv = gstr2b_invoices[candidate_idx]
                    val_diff = abs(p_inv.taxable_value - candidate_inv.taxable_value)
                    
                    if val_diff <= self.amount_tolerance and (
                        p_inv.tax_period == candidate_inv.tax_period or p_inv.invoice_date == candidate_inv.invoice_date
                    ):
                        stage_c_idx = candidate_idx
                        break

            if stage_c_idx is not None:
                consumed_2b_indices.add(stage_c_idx)
                b2b_inv = gstr2b_invoices[stage_c_idx]
                
                comparison = calculate_tax_differences(
                    p_inv.taxable_value, p_inv.cgst, p_inv.sgst, p_inv.igst,
                    b2b_inv.taxable_value, b2b_inv.cgst, b2b_inv.sgst, b2b_inv.igst,
                    self.amount_tolerance
                )

                rules = evaluate_statutory_rules(MatchStatus.FUZZY_MATCH_REQUIRES_REVIEW, p_inv, b2b_inv, comparison.total_tax_diff)
                results.append(
                    ReconciliationResult(
                        status=MatchStatus.FUZZY_MATCH_REQUIRES_REVIEW,
                        purchase_invoice=p_inv,
                        matched_2b_invoice=b2b_inv,
                        taxable_difference=comparison.taxable_diff,
                        tax_difference=comparison.total_tax_diff,
                        confidence=0.70,
                        reason=f"Matched on GSTIN, date, and taxable value, but invoice numbering differs ('{p_inv.invoice_number}' vs '{b2b_inv.invoice_number}').",
                        rules_flagged=[r.rule_id for r in rules]
                    )
                )
                continue

            # Unmatched purchase invoice -> MISSING_IN_2B
            rules = evaluate_statutory_rules(MatchStatus.MISSING_IN_2B, p_inv, None, p_inv.total_tax)
            results.append(
                ReconciliationResult(
                    status=MatchStatus.MISSING_IN_2B,
                    purchase_invoice=p_inv,
                    matched_2b_invoice=None,
                    taxable_difference=p_inv.taxable_value,
                    tax_difference=p_inv.total_tax,
                    confidence=1.0,
                    reason="Invoice exists in purchase register but is missing in GSTR-2B statement.",
                    rules_flagged=[r.rule_id for r in rules]
                )
            )

        # 4. Any remaining unconsumed GSTR-2B invoices -> MISSING_IN_PURCHASE_REGISTER
        for idx, b2b_inv in enumerate(gstr2b_invoices):
            if idx not in consumed_2b_indices:
                results.append(
                    ReconciliationResult(
                        status=MatchStatus.MISSING_IN_PURCHASE_REGISTER,
                        purchase_invoice=None,
                        matched_2b_invoice=b2b_inv,
                        taxable_difference=-b2b_inv.taxable_value,
                        tax_difference=-b2b_inv.total_tax,
                        confidence=1.0,
                        reason="Invoice reported by supplier in GSTR-2B but absent from purchase ledger.",
                        rules_flagged=["RULE_MISSING_IN_BOOKS"]
                    )
                )

        return results
