import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

PURCHASE_DATA = """supplier_gstin,invoice_number,invoice_date,taxable_value,cgst,sgst,igst
27AAPFU0939F1ZV,INV-EXACT-01,2026-04-10,10000.00,900.00,900.00,0.00
06AAACB1234F1ZD,INV-MISMATCH-02,2026-04-12,20000.00,1800.00,1800.00,0.00
29AABCB1234F1Z4,INV-MISSING-03,2026-04-15,30000.00,0.00,0.00,5400.00
"""

GSTR2B_DATA = """supplier_gstin,invoice_number,invoice_date,taxable_value,cgst,sgst,igst
27AAPFU0939F1ZV,INV-EXACT-01,2026-04-10,10000.00,900.00,900.00,0.00
06AAACB1234F1ZD,INV-MISMATCH-02,2026-04-12,15000.00,1350.00,1350.00,0.00
"""

def test_full_reconciliation_session_lifecycle():
    # 1. Upload Purchase Register
    p_files = {"file": ("purchase_ledger.csv", PURCHASE_DATA.encode("utf-8"), "text/csv")}
    p_res = client.post("/api/reconciliation/upload/purchase-register", files=p_files)
    assert p_res.status_code == 200
    session_id = p_res.json()["session_id"]
    assert p_res.json()["row_count"] == 3

    # 2. Upload GSTR-2B using the same session ID
    b_files = {"file": ("gstr2b_statement.csv", GSTR2B_DATA.encode("utf-8"), "text/csv")}
    b_res = client.post(
        "/api/reconciliation/upload/gstr2b",
        files=b_files,
        data={"session_id": session_id}
    )
    assert b_res.status_code == 200
    assert b_res.json()["session_id"] == session_id
    assert b_res.json()["row_count"] == 2

    # 3. Check Session Info
    info_res = client.get(f"/api/reconciliation/session/{session_id}")
    assert info_res.status_code == 200
    info_data = info_res.json()
    assert info_data["session_id"] == session_id
    assert info_data["purchase_filename"] == "purchase_ledger.csv"
    assert info_data["gstr2b_filename"] == "gstr2b_statement.csv"

    # 4. Run Deterministic Reconciliation
    run_res = client.post("/api/reconciliation/run", json={"session_id": session_id})
    assert run_res.status_code == 200
    recon = run_res.json()
    assert recon["status"] == "success"
    summary = recon["summary"]

    assert summary["total_purchase_invoices"] == 3
    assert summary["total_2b_invoices"] == 2
    assert summary["exact_matches"] == 1
    assert summary["amount_mismatches"] == 1
    assert summary["missing_in_2b"] == 1
    # At-risk ITC: Mismatch diff (3600 - 2700 = 900) + Missing 2B (5400) = 6300.00
    assert float(summary["total_at_risk_itc"]) == 6300.0

def test_run_reconciliation_missing_session():
    res = client.post("/api/reconciliation/run", json={"session_id": "non_existent_session"})
    assert res.status_code == 400
