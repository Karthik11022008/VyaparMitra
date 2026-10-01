import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.config import BASE_DIR

client = TestClient(app)

def test_full_end_to_end_demonstration_flow():
    # Step 1: Health check
    h_res = client.get("/api/health")
    assert h_res.status_code == 200
    assert h_res.json()["phase"] == "phase-4"

    # Step 2: Upload demo purchase register
    purchase_csv_path = BASE_DIR / "data" / "demo" / "purchase_register.csv"
    with open(purchase_csv_path, "rb") as f:
        p_content = f.read()
    p_res = client.post(
        "/api/reconciliation/upload/purchase-register",
        files={"file": ("purchase_register.csv", p_content, "text/csv")}
    )
    assert p_res.status_code == 200
    p_data = p_res.json()
    session_id = p_data["session_id"]
    assert p_data["row_count"] == 8
    assert p_data["validation_status"] == "VALID"

    # Step 3: Upload demo GSTR-2B
    gstr2b_csv_path = BASE_DIR / "data" / "demo" / "gstr2b.csv"
    with open(gstr2b_csv_path, "rb") as f:
        b_content = f.read()
    b_res = client.post(
        "/api/reconciliation/upload/gstr2b",
        files={"file": ("gstr2b.csv", b_content, "text/csv")},
        data={"session_id": session_id}
    )
    assert b_res.status_code == 200
    b_data = b_res.json()
    assert b_data["row_count"] == 6
    assert b_data["validation_status"] == "VALID"

    # Step 4: Validate both files
    assert p_data["validation_status"] == "VALID"
    assert b_data["validation_status"] == "VALID"

    # Step 5: Run deterministic reconciliation
    recon_res = client.post("/api/reconciliation/run", json={"session_id": session_id})
    assert recon_res.status_code == 200
    recon = recon_res.json()
    summary = recon["summary"]

    # Step 6: Verify results
    assert summary["total_purchase_invoices"] == 8
    assert summary["total_2b_invoices"] == 6
    assert summary["exact_matches"] == 2
    assert summary["missing_in_2b"] == 1
    assert float(summary["total_at_risk_itc"]) == 12960.00

    # Step 7: Run AI Agent analysis on real uploaded session
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

    # Step 8: Generate supplier draft
    notice = agent_data["actions"][0]
    notice_id = notice["notice_id"]

    # Step 9: Verify Human-in-the-Loop review status
    assert notice["human_review_status"] == "DRAFT — REQUIRES HUMAN REVIEW"
    act_res = client.post(
        f"/api/agent/notice/{notice_id}/action",
        json={"session_id": session_id, "action": "APPROVE"}
    )
    assert act_res.status_code == 200

    # Step 10: Export Reports (CSV & HTML)
    csv_res = client.get(f"/api/reconciliation/export/{session_id}/csv")
    assert csv_res.status_code == 200
    assert "VYAPARMITRA" in csv_res.text

    html_res = client.get(f"/api/reconciliation/export/{session_id}/html")
    assert html_res.status_code == 200
    assert "<!DOCTYPE html>" in html_res.text
    assert "VyaparMitra (व्यापार मित्र)" in html_res.text

    # Step 11: Verify audit trail
    audit_res = client.get(f"/api/reconciliation/audit/{session_id}")
    assert audit_res.status_code == 200
    events = [e["event_type"] for e in audit_res.json()["events"]]
    assert "FILE_UPLOADED" in events
    assert "FILE_VALIDATED" in events
    assert "RECONCILIATION_STARTED" in events
    assert "RECONCILIATION_COMPLETED" in events
    assert "AGENT_ANALYSIS_STARTED" in events
    assert "AGENT_ANALYSIS_COMPLETED" in events
    assert "NOTICE_APPROVED" in events
