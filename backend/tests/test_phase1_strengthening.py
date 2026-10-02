import json
import uuid
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.invoice import (
    PurchaseInvoice,
    GSTR2BInvoice,
    MatchStatus,
    ReconciliationResult,
    SupplierSummary,
)
from backend.app.services.reconciliation_service import (
    build_supplier_summaries,
    run_reconciliation,
    reconcile_demo_dataset,
    restore_session_from_db,
    SESSION_DATA_CACHE,
)
from backend.app.database import get_reconciliation_history, get_reconciliation_session

client = TestClient(app)

def test_deterministic_supplier_summary_calculation():
    """Verifies that supplier summary is 100% deterministically aggregated without LLM."""
    results = [
        # Supplier 1: Exact match
        ReconciliationResult(
            status=MatchStatus.EXACT_MATCH,
            purchase_invoice=PurchaseInvoice(
                supplier_gstin="27AAPFU0939F1ZV",
                supplier_name="Acme Tools",
                invoice_number="INV-001",
                invoice_date="2026-04-10",
                taxable_value=Decimal("10000.00"),
                cgst=Decimal("900.00"),
                sgst=Decimal("900.00"),
                igst=Decimal("0.00"),
                total_value=Decimal("11800.00"),
            ),
            matched_2b_invoice=GSTR2BInvoice(
                supplier_gstin="27AAPFU0939F1ZV",
                supplier_name="Acme Tools",
                invoice_number="INV-001",
                invoice_date="2026-04-10",
                taxable_value=Decimal("10000.00"),
                cgst=Decimal("900.00"),
                sgst=Decimal("900.00"),
                igst=Decimal("0.00"),
            ),
            tax_difference=Decimal("0.00"),
            confidence=1.0,
            reason="Exact match on normalized invoice number, supplier GSTIN, and tax value.",
        ),
        # Supplier 1: Missing in 2B (At risk ITC: 1800.00)
        ReconciliationResult(
            status=MatchStatus.MISSING_IN_2B,
            purchase_invoice=PurchaseInvoice(
                supplier_gstin="27AAPFU0939F1ZV",
                supplier_name="Acme Tools",
                invoice_number="INV-002",
                invoice_date="2026-04-12",
                taxable_value=Decimal("10000.00"),
                cgst=Decimal("900.00"),
                sgst=Decimal("900.00"),
                igst=Decimal("0.00"),
                total_value=Decimal("11800.00"),
            ),
            matched_2b_invoice=None,
            tax_difference=Decimal("1800.00"),
            confidence=0.0,
            reason="Invoice recorded in buyer books but absent in GSTR-2B.",
        ),
        # Supplier 2: Amount Mismatch (At risk difference: 500.00)
        ReconciliationResult(
            status=MatchStatus.AMOUNT_MISMATCH,
            purchase_invoice=PurchaseInvoice(
                supplier_gstin="29AABCU9603R1ZJ",
                supplier_name="Karnataka Tech",
                invoice_number="INV-042",
                invoice_date="2026-04-14",
                taxable_value=Decimal("25000.00"),
                cgst=Decimal("2500.00"),
                sgst=Decimal("2500.00"),
                igst=Decimal("0.00"),
                total_value=Decimal("30000.00"),
            ),
            matched_2b_invoice=GSTR2BInvoice(
                supplier_gstin="29AABCU9603R1ZJ",
                supplier_name="Karnataka Tech",
                invoice_number="INV-042",
                invoice_date="2026-04-14",
                taxable_value=Decimal("22500.00"),
                cgst=Decimal("2250.00"),
                sgst=Decimal("2250.00"),
                igst=Decimal("0.00"),
            ),
            tax_difference=Decimal("500.00"),
            confidence=0.9,
            reason="Tax value discrepancy detected between books and portal.",
        ),
    ]

    summaries = build_supplier_summaries(results)
    assert len(summaries) == 2

    # Top risk supplier must be Supplier 1 with Rs 1800 at-risk ITC
    top_supplier = summaries[0]
    assert top_supplier.supplier_gstin == "27AAPFU0939F1ZV"
    assert top_supplier.supplier_name == "Acme Tools"
    assert top_supplier.total_invoices == 2
    assert top_supplier.exact_matches == 1
    assert top_supplier.missing_in_2b == 1
    assert top_supplier.total_at_risk_itc == Decimal("1800.00")

    # Second supplier
    second_supplier = summaries[1]
    assert second_supplier.supplier_gstin == "29AABCU9603R1ZJ"
    assert second_supplier.supplier_name == "Karnataka Tech"
    assert second_supplier.total_invoices == 1
    assert second_supplier.amount_mismatches == 1
    assert second_supplier.total_at_risk_itc == Decimal("500.00")

def test_demo_reconciliation_includes_supplier_summaries():
    """Verifies that demo reconciliation generates non-empty supplier summaries."""
    resp = reconcile_demo_dataset("test-phase1-demo")
    assert resp.supplier_summaries is not None
    assert len(resp.supplier_summaries) > 0

    # Ensure all required fields exist on each summary
    for s in resp.supplier_summaries:
        assert s.supplier_gstin != ""
        assert s.total_invoices > 0
        assert isinstance(s.total_at_risk_itc, Decimal)
        assert s.supplier_name != ""

def test_api_reconciliation_history_endpoint():
    """Tests GET /api/reconciliation/history returns previous sessions."""
    # Ensure at least one session exists with a fresh unique ID
    test_sid = f"sess-hist-{uuid.uuid4().hex[:8]}"
    reconcile_demo_dataset(test_sid)

    response = client.get("/api/reconciliation/history")
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "sessions" in data
    assert data["count"] > 0
    session_ids = [s["session_id"] for s in data["sessions"]]
    assert test_sid in session_ids

def test_api_session_results_endpoint_and_cache_recovery():
    """Tests session recovery from SQLite after in-memory cache is purged."""
    sid = "sess-recovery-test"
    orig_resp = reconcile_demo_dataset(sid)
    assert orig_resp.summary.exact_matches == 2

    # Clear in-memory cache to simulate server restart
    if sid in SESSION_DATA_CACHE:
        del SESSION_DATA_CACHE[sid]

    # Verify cache is empty for this session
    assert sid not in SESSION_DATA_CACHE or SESSION_DATA_CACHE[sid].get("reconciliation_response") is None

    # Call GET /api/reconciliation/session/{session_id}/results
    response = client.get(f"/api/reconciliation/session/{sid}/results")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["summary"]["exact_matches"] == 2
    assert len(data["detailed_results"]) == 10
    assert len(data["supplier_summaries"]) > 0

def test_api_session_suppliers_endpoint():
    """Tests GET /api/reconciliation/session/{session_id}/suppliers."""
    sid = "sess-suppliers-test"
    reconcile_demo_dataset(sid)

    response = client.get(f"/api/reconciliation/session/{sid}/suppliers")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == sid
    assert data["supplier_count"] > 0
    assert len(data["suppliers"]) == data["supplier_count"]

    first_supplier = data["suppliers"][0]
    assert "supplier_gstin" in first_supplier
    assert "supplier_name" in first_supplier
    assert "total_at_risk_itc" in first_supplier
    assert "exact_matches" in first_supplier
    assert "amount_mismatches" in first_supplier
    assert "missing_in_2b" in first_supplier
