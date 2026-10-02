import pytest
from decimal import Decimal
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.agent.orchestrator import VyaparMitraOrchestrator
from backend.app.agent.models import AgentInvestigateRequest, AgentInvestigateResponse
from backend.app.agent.tools_registry import (
    tool_get_session_summary,
    tool_get_missing_invoices,
    tool_inspect_invoice,
    tool_get_supplier_discrepancies,
    tool_search_invoices,
)
from backend.app.services.reconciliation_service import reconcile_demo_dataset
from backend.app.database import get_audit_events

client = TestClient(app)


@pytest.fixture(scope="module")
def demo_session():
    """Ensures demo dataset reconciliation is cached and available."""
    recon = reconcile_demo_dataset()
    return recon


def test_investigate_itc_risk(demo_session):
    """Verifies intent classification, tool execution, and grounded answer for ITC risk."""
    orchestrator = VyaparMitraOrchestrator(api_key="")
    req = AgentInvestigateRequest(
        question="Why is my ITC at risk?",
        session_id=demo_session.session_id,
    )
    res = orchestrator.investigate(req)
    assert isinstance(res, AgentInvestigateResponse)
    assert res.status == "success"
    assert res.intent == "ITC_RISK"
    assert "tool_get_session_summary" in res.tools_used
    assert len(res.evidence) > 0
    assert len(res.answer) > 0
    assert "Section 16(2)(aa)" in res.answer
    assert "₹" in res.answer


def test_investigate_missing_in_2b(demo_session):
    """Verifies retrieval of missing in GSTR-2B invoices without LLM hallucination."""
    orchestrator = VyaparMitraOrchestrator(api_key="")
    req = AgentInvestigateRequest(
        question="Show me all invoices missing from GSTR-2B",
        session_id=demo_session.session_id,
    )
    res = orchestrator.investigate(req)
    assert res.status == "success"
    assert res.intent == "MISSING_IN_2B"
    assert "tool_get_missing_invoices" in res.tools_used
    assert len(res.evidence) == demo_session.summary.missing_in_2b
    for item in res.evidence:
        assert item.status == "MISSING_IN_2B"
        assert item.invoice_number is not None
        assert item.tax_difference is not None


def test_investigate_invoice_inspection_found(demo_session):
    """Verifies drill-down inspection of a specific flagged invoice."""
    flagged = next(
        (r for r in demo_session.detailed_results if r.status.value != "EXACT_MATCH"),
        None,
    )
    assert flagged is not None
    inv_num = flagged.purchase_invoice.invoice_number

    orchestrator = VyaparMitraOrchestrator(api_key="")
    req = AgentInvestigateRequest(
        question=f"Why was invoice {inv_num} flagged?",
        session_id=demo_session.session_id,
        invoice_context=inv_num,
    )
    res = orchestrator.investigate(req)
    assert res.status == "success"
    assert res.intent == "INVOICE_INSPECTION"
    assert "tool_inspect_invoice" in res.tools_used
    assert len(res.evidence) >= 1
    assert res.evidence[0].invoice_number == inv_num
    assert res.evidence[0].status == flagged.status.value


def test_investigate_invoice_inspection_not_found(demo_session):
    """Verifies graceful handling when an inspected invoice is not in the session."""
    orchestrator = VyaparMitraOrchestrator(api_key="")
    req = AgentInvestigateRequest(
        question="Inspect invoice UNKNOWN-9999-XYZ",
        session_id=demo_session.session_id,
    )
    res = orchestrator.investigate(req)
    assert res.status == "success"
    assert res.intent == "INVOICE_INSPECTION"
    assert "UNKNOWN-9999-XYZ" in res.answer
    assert "not found" in res.answer.lower()


def test_investigate_supplier_discrepancies(demo_session):
    """Verifies supplier-wise risk aggregation and ranking."""
    orchestrator = VyaparMitraOrchestrator(api_key="")
    req = AgentInvestigateRequest(
        question="Which suppliers have the most discrepancies?",
        session_id=demo_session.session_id,
    )
    res = orchestrator.investigate(req)
    assert res.status == "success"
    assert res.intent == "SUPPLIER_DISCREPANCIES"
    assert "tool_get_supplier_discrepancies" in res.tools_used
    assert len(res.evidence) > 0
    top_sup = res.evidence[0]
    assert top_sup.supplier_gstin is not None
    assert top_sup.tax_difference is not None


