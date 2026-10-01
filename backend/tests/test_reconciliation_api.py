from fastapi.testclient import TestClient
from backend.app.main import app

def test_demo_reconciliation_endpoint():
    client = TestClient(app)
    response = client.post("/api/reconciliation/demo")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    
    summary = data["summary"]
    assert summary["total_purchase_invoices"] == 8
    assert summary["total_2b_invoices"] == 6
    assert summary["exact_matches"] == 2
    assert summary["fuzzy_matches"] == 1
    assert summary["amount_mismatches"] == 1
    assert summary["missing_in_2b"] == 1
    assert summary["missing_in_purchase_register"] == 2
    assert summary["duplicate_candidates"] == 2
    assert summary["invalid_records"] == 1
    assert float(summary["total_purchase_itc"]) == 29700.00
    assert float(summary["total_2b_itc"]) == 21600.00
    assert float(summary["total_at_risk_itc"]) == 12960.00

    results = data["detailed_results"]
    assert len(results) == 10
