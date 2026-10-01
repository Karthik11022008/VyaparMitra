from decimal import Decimal
from typing import List, Optional
import uuid
from backend.app.schemas.invoice import ReconciliationResult, MatchStatus
from backend.app.agent.models import SupplierDisputeNotice
from backend.app.tools.statutory_rules import STATUTORY_RULES_CATALOG

def generate_dispute_notices(reconciliation_items: List[ReconciliationResult]) -> List[SupplierDisputeNotice]:
    """
    Deterministically generates structured supplier dispute notices based strictly on reconciliation findings.
    All notices are created with 'DRAFT — REQUIRES HUMAN REVIEW' status.
    """
    notices: List[SupplierDisputeNotice] = []
    notice_counter = 1

    for item in reconciliation_items:
        # Generate notice only for discrepancies requiring supplier action
        if item.status not in (
            MatchStatus.MISSING_IN_2B,
            MatchStatus.AMOUNT_MISMATCH,
            MatchStatus.FUZZY_MATCH_REQUIRES_REVIEW
        ):
            continue

        p_inv = item.purchase_invoice
        b_inv = item.matched_2b_invoice
        if not p_inv:
            continue

        notice_id = f"NOT-2026-{notice_counter:03d}"
        notice_counter += 1

        supplier_ref = p_inv.supplier_gstin
        inv_ref = f"{p_inv.invoice_number} (Dated: {p_inv.invoice_date})"
        
        statutory_ref = "Section 16(2)(aa) read with Section 50 of the CGST Act, 2017"
        if item.rules_flagged and item.rules_flagged[0] in STATUTORY_RULES_CATALOG:
            statutory_ref = STATUTORY_RULES_CATALOG[item.rules_flagged[0]].statutory_reference

        b2b_tax = b_inv.total_tax if b_inv else Decimal("0.00")
        b2b_inv_num = b_inv.invoice_number if b_inv else ""

        if item.status == MatchStatus.MISSING_IN_2B:
            discrepancy = "Invoice present in buyer's purchase ledger but unreflected in GSTR-2B statement."
            verified_amount = p_inv.total_tax
            requested_action = (
                f"Please verify outward supply reporting and furnish this invoice in your upcoming GSTR-1 return "
                f"to enable valid Input Tax Credit entitlement under Section 16(2)(aa)."
            )
            body = (
                f"Dear Accounts Team,\n\n"
                f"During our routine monthly GST reconciliation for tax period {p_inv.tax_period}, we noted that "
                f"Invoice #{p_inv.invoice_number} dated {p_inv.invoice_date} for taxable value Rs. {p_inv.taxable_value:,.2f} "
                f"(Tax: Rs. {p_inv.total_tax:,.2f}) has not appeared in our auto-drafted GSTR-2B statement.\n\n"
                f"As per {statutory_ref}, recipient credit is contingent on supplier outward filing. "
                f"We kindly request you to confirm inclusion of this invoice in your next GSTR-1 filing.\n\n"
                f"Regards,\nAccounts Department"
            )

        elif item.status == MatchStatus.AMOUNT_MISMATCH:
            discrepancy = (
                f"Tax variance detected. Buyer books reflect tax of Rs. {p_inv.total_tax:,.2f}, "
                f"whereas GSTR-2B reflects Rs. {b2b_tax:,.2f} "
                f"(Variance: Rs. {item.tax_difference:,.2f})."
            )
            verified_amount = abs(item.tax_difference)
            requested_action = (
                f"Please review line-item tax details and furnish an amended GSTR-1 entry or credit/debit note "
                f"to resolve the variance of Rs. {item.tax_difference:,.2f}."
            )
            body = (
                f"Dear Accounts Team,\n\n"
                f"Regarding Invoice #{p_inv.invoice_number} dated {p_inv.invoice_date}, our records reflect a tax amount of "
                f"Rs. {p_inv.total_tax:,.2f} while the GSTR-2B portal shows Rs. {b2b_tax:,.2f}.\n\n"
                f"Kindly reconcile the difference of Rs. {item.tax_difference:,.2f} and issue an amendment or confirmation.\n\n"
                f"Regards,\nAccounts Department"
            )

        elif item.status == MatchStatus.FUZZY_MATCH_REQUIRES_REVIEW:
            discrepancy = (
                f"Invoice number formatting variance. Buyer recorded '{p_inv.invoice_number}', "
                f"while GSTR-2B shows '{b2b_inv_num}'."
            )
            verified_amount = Decimal("0.00")
            requested_action = "Please confirm whether this entry corresponds to our purchase order so records can be harmonized."
            body = (
                f"Dear Accounts Team,\n\n"
                f"We identified a minor invoice numbering variation regarding purchase date {p_inv.invoice_date}. "
                f"Our books record #{p_inv.invoice_number} while your portal filing shows #{b2b_inv_num}.\n\n"
                f"Please confirm transaction identity for internal cross-referencing.\n\n"
                f"Regards,\nAccounts Department"
            )

        notices.append(
            SupplierDisputeNotice(
                notice_id=notice_id,
                supplier_reference=supplier_ref,
                invoice_reference=inv_ref,
                discrepancy=discrepancy,
                verified_amount=verified_amount,
                applicable_statutory_reference=statutory_ref,
                requested_supplier_action=requested_action,
                human_review_status="DRAFT — REQUIRES HUMAN REVIEW",
                notice_body=body
            )
        )

    return notices
