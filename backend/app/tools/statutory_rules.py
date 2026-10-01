from typing import Dict
from pydantic import BaseModel

class StatutoryRuleMetadata(BaseModel):
    rule_id: str
    title: str
    statutory_reference: str
    compliance_summary: str
    review_guidance: str
    disclaimer: str = "This notification is generated for commercial accounting reconciliation purposes only and does not constitute statutory legal advice."

STATUTORY_RULES_CATALOG: Dict[str, StatutoryRuleMetadata] = {
    "RULE_16_2_AA": StatutoryRuleMetadata(
        rule_id="RULE_16_2_AA",
        title="GSTR-2B Outward Supply Reflection Requirement",
        statutory_reference="Section 16(2)(aa) of the Central Goods and Services Tax Act, 2017",
        compliance_summary="Input Tax Credit is available only if invoice details are reported by the supplier in GSTR-1 and communicated to the recipient in GSTR-2B.",
        review_guidance="Verify whether the supplier has filed GSTR-1 for the corresponding tax period or if the transaction was recorded under an incorrect GSTIN."
    ),
    "RULE_16_4": StatutoryRuleMetadata(
        rule_id="RULE_16_4",
        title="Statutory ITC Availment Cut-Off Horizon",
        statutory_reference="Section 16(4) of the Central Goods and Services Tax Act, 2017",
        compliance_summary="ITC on any invoice or debit note cannot be availed after 30th November following the end of the financial year to which the invoice pertains, or the date of furnishing of the annual return, whichever is earlier.",
        review_guidance="Invoice date approaches or exceeds the statutory cutoff for the corresponding financial year. Prioritize immediate review before filing GSTR-3B."
    ),
    "RULE_37A": StatutoryRuleMetadata(
        rule_id="RULE_37A",
        title="ITC Reversal on Non-Payment of Tax by Supplier",
        statutory_reference="Rule 37A of the Central Goods and Services Tax Rules, 2017",
        compliance_summary="Where ITC has been availed by a registered person in GSTR-3B, but the supplier fails to furnish GSTR-3B for the corresponding tax period by the 30th November following the financial year end, the availed credit is subject to reversal.",
        review_guidance="Request supplier confirmation of GSTR-3B tax payment to prevent mandatory credit reversal."
    ),
    "RULE_AMOUNT_MISMATCH": StatutoryRuleMetadata(
        rule_id="RULE_AMOUNT_MISMATCH",
        title="Taxable / Tax Value Variance Between Purchase Ledger and GSTR-2B",
        statutory_reference="Section 16(2) read with Section 38 of the CGST Act",
        compliance_summary="Credit claimed in excess of the amount reported in GSTR-2B exposes the recipient to difference notices and interest under Section 50.",
        review_guidance="Buyer books reflect a higher tax amount than reported by the supplier. Reconcile invoice line-items or request an amended credit/debit note from the supplier."
    ),
    "RULE_MISSING_2B": StatutoryRuleMetadata(
        rule_id="RULE_MISSING_2B",
        title="Unreflected Purchase Entry in Auto-Drafted ITC Statement",
        statutory_reference="Circular No. 170/02/2022-GST & GSTR-2B Mechanism",
        compliance_summary="Invoice exists in internal purchase books but is absent in GSTR-2B statement for the current tax period.",
        review_guidance="Reach out to supplier with invoice particulars to ensure supply is uploaded in their next GSTR-1 outward return."
    ),
}
