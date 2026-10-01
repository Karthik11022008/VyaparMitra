import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.agent.orchestrator import VyaparMitraOrchestrator, MAX_AGENT_ITERATIONS
from backend.app.agent.models import AgentRequest, AgentAnalyzeResponse
from backend.app.agent.tools_registry import (
    tool_validate_gstin,
    tool_normalize_invoice,
    tool_calculate_tax_differences,
    tool_calculate_section_50_interest,
    tool_lookup_statutory_rule,
    tool_run_reconciliation,
)
from backend.app.agent.dispute_notice import generate_dispute_notices
from backend.app.schemas.invoice import ReconciliationResult, PurchaseInvoice, MatchStatus

client = TestClient(app)

def test_agent_analyze_endpoint_success():
    payload = {"request": "Analyze the current purchase register and identify invoices requiring review."}
    response = client.post("/api/agent/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["session_id"].startswith("sess-")
    assert "summary" in data and len(data["summary"]) > 0
    assert len(data["findings"]) > 0
    assert len(data["actions"]) > 0
    assert "tool_run_reconciliation" in data["tools_used"]
    assert data["human_review_required"] is True
    assert "VyaparMitra is an accounting and reconciliation assistance system" in data["disclaimer"]

def test_agent_missing_api_key_graceful_fallback():
    # Orchestrator with no API key must fall back to deterministic synthesis without raising an error
    orchestrator = VyaparMitraOrchestrator(api_key="")
    req = AgentRequest(request="Check for delinquent supplier filings.")
    response = orchestrator.analyze(req)
    assert isinstance(response, AgentAnalyzeResponse)
    assert response.status == "success"
    assert len(response.actions) > 0
    assert response.human_review_required is True

def test_agent_malformed_request():
    # Empty payload
    res1 = client.post("/api/agent/analyze", json={})
    assert res1.status_code == 422

    # Request string too short (<3 chars)
    res2 = client.post("/api/agent/analyze", json={"request": "hi"})
    assert res2.status_code == 422

def test_deterministic_tool_invocations():
    # Normalization tool
    norm_res = tool_normalize_invoice(" INV-99 / 2026 ")
    assert norm_res["normalized"] == "INV992026"

    # GSTIN validation tool
    gstin_res = tool_validate_gstin("27AAPFU0939F1ZV")
    assert gstin_res["is_valid"] is True
    assert gstin_res["checksum_valid"] is True

    # Tax diff tool
    tax_res = tool_calculate_tax_differences(
        purchase_taxable=10000, purchase_cgst=900, purchase_sgst=900, purchase_igst=0,
        gstr2b_taxable=10000, gstr2b_cgst=900, gstr2b_sgst=900, gstr2b_igst=0
    )
    assert tax_res["total_tax_diff"] == 0.0
    assert tax_res["is_within_tolerance"] is True

    # Interest tool
    int_res = tool_calculate_section_50_interest(principal_tax=10000, delay_days=365, annual_rate=0.18)
    assert int_res["calculated_interest"] == 1800.0

    # Rule lookup tool
    rule_res = tool_lookup_statutory_rule("RULE_16_2_AA")
    assert "Section 16(2)(aa)" in rule_res["statutory_reference"]

def test_tool_failure_handling():
    # Non-existent rule ID returns error dictionary rather than raising unhandled exception
    res = tool_lookup_statutory_rule("UNKNOWN_RULE_XYZ")
    assert "error" in res

def test_agent_iteration_limit():
    assert MAX_AGENT_ITERATIONS <= 5
    orchestrator = VyaparMitraOrchestrator(api_key="")
    req = AgentRequest(request="Test loop bounds.")
    response = orchestrator.analyze(req)
    # Ensure tool execution respects bounded steps
    assert len(response.tools_used) <= MAX_AGENT_ITERATIONS

def test_human_review_requirement_enforced():
    orchestrator = VyaparMitraOrchestrator(api_key="")
    req = AgentRequest(request="Generate supplier notices.")
    response = orchestrator.analyze(req)
    assert response.human_review_required is True
    for action in response.actions:
        assert action.human_review_status == "DRAFT — REQUIRES HUMAN REVIEW"

def test_dispute_notice_generation_details():
    sample_result = ReconciliationResult(
        status=MatchStatus.MISSING_IN_2B,
        purchase_invoice=PurchaseInvoice(
            supplier_gstin="06AAACB1234F1ZD",
            invoice_number="HR-INV-305",
            invoice_date="2026-04-18",
            taxable_value=Decimal("30000.00"),
            igst=Decimal("5400.00")
        ),
        matched_2b_invoice=None,
        taxable_difference=Decimal("30000.00"),
        tax_difference=Decimal("5400.00"),
        confidence=1.0,
        reason="Missing in 2B statement.",
        rules_flagged=["RULE_16_2_AA"]
    )
    notices = generate_dispute_notices([sample_result])
    assert len(notices) == 1
    n = notices[0]
    assert n.supplier_reference == "06AAACB1234F1ZD"
    assert "HR-INV-305" in n.invoice_reference
    assert n.verified_amount == Decimal("5400.00")
    assert "Section 16(2)(aa)" in n.applicable_statutory_reference
    assert "GSTR-1" in n.requested_supplier_action
    assert n.human_review_status == "DRAFT — REQUIRES HUMAN REVIEW"
