from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel
from backend.app.schemas.invoice import MatchStatus, PurchaseInvoice, GSTR2BInvoice
from backend.app.tools.statutory_rules import STATUTORY_RULES_CATALOG, StatutoryRuleMetadata

class RuleEvaluationResult(BaseModel):
    rule_id: str
    statutory_reference: str
    review_summary: str
    recommended_action: str

def evaluate_statutory_rules(
    status: MatchStatus,
    purchase_inv: Optional[PurchaseInvoice],
    b2b_inv: Optional[GSTR2BInvoice],
    tax_difference: Decimal
) -> List[RuleEvaluationResult]:
    """
    Evaluates statutory compliance flags deterministically.
    Produces objective, professional accounting review notices without making legal conclusions.
    """
    triggered_rules: List[RuleEvaluationResult] = []

    def add_rule(rule_id: str, custom_summary: Optional[str] = None):
        meta: StatutoryRuleMetadata = STATUTORY_RULES_CATALOG[rule_id]
        triggered_rules.append(RuleEvaluationResult(
            rule_id=meta.rule_id,
            statutory_reference=meta.statutory_reference,
            review_summary=custom_summary or meta.compliance_summary,
            recommended_action=meta.review_guidance
        ))

    if status == MatchStatus.MISSING_IN_2B:
        add_rule("RULE_16_2_AA", "Invoice not reflected in GSTR-2B; ITC currently unverified for claim under Section 16(2)(aa).")
        add_rule("RULE_MISSING_2B")

    elif status == MatchStatus.AMOUNT_MISMATCH:
        if tax_difference > Decimal("0.00"):
            add_rule("RULE_AMOUNT_MISMATCH", f"Purchase ITC exceeds GSTR-2B by Rs. {tax_difference:,.2f}. Excess requires compliance review.")
        elif tax_difference < Decimal("0.00"):
            add_rule("RULE_AMOUNT_MISMATCH", f"GSTR-2B reflects higher tax (Rs. {abs(tax_difference):,.2f}) than recorded in purchase register. Verify internal books.")

    elif status == MatchStatus.FUZZY_MATCH_REQUIRES_REVIEW:
        add_rule("RULE_16_2_AA", "Invoice matched with variance in invoice numbering string. Human review required to confirm transaction identity.")

    # Time-barring check under Section 16(4) if invoice date is older than 18 months or from prior FY
    if purchase_inv and purchase_inv.invoice_date:
        try:
            # Check year in YYYY-MM-DD
            year = int(purchase_inv.invoice_date.split("-")[0])
            # If invoice is from 2024 or earlier in a 2026 tax period
            if year <= 2024:
                add_rule("RULE_16_4", f"Invoice dated {purchase_inv.invoice_date} may fall beyond statutory FY claim cutoff. Requires accounting verification.")
        except Exception:
            pass

    return triggered_rules
