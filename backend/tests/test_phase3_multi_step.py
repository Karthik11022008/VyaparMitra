import pytest
import json
from decimal import Decimal
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.agent.orchestrator import VyaparMitraOrchestrator
from backend.app.agent.models import (
    AgentInvestigateRequest,
    AgentInvestigateResponse,
    ToolCallRequest,
    AgentStepTrace,
)
from backend.app.agent.tools_registry import (
    AVAILABLE_TOOLS,
    TOOL_CONTRACTS,
    TOOL_DEFINITIONS,
    validate_and_call_tool,
)
from backend.app.services.reconciliation_service import reconcile_demo_dataset
from backend.app.database import get_audit_events

client = TestClient(app)


@pytest.fixture(scope="module")
def demo_session():
    """Provides a deterministically reconciled demo dataset session."""
    recon = reconcile_demo_dataset()
    return recon


# ==============================================================================
# 1. TOOL CONTRACT & VALIDATION TESTS
# ==============================================================================

def test_tool_catalog_all_contracts_declared():
    """Verifies that all registered tools have complete contracts and parameter schemas."""
    assert len(AVAILABLE_TOOLS) >= 11
    for tool_name in AVAILABLE_TOOLS:
        assert tool_name in TOOL_CONTRACTS, f"Tool '{tool_name}' missing contract"
        contract = TOOL_CONTRACTS[tool_name]
        assert contract.name == tool_name
        assert len(contract.description) > 0
        assert contract.category in [
            "reconciliation", "validation", "normalization",
            "calculation", "statutory_lookup", "data_retrieval"
        ]
        assert contract.is_deterministic is True


def test_tool_definitions_for_gemini_formatting():
    """Verifies tool declarations formatting matches expected function-calling schema."""
    assert len(TOOL_DEFINITIONS) == len(TOOL_CONTRACTS)
    for td in TOOL_DEFINITIONS:
        assert "name" in td
        assert "description" in td
        assert "parameters" in td
        assert td["parameters"]["type"].lower() == "object"


def test_validate_and_call_tool_unknown_tool():
    """Verifies rejection of unregistered tool names with clean error trace."""
    res = validate_and_call_tool("tool_unknown_arbitrary_cmd", {"arg": 123})
    assert res["success"] is False
    assert res["status"] == "ERROR"
    assert "not in the registered tool catalog" in res["observation_summary"]
    assert res["data"] is None
    assert res["duration_ms"] >= 0


def test_validate_and_call_tool_missing_required_param():
    """Verifies rejection when a required parameter is omitted."""
    # tool_lookup_statutory_rule requires 'rule_id'
    res = validate_and_call_tool("tool_lookup_statutory_rule", {})
    assert res["success"] is False
    assert res["status"] == "ERROR"
    assert "Missing required parameter 'rule_id'" in res["observation_summary"]


def test_validate_and_call_tool_requires_session_enforcement():
    """Verifies session requirement is strictly enforced for data retrieval tools."""
    res = validate_and_call_tool("tool_get_session_summary", {}, session_id=None)
    assert res["success"] is False
    assert res["status"] == "ERROR"
    assert "requires an active session_id" in res["observation_summary"]


def test_validate_and_call_tool_success_trace(demo_session):
    """Verifies successful tool execution returns complete metadata and observation summary."""
    res = validate_and_call_tool(
        "tool_get_session_summary",
        {},
        session_id=demo_session.session_id,
        step_index=1,
    )
    assert res["success"] is True
    assert res["status"] == "SUCCESS"
    assert res["step_index"] == 1
    assert res["data"] is not None
    assert "purchase vs" in res["observation_summary"]
    assert res["duration_ms"] >= 0
    assert "timestamp" in res


# ==============================================================================
# 2. MULTI-STEP REASONING CHAINS & PLANNING TESTS
# ==============================================================================

def test_investigate_plan_generation(demo_session):
    """Verifies the agent formulates a multi-step strategic plan before execution."""
    orchestrator = VyaparMitraOrchestrator(api_key="")
    req = AgentInvestigateRequest(
        question="Why is my ITC at risk?",
        session_id=demo_session.session_id,
    )
    res = orchestrator.investigate(req)
    assert isinstance(res.plan, list)
    assert len(res.plan) >= 2
    assert any("ITC" in p or "at-risk" in p for p in res.plan)
    assert any("Section 16" in p for p in res.plan)


