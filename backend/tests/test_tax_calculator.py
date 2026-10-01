from decimal import Decimal
from backend.app.tools.tax_calculator import calculate_tax_differences

def test_exact_tax_match():
    res = calculate_tax_differences(
        purchase_taxable=Decimal("10000.00"),
        purchase_cgst=Decimal("900.00"),
        purchase_sgst=Decimal("900.00"),
        purchase_igst=Decimal("0.00"),
        gstr2b_taxable=Decimal("10000.00"),
        gstr2b_cgst=Decimal("900.00"),
        gstr2b_sgst=Decimal("900.00"),
        gstr2b_igst=Decimal("0.00")
    )
    assert res.taxable_diff == Decimal("0.00")
    assert res.cgst_diff == Decimal("0.00")
    assert res.sgst_diff == Decimal("0.00")
    assert res.igst_diff == Decimal("0.00")
    assert res.total_tax_diff == Decimal("0.00")
    assert res.is_within_tolerance is True

def test_tax_variance_within_tolerance():
    # 50 paise rounding difference
    res = calculate_tax_differences(
        purchase_taxable=Decimal("10000.50"),
        purchase_cgst=Decimal("900.00"),
        purchase_sgst=Decimal("900.00"),
        purchase_igst=Decimal("0.00"),
        gstr2b_taxable=Decimal("10000.00"),
        gstr2b_cgst=Decimal("900.00"),
        gstr2b_sgst=Decimal("900.00"),
        gstr2b_igst=Decimal("0.00"),
        tolerance=Decimal("1.00")
    )
    assert res.taxable_diff == Decimal("0.50")
    assert res.is_within_tolerance is True

def test_tax_variance_beyond_tolerance():
    res = calculate_tax_differences(
        purchase_taxable=Decimal("50000.00"),
        purchase_cgst=Decimal("4500.00"),
        purchase_sgst=Decimal("4500.00"),
        purchase_igst=Decimal("0.00"),
        gstr2b_taxable=Decimal("40000.00"),
        gstr2b_cgst=Decimal("3600.00"),
        gstr2b_sgst=Decimal("3600.00"),
        gstr2b_igst=Decimal("0.00")
    )
    assert res.taxable_diff == Decimal("10000.00")
    assert res.total_tax_diff == Decimal("1800.00")
    assert res.is_within_tolerance is False
