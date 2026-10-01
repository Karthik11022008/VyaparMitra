from decimal import Decimal
from backend.app.schemas.invoice import PurchaseInvoice, GSTR2BInvoice, MatchStatus
from backend.app.tools.matching_engine import InvoiceMatchingEngine

def test_exact_invoice_match():
    p = [
        PurchaseInvoice(
            supplier_gstin="27AAPFU0939F1ZV",
            invoice_number="INV-001",
            invoice_date="2026-04-10",
            taxable_value=Decimal("10000.00"),
            cgst=Decimal("900.00"),
            sgst=Decimal("900.00")
        )
    ]
    b = [
        GSTR2BInvoice(
            supplier_gstin="27AAPFU0939F1ZV",
            invoice_number="INV-001",
            invoice_date="2026-04-10",
            taxable_value=Decimal("10000.00"),
            cgst=Decimal("900.00"),
            sgst=Decimal("900.00")
        )
    ]
    engine = InvoiceMatchingEngine()
    results = engine.reconcile(p, b)
    assert len(results) == 1
    assert results[0].status == MatchStatus.EXACT_MATCH
    assert results[0].taxable_difference == Decimal("0.00")
    assert results[0].confidence == 1.0

def test_normalized_formatting_match():
    # INV/2026/042 vs INV-2026-042
    p = [
        PurchaseInvoice(
            supplier_gstin="29AABCU9603R1ZJ",
            invoice_number="INV/2026/042",
            invoice_date="2026-04-12",
            taxable_value=Decimal("25000.00"),
            cgst=Decimal("2250.00"),
            sgst=Decimal("2250.00")
        )
    ]
    b = [
        GSTR2BInvoice(
            supplier_gstin="29AABCU9603R1ZJ",
            invoice_number="INV-2026-042",
            invoice_date="2026-04-12",
            taxable_value=Decimal("25000.00"),
            cgst=Decimal("2250.00"),
            sgst=Decimal("2250.00")
        )
    ]
    engine = InvoiceMatchingEngine()
    results = engine.reconcile(p, b)
    assert len(results) == 1
    assert results[0].status == MatchStatus.EXACT_MATCH

def test_fuzzy_match_requires_review():
    p = [
        PurchaseInvoice(
            supplier_gstin="29AABCU9603R1ZJ",
            invoice_number="BLR-SUP-9871",
            invoice_date="2026-04-14",
            taxable_value=Decimal("18000.00"),
            igst=Decimal("3240.00")
        )
    ]
    b = [
        GSTR2BInvoice(
            supplier_gstin="29AABCU9603R1ZJ",
            invoice_number="BLR-SUP-9871A",
            invoice_date="2026-04-14",
            taxable_value=Decimal("18000.00"),
            igst=Decimal("3240.00")
        )
    ]
    engine = InvoiceMatchingEngine(fuzzy_threshold=85.0)
    results = engine.reconcile(p, b)
    assert len(results) == 1
    assert results[0].status == MatchStatus.FUZZY_MATCH_REQUIRES_REVIEW
    assert results[0].confidence >= 0.85

def test_amount_mismatch():
    p = [
        PurchaseInvoice(
            supplier_gstin="07AAAAA0000A1Z4",
            invoice_number="DEL-101",
            invoice_date="2026-04-15",
            taxable_value=Decimal("50000.00"),
            cgst=Decimal("4500.00"),
            sgst=Decimal("4500.00")
        )
    ]
    b = [
        GSTR2BInvoice(
            supplier_gstin="07AAAAA0000A1Z4",
            invoice_number="DEL-101",
            invoice_date="2026-04-15",
            taxable_value=Decimal("40000.00"),
            cgst=Decimal("3600.00"),
            sgst=Decimal("3600.00")
        )
    ]
    engine = InvoiceMatchingEngine()
    results = engine.reconcile(p, b)
    assert len(results) == 1
    assert results[0].status == MatchStatus.AMOUNT_MISMATCH
    assert results[0].taxable_difference == Decimal("10000.00")
    assert results[0].tax_difference == Decimal("1800.00")

def test_missing_in_2b():
    p = [
        PurchaseInvoice(
            supplier_gstin="06AAACB1234F1ZD",
            invoice_number="HR-INV-305",
            invoice_date="2026-04-18",
            taxable_value=Decimal("30000.00"),
            igst=Decimal("5400.00")
        )
    ]
    engine = InvoiceMatchingEngine()
    results = engine.reconcile(p, [])
    assert len(results) == 1
    assert results[0].status == MatchStatus.MISSING_IN_2B
    assert results[0].tax_difference == Decimal("5400.00")

def test_missing_in_purchase_register():
    b = [
        GSTR2BInvoice(
            supplier_gstin="27AAPFU0939F1ZV",
            invoice_number="MUM-888",
            invoice_date="2026-04-20",
            taxable_value=Decimal("15000.00"),
            cgst=Decimal("1350.00"),
            sgst=Decimal("1350.00")
        )
    ]
    engine = InvoiceMatchingEngine()
    results = engine.reconcile([], b)
    assert len(results) == 1
    assert results[0].status == MatchStatus.MISSING_IN_PURCHASE_REGISTER

def test_duplicate_candidate():
    p1 = PurchaseInvoice(
        supplier_gstin="27AAPFU0939F1ZV",
        invoice_number="DUP-777",
        invoice_date="2026-04-22",
        taxable_value=Decimal("12000.00"),
        cgst=Decimal("1080.00"),
        sgst=Decimal("1080.00")
    )
    p2 = PurchaseInvoice(
        supplier_gstin="27AAPFU0939F1ZV",
        invoice_number="DUP-777",
        invoice_date="2026-04-22",
        taxable_value=Decimal("12000.00"),
        cgst=Decimal("1080.00"),
        sgst=Decimal("1080.00")
    )
    engine = InvoiceMatchingEngine()
    results = engine.reconcile([p1, p2], [])
    assert len(results) == 2
    assert results[0].status == MatchStatus.DUPLICATE_CANDIDATE
    assert results[1].status == MatchStatus.DUPLICATE_CANDIDATE

def test_invalid_gstin_record():
    p = [
        PurchaseInvoice(
            supplier_gstin="99INVALID1234ZZZ",
            invoice_number="BAD-INV",
            invoice_date="2026-04-25",
            taxable_value=Decimal("8000.00"),
            cgst=Decimal("720.00"),
            sgst=Decimal("720.00")
        )
    ]
    engine = InvoiceMatchingEngine()
    results = engine.reconcile(p, [])
    assert len(results) == 1
    assert results[0].status == MatchStatus.INVALID_DATA