def test_investigate_tax_difference(demo_session):
    """Verifies tax variance calculation and tolerance checks."""
    orchestrator = VyaparMitraOrchestrator(api_key="")
    req = AgentInvestigateRequest(
        question="What is the tax difference between books and 2B?",
        session_id=demo_session.session_id,
    )
    res = orchestrator.investigate(req)
    assert res.status == "success"
    assert res.intent == "TAX_DIFFERENCE"
    assert "tool_calculate_tax_differences" in res.tools_used
    assert len(res.evidence) > 0
    tax_info = res.evidence[0]
    assert tax_info.purchase_tax is not None
    assert tax_info.gstr2b_tax is not None


def test_investigate_statutory_rule(demo_session):
    """Verifies statutory rule explanation lookup."""
    orchestrator = VyaparMitraOrchestrator(api_key="")
    req = AgentInvestigateRequest(
        question="Explain Section 16(2)(aa) statutory rule",
        session_id=demo_session.session_id,
    )
    res = orchestrator.investigate(req)
    assert res.status == "success"
    assert res.intent == "STATUTORY_RULE"
    assert "tool_lookup_statutory_rule" in res.tools_used
    assert len(res.evidence) > 0
    rule = res.evidence[0]
    assert "Section 16(2)(aa)" in rule.statutory_rule
    assert "GSTR-1" in rule.details


def test_investigate_interest_exposure(demo_session):
    """Verifies statutory interest exposure calculation under Section 50."""
    orchestrator = VyaparMitraOrchestrator(api_key="")
    req = AgentInvestigateRequest(
        question="What is our potential Section 50 interest exposure?",
        session_id=demo_session.session_id,
    )
    res = orchestrator.investigate(req)
    assert res.status == "success"
    assert res.intent == "INTEREST_EXPOSURE"
    assert "tool_calculate_section_50_interest" in res.tools_used
    assert len(res.evidence) > 0
    interest_info = res.evidence[0]
    assert "Section 50" in interest_info.statutory_rule
    assert "18%" in interest_info.details


def test_investigate_draft_notice_hitl(demo_session):
    """Verifies HITL protection: notices are drafts and require human review."""
    orchestrator = VyaparMitraOrchestrator(api_key="")
    req = AgentInvestigateRequest(
        question="Draft dispute notices for delinquent suppliers",
        session_id=demo_session.session_id,
    )
    res = orchestrator.investigate(req)
    assert res.status == "success"
    assert res.intent == "DRAFT_NOTICE"
    assert res.human_review_required is True
    assert res.draft_notice is not None
    assert res.draft_notice.human_review_status == "DRAFT — REQUIRES HUMAN REVIEW"
    assert len(res.draft_notice.supplier_reference) > 0
    assert res.draft_notice.verified_amount > 0


def test_investigate_empty_question(demo_session):
    """Verifies friendly guidance when prompt is blank."""
    orchestrator = VyaparMitraOrchestrator(api_key="")
    req = AgentInvestigateRequest(
        question="   ",
        session_id=demo_session.session_id,
    )
    res = orchestrator.investigate(req)
    assert res.status == "success"
    assert res.intent == "EMPTY_QUESTION"
    assert "reconciliation session" in res.answer


def test_investigate_fastapi_endpoint(demo_session):
    """Verifies the HTTP POST /api/agent/investigate endpoint contract."""
    payload = {
        "question": "Which suppliers have discrepancies and missing invoices?",
        "session_id": demo_session.session_id,
    }
    response = client.post("/api/agent/investigate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["intent"] == "SUPPLIER_DISCREPANCIES"
    assert len(data["tools_used"]) > 0
    assert len(data["evidence"]) > 0
    assert "disclaimer" in data
    assert "VyaparMitra is an accounting and reconciliation assistance system" in data["disclaimer"]


def test_investigate_audit_trail_recorded(demo_session):
    """Verifies that every investigation creates an immutable audit trail entry."""
    payload = {
        "question": "Show me missing invoices in GSTR-2B",
        "session_id": demo_session.session_id,
    }
    response = client.post("/api/agent/investigate", json=payload)
    assert response.status_code == 200

    # Verify database audit record
    trail = get_audit_events(session_id=demo_session.session_id)
    investigation_events = [e for e in trail if e["event_type"] == "AGENT_INVESTIGATION_COMPLETED"]
    assert len(investigation_events) >= 1
    last_event = investigation_events[-1]
    assert "details" in last_event
    assert "MISSING_IN_2B" in last_event["details"]


def test_backward_compatibility_analyze_endpoint():
    """Verifies existing /api/agent/analyze endpoint remains 100% operational."""
    payload = {"request": "Run comprehensive diagnostic reconciliation analysis."}
    response = client.post("/api/agent/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["session_id"].startswith("sess-")
    assert len(data["findings"]) > 0
    assert len(data["actions"]) > 0
    assert data["human_review_required"] is True