def test_investigate_step_traces_collected(demo_session):
    """Verifies step-by-step traces are recorded with index, duration, status, and summary."""
    orchestrator = VyaparMitraOrchestrator(api_key="")
    req = AgentInvestigateRequest(
        question="Why is my ITC at risk?",
        session_id=demo_session.session_id,
    )
    res = orchestrator.investigate(req)
    assert len(res.steps_executed) >= 2
    for idx, trace in enumerate(res.steps_executed, start=1):
        assert isinstance(trace, AgentStepTrace)
        assert trace.step_index == idx
        assert trace.tool_name.startswith("tool_")
        assert trace.status == "SUCCESS"
        assert trace.duration_ms >= 0
        assert len(trace.observation_summary) > 0


def test_two_step_reasoning_chain(demo_session):
    """Verifies a 2-step chain: retrieve missing invoices -> look up statutory rule."""
    orchestrator = VyaparMitraOrchestrator(api_key="")
    req = AgentInvestigateRequest(
        question="Show me all invoices missing from GSTR-2B",
        session_id=demo_session.session_id,
    )
    res = orchestrator.investigate(req)
    executed_tool_names = [st.tool_name for st in res.steps_executed]
    assert "tool_get_missing_invoices" in executed_tool_names
    assert "tool_lookup_statutory_rule" in executed_tool_names
    assert len(res.evidence) == demo_session.summary.missing_in_2b


def test_three_step_reasoning_chain(demo_session):
    """Verifies a 3-step chain: aggregate suppliers -> inspect missing invoices -> verify rule."""
    orchestrator = VyaparMitraOrchestrator(api_key="")
    req = AgentInvestigateRequest(
        question="Which suppliers have the most discrepancies?",
        session_id=demo_session.session_id,
    )
    res = orchestrator.investigate(req)
    executed_tool_names = [st.tool_name for st in res.steps_executed]
    assert "tool_get_supplier_discrepancies" in executed_tool_names
    assert "tool_get_missing_invoices" in executed_tool_names
    assert "tool_lookup_statutory_rule" in executed_tool_names
    assert len(res.steps_executed) >= 3


def test_dynamic_argument_forwarding_interest(demo_session):
    """Verifies step 1 summary output is dynamically forwarded as principal_tax to step 2."""
    orchestrator = VyaparMitraOrchestrator(api_key="")
    req = AgentInvestigateRequest(
        question="What is our potential Section 50 interest exposure?",
        session_id=demo_session.session_id,
    )
    res = orchestrator.investigate(req)
    assert len(res.steps_executed) >= 2
    step1 = res.steps_executed[0]
    step2 = res.steps_executed[1]

    assert step1.tool_name == "tool_get_session_summary"
    assert step2.tool_name == "tool_calculate_section_50_interest"
    # Ensure principal_tax argument in step 2 was forwarded from session summary
    expected_at_risk = float(demo_session.summary.total_at_risk_itc)
    assert step2.tool_input.get("principal_tax") == expected_at_risk


def test_dynamic_argument_forwarding_invoice_drilldown(demo_session):
    """Verifies invoice drill-down extracts taxes and forwards them to tax difference calculator."""
    flagged = next(r for r in demo_session.detailed_results if r.status.value != "EXACT_MATCH")
    inv_num = flagged.purchase_invoice.invoice_number

    orchestrator = VyaparMitraOrchestrator(api_key="")
    req = AgentInvestigateRequest(
        question=f"Why was invoice {inv_num} flagged?",
        session_id=demo_session.session_id,
    )
    res = orchestrator.investigate(req)
    step_names = [s.tool_name for s in res.steps_executed]
    assert "tool_inspect_invoice" in step_names
    assert "tool_calculate_tax_differences" in step_names

    calc_step = next(s for s in res.steps_executed if s.tool_name == "tool_calculate_tax_differences")
    assert "purchase_tax" in calc_step.tool_input
    assert "gstr2b_tax" in calc_step.tool_input


# ==============================================================================
# 3. SAFETY CONTROLS & GUARDRAILS TESTS
# ==============================================================================

def test_bounded_execution_loop_max_steps(demo_session):
    """Verifies loop strictly terminates within MAX_INVESTIGATION_STEPS (4 steps)."""
    orchestrator = VyaparMitraOrchestrator(api_key="")
    req = AgentInvestigateRequest(
        question="Which suppliers have discrepancies and missing invoices?",
        session_id=demo_session.session_id,
    )
    res = orchestrator.investigate(req)
    assert len(res.steps_executed) <= 4


