from backend.app.tools.normalization import normalize_invoice_number, normalize_gstin

def test_invoice_normalization_basic():
    assert normalize_invoice_number(" INV-001 / 2026 ") == "INV0012026"
    assert normalize_invoice_number("INV001/2026") == "INV0012026"
    assert normalize_invoice_number("inv 001 2026") == "INV0012026"
    assert normalize_invoice_number("inv-001-2026") == "INV0012026"

def test_invoice_normalization_special_chars():
    assert normalize_invoice_number("BLR_SUP.9871-A\\B") == "BLRSUP9871AB"
    assert normalize_invoice_number("123/2025-26") == "123202526"

def test_invoice_normalization_edge_cases():
    assert normalize_invoice_number("") == ""
    assert normalize_invoice_number("   ") == ""
    assert normalize_invoice_number(None) == ""

def test_gstin_normalization():
    assert normalize_gstin(" 27aapfu0939f1zv ") == "27AAPFU0939F1ZV"
    assert normalize_gstin("") == ""
    assert normalize_gstin(None) == ""
