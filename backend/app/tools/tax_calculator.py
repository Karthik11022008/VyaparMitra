from decimal import Decimal
from pydantic import BaseModel

DEFAULT_TOLERANCE = Decimal("1.00")

class TaxComparison(BaseModel):
    taxable_diff: Decimal
    cgst_diff: Decimal
    sgst_diff: Decimal
    igst_diff: Decimal
    total_tax_diff: Decimal
    is_within_tolerance: bool
    tolerance_applied: Decimal

def calculate_tax_differences(
    purchase_taxable: Decimal,
    purchase_cgst: Decimal,
    purchase_sgst: Decimal,
    purchase_igst: Decimal,
    gstr2b_taxable: Decimal,
    gstr2b_cgst: Decimal,
    gstr2b_sgst: Decimal,
    gstr2b_igst: Decimal,
    tolerance: Decimal = DEFAULT_TOLERANCE
) -> TaxComparison:
    """
    Deterministically computes monetary variance between purchase records and GSTR-2B.
    Positive difference indicates buyer claimed more credit than reported by supplier.
    """
    taxable_diff = round(purchase_taxable - gstr2b_taxable, 2)
    cgst_diff = round(purchase_cgst - gstr2b_cgst, 2)
    sgst_diff = round(purchase_sgst - gstr2b_sgst, 2)
    igst_diff = round(purchase_igst - gstr2b_igst, 2)
    
    total_purchase_tax = purchase_cgst + purchase_sgst + purchase_igst
    total_2b_tax = gstr2b_cgst + gstr2b_sgst + gstr2b_igst
    total_tax_diff = round(total_purchase_tax - total_2b_tax, 2)
    
    is_within_tolerance = (
        abs(taxable_diff) <= tolerance and
        abs(total_tax_diff) <= tolerance
    )
    
    return TaxComparison(
        taxable_diff=taxable_diff,
        cgst_diff=cgst_diff,
        sgst_diff=sgst_diff,
        igst_diff=igst_diff,
        total_tax_diff=total_tax_diff,
        is_within_tolerance=is_within_tolerance,
        tolerance_applied=tolerance
    )
