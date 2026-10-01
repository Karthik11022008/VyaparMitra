import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

PURCHASE_DATA = """supplier_gstin,invoice_number,invoice_date,taxable_value,cgst,sgst,igst
27AAPFU0939F1ZV,INV-EXACT-01,2026-04-10,10000.00,900.00,900.00,0.00
"""

GSTR2B_DATA = """supplier_gstin,invoice_number,invoice_date,taxable_value,cgst,sgst,igst
27AAPFU0939F1ZV,INV-EXACT-01,2026-04-10,10000.00,900.00,900.00,0.00
"""

def setup_test_session():
    # Setup session with reconciled data
    p_res = client.post(
        "/api/reconciliation/upload/purchase-register",
        files={"file": ("p.csv", PURCHASE_DATA.encode("utf-8"), "text/csv")}
    )
    session_id = p_res.json()["session_id"]
    client.post(
        "/api/reconciliation/upload/gstr2b",
        files={"file": ("b.csv", GSTR2B_DATA.encode("utf-8"), "text/csv")},
        data={"session_id": session_id}
    )
    client.post("/api/reconciliation/run", json={"session_id": session_id})
    return session_id

def test_export_csv_report():
    session_id = setup_test_session()
    res = client.get(f"/api/reconciliation/export/{session_id}/csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert f"VyaparMitra_Recon_{session_id}.csv" in res.headers["content-disposition"]
    text = res.text
    assert "VYAPARMITRA GST RECONCILIATION AUDIT REPORT" in text
    assert session_id in text
    assert "STATUTORY DISCLAIMER" in text
    assert "INV-EXACT-01" in text

def test_export_html_report():
    session_id = setup_test_session()
    res = client.get(f"/api/reconciliation/export/{session_id}/html")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert f"VyaparMitra_Report_{session_id}.html" in res.headers["content-disposition"]
    html = res.text
    assert "VyaparMitra (व्यापार मित्र)" in html
    assert session_id in html
    assert "STATUTORY DISCLAIMER" in html
    assert "Exact Matches" in html

def test_export_unreconciled_session_returns_400():
    unknown_id = "nonexistent-sess-9999"
    csv_res = client.get(f"/api/reconciliation/export/{unknown_id}/csv")
    assert csv_res.status_code == 400
    assert csv_res.json()["detail"] == "Reconciliation has not been executed for this session yet."

    html_res = client.get(f"/api/reconciliation/export/{unknown_id}/html")
    assert html_res.status_code == 400
    assert html_res.json()["detail"] == "Reconciliation has not been executed for this session yet."

def test_export_demo_dataset_csv_and_html():
    demo_res = client.post("/api/reconciliation/demo")
    assert demo_res.status_code == 200
    demo_data = demo_res.json()
    session_id = demo_data.get("session_id")
    assert session_id is not None
    assert session_id.startswith("sess-demo-")

    csv_res = client.get(f"/api/reconciliation/export/{session_id}/csv")
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    assert "VYAPARMITRA GST RECONCILIATION AUDIT REPORT" in csv_res.text
    assert session_id in csv_res.text

    html_res = client.get(f"/api/reconciliation/export/{session_id}/html")
    assert html_res.status_code == 200
    assert "text/html" in html_res.headers["content-type"]
    assert "VyaparMitra (व्यापार मित्र)" in html_res.text
    assert session_id in html_res.text

def test_export_demo_session_alias_fallback():
    csv_res = client.get("/api/reconciliation/export/demo-session/csv")
    assert csv_res.status_code == 200
    assert "VYAPARMITRA GST RECONCILIATION AUDIT REPORT" in csv_res.text

    html_res = client.get("/api/reconciliation/export/demo-session/html")
    assert html_res.status_code == 200
    assert "VyaparMitra (व्यापार मित्र)" in html_res.text
