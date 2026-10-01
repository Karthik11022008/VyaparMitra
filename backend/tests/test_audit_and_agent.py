import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

PURCHASE_DATA = """supplier_gstin,invoice_number,invoice_date,taxable_value,cgst,sgst,igst
06AAACB1234F1ZD,INV-MISSING-99,2026-04-12,20000.00,0.00,0.00,3600.00
"""

GSTR2B_DATA = """supplier_gstin,invoice_number,invoice_date,taxable_value,cgst,sgst,igst
27AAPFU0939F1ZV,INV-UNRELATED-01,2026-04-10,10000.00,900.00,900.00,0.00
"""

def test_agent_with_uploaded_session_and_audit_trail():
    # 1. Ingest files
    p_res = client.post(
        "/api/reconciliation/upload/purchase-register",
        files={"file": ("books.csv", PURCHASE_DATA.encode("utf-8"), "text/csv")}
    )
    session_id = p_res.json()["session_id"]
    client.post(
        "/api/reconciliation/upload/gstr2b",
        files={"file": ("gstr2b.csv", GSTR2B_DATA.encode("utf-8"), "text/csv")},
        data={"session_id": session_id}
    )

    # 2. Run reconciliation
    client.post("/api/reconciliation/run", json={"session_id": session_id})

    # 3. Request Agent Analysis using the uploaded session_id
    agent_res = client.post(
        "/api/agent/analyze",
        json={
            "request": "Analyze discrepancies for this uploaded dataset and generate vendor communications.",
            "session_id": session_id
        }
    )
    assert agent_res.status_code == 200
    agent_data = agent_res.json()
    assert agent_data["session_id"] == session_id
    assert len(agent_data["findings"]) > 0
    assert len(agent_data["actions"]) > 0

    notice = agent_data["actions"][0]
    notice_id = notice["notice_id"]

    # 4. Human-in-the-Loop decision: Approve Notice
    action_res = client.post(
        f"/api/agent/notice/{notice_id}/action",
        json={"session_id": session_id, "action": "APPROVE"}
    )
    assert action_res.status_code == 200
    assert action_res.json()["status"] == "success"

    # 5. Check Audit Trail
    audit_res = client.get(f"/api/reconciliation/audit/{session_id}")
    assert audit_res.status_code == 200
    audit_data = audit_res.json()
    assert audit_data["session_id"] == session_id
    event_types = [e["event_type"] for e in audit_data["events"]]

    assert "FILE_UPLOADED" in event_types
    assert "FILE_VALIDATED" in event_types
    assert "RECONCILIATION_STARTED" in event_types
    assert "RECONCILIATION_COMPLETED" in event_types
    assert "AGENT_ANALYSIS_STARTED" in event_types
    assert "AGENT_ANALYSIS_COMPLETED" in event_types
    assert "NOTICE_APPROVED" in event_types