def test_cycle_detection_prevents_duplicate_calls(demo_session):
    """Verifies cycle detector prevents calling the same tool with identical arguments."""
    orchestrator = VyaparMitraOrchestrator(api_key="")
    req = AgentInvestigateRequest(
        question="Give me an overview of this reconciliation session",
        session_id=demo_session.session_id,
    )
    res = orchestrator.investigate(req)
    # Check that no two executed steps share both the exact same tool_name and tool_input
    signatures = [(st.tool_name, json.dumps(st.tool_input, sort_keys=True)) for st in res.steps_executed]
    assert len(signatures) == len(set(signatures)), "Duplicate tool execution detected in loop"


def test_zero_llm_math_invariance(demo_session):
    """Verifies mathematical figures in response are strictly deterministic, not LLM guesses."""
    orchestrator = VyaparMitraOrchestrator(api_key="")
    req = AgentInvestigateRequest(
        question="Why is my ITC at risk?",
        session_id=demo_session.session_id,
    )
    res = orchestrator.investigate(req)
    expected_risk = demo_session.summary.total_at_risk_itc
    formatted_val = f"{expected_risk:,.2f}"
    assert formatted_val in res.answer, f"Expected deterministic value {formatted_val} not in answer"


def test_offline_fallback_deterministic_operation(demo_session):
    """Verifies the orchestrator operates seamlessly offline without Gemini API keys."""
    orchestrator = VyaparMitraOrchestrator(api_key="")
    assert orchestrator.client is None
    req = AgentInvestigateRequest(
        question="What is the tax difference between books and 2B?",
        session_id=demo_session.session_id,
    )
    res = orchestrator.investigate(req)
    assert res.status == "success"
    assert len(res.answer) > 0
    assert "₹" in res.answer
    assert len(res.steps_executed) > 0


# ==============================================================================
# 4. HITL & AUDIT TRAIL COMPLIANCE TESTS
# ==============================================================================

def test_hitl_notice_generation_in_chain(demo_session):
    """Verifies draft dispute notice generation retains mandatory HITL review status."""
    orchestrator = VyaparMitraOrchestrator(api_key="")
    req = AgentInvestigateRequest(
        question="Draft dispute notices for delinquent suppliers",
        session_id=demo_session.session_id,
    )
    res = orchestrator.investigate(req)
    assert res.human_review_required is True
    assert res.draft_notice is not None
    assert res.draft_notice.human_review_status == "DRAFT — REQUIRES HUMAN REVIEW"
    assert res.draft_notice.verified_amount > 0


def test_audit_events_multi_step_lifecycle(demo_session):
    """Verifies that the entire agent reasoning lifecycle is captured in SQLite audit trail."""
    sid = demo_session.session_id
    payload = {
        "question": "Why is my ITC at risk?",
        "session_id": sid,
    }
    response = client.post("/api/agent/investigate", json=payload)
    assert response.status_code == 200

    trail = get_audit_events(sid)
    event_types = [e["event_type"] for e in trail]

    assert "AGENT_PLAN_CREATED" in event_types
    assert "AGENT_TOOL_SELECTED" in event_types
    assert "AGENT_TOOL_EXECUTED" in event_types
    assert "AGENT_REASONING_COMPLETED" in event_types
    assert "AGENT_INVESTIGATION_COMPLETED" in event_types


def test_api_investigate_response_contract(demo_session):
    """Verifies the HTTP POST /api/agent/investigate endpoint returns Phase 3 plan & steps."""
    payload = {
        "question": "Show me all invoices missing from GSTR-2B",
        "session_id": demo_session.session_id,
    }
    response = client.post("/api/agent/investigate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "plan" in data
    assert isinstance(data["plan"], list)
    assert len(data["plan"]) > 0

    assert "steps_executed" in data
    assert isinstance(data["steps_executed"], list)
    assert len(data["steps_executed"]) > 0

    step0 = data["steps_executed"][0]
    assert "step_index" in step0
    assert "tool_name" in step0
    assert "tool_input" in step0
    assert "observation_summary" in step0
    assert "duration_ms" in step0
    assert "status" in step0
    assert step0["status"] == "SUCCESS"
