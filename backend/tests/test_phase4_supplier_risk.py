import pytest
from decimal import Decimal
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.supplier_risk_service import (
    compute_supplier_risk_score,
    build_supplier_risk_profile,
    build_all_supplier_risk_profiles,
    get_supplier_history_profile,
)
from backend.app.schemas.invoice import MatchStatus
from backend.app.agent.orchestrator import get_agent_orchestrator
from backend.app.agent.models import AgentInvestigateRequest

client = TestClient(app)

def test_compute_supplier_risk_score_clean():
    """A supplier with all matching invoices and zero risk must yield a 0 risk score (LOW/clean)."""
    score, category, breakdown, signals, actions = compute_supplier_risk_score(
        total_invoices=5,
        exact_matches=5,
        fuzzy_matches=0,
        tax_mismatches=0,
        missing_in_2b=0,
        duplicate_candidates=0,
        invalid_records=0,
        at_risk_itc=Decimal("0.00"),
    )
    assert score == 0
    assert category == "LOW"
    assert len(signals) == 0
    assert breakdown["missing_2b_factor"] == 0
    assert breakdown["exposure_factor"] == 0

def test_compute_supplier_risk_score_missing_2b():
    """A supplier with missing 2B invoices receives appropriate baseline and incremental penalties."""
    score, category, breakdown, signals, actions = compute_supplier_risk_score(
        total_invoices=3,
        exact_matches=2,
        fuzzy_matches=0,
        tax_mismatches=0,
        missing_in_2b=1,
        duplicate_candidates=0,
        invalid_records=0,
        at_risk_itc=Decimal("5000.00"),
    )
    # base 30 + 10 (1*10) + 5 (exposure < 10k) = 45 -> MEDIUM
    assert score >= 40
    assert category in ("MEDIUM", "HIGH")
    assert any(s.code == "MISSING_2B" for s in signals)

def test_compute_supplier_risk_score_critical_exposure():
    """A supplier with missing 2B and heavy exposure (>= 50k) hits HIGH or CRITICAL score."""
    score, category, breakdown, signals, actions = compute_supplier_risk_score(
        total_invoices=4,
        exact_matches=1,
        fuzzy_matches=0,
        tax_mismatches=1,
        missing_in_2b=2,
        duplicate_candidates=0,
        invalid_records=0,
        at_risk_itc=Decimal("75000.00"),
    )
    assert score >= 70
    assert category in ("HIGH", "CRITICAL")
    assert any(s.code == "HIGH_ITC_EXPOSURE" for s in signals)
    assert breakdown["exposure_factor"] == 20

def test_build_all_supplier_risk_profiles_demo_session():
    """Computes risk profiles for all suppliers in demo dataset deterministically."""
    profiles = build_all_supplier_risk_profiles("demo-session")
    assert len(profiles) > 0
    # Ranked descending by risk_score, then exposure
    for i in range(len(profiles) - 1):
        assert (profiles[i].risk_score, profiles[i].at_risk_itc) >= (
            profiles[i + 1].risk_score,
            profiles[i + 1].at_risk_itc,
        )

def test_build_single_supplier_profile_with_affected_invoices():
    """Tests drilldown profile retrieval for a specific supplier in demo session."""
    profiles = build_all_supplier_risk_profiles("demo-session")
    target = profiles[0]
    profile = build_supplier_risk_profile("demo-session", target.supplier_gstin)
    assert profile is not None
    assert profile.supplier_gstin == target.supplier_gstin
    assert profile.risk_score == target.risk_score
    assert len(profile.recommended_actions) > 0
    if profile.missing_in_2b > 0 or profile.tax_mismatches > 0:
        assert len(profile.affected_invoices) > 0

def test_get_supplier_history_insufficient_data():
    """A fresh supplier with < 2 historical sessions returns has_sufficient_history=False."""
    history = get_supplier_history_profile("27AAPFU0939F1ZV")
    assert history.supplier_gstin == "27AAPFU0939F1ZV"
    if history.sessions_seen_count < 2:
        assert history.has_sufficient_history is False
        assert len(history.detected_patterns) == 0

def test_api_get_all_supplier_risks():
    """FastAPI endpoint GET /api/suppliers/{session_id}/risk returns 200 with list of profiles."""
    response = client.get("/api/suppliers/demo-session/risk")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "risk_score" in data[0]
    assert "risk_category" in data[0]
    assert "signals" in data[0]

def test_api_get_single_supplier_profile():
    """FastAPI endpoint GET /api/suppliers/{session_id}/{gstin}/profile returns 200."""
    all_res = client.get("/api/suppliers/demo-session/risk")
    gstin = all_res.json()[0]["supplier_gstin"]
    response = client.get(f"/api/suppliers/demo-session/{gstin}/profile")
    assert response.status_code == 200
    data = response.json()
    assert data["supplier_gstin"] == gstin
    assert "score_breakdown" in data
    assert "affected_invoices" in data

def test_api_get_single_supplier_profile_not_found():
    """FastAPI endpoint returns 404 for unknown supplier."""
    response = client.get("/api/suppliers/demo-session/NONEXISTENT9999/profile")
    assert response.status_code == 404

def test_api_get_supplier_history():
    """FastAPI endpoint GET /api/suppliers/{session_id}/{gstin}/history returns 200."""
    all_res = client.get("/api/suppliers/demo-session/risk")
    gstin = all_res.json()[0]["supplier_gstin"]
    response = client.get(f"/api/suppliers/demo-session/{gstin}/history")
    assert response.status_code == 200
    data = response.json()
    assert data["supplier_gstin"] == gstin
    assert "has_sufficient_history" in data

def test_conversational_investigate_supplier_profile():
    """The conversational orchestrator routes 'What is the risk profile of supplier ...' to SUPPLIER_PROFILE."""
    orchestrator = get_agent_orchestrator()
    all_res = client.get("/api/suppliers/demo-session/risk")
    gstin = all_res.json()[0]["supplier_gstin"]

    req = AgentInvestigateRequest(
        session_id="demo-session",
        question=f"What is the risk score and profile of supplier {gstin}?",
    )
    resp = orchestrator.investigate(req)
    assert resp.intent == "SUPPLIER_PROFILE"
    assert "tool_get_supplier_profile" in resp.tools_used
    assert len(resp.evidence) > 0
    assert gstin in resp.answer or gstin in resp.evidence[0].supplier_gstin

def test_conversational_investigate_supplier_history():
    """The conversational orchestrator routes 'Show historical performance for vendor ...' to SUPPLIER_HISTORY."""
    orchestrator = get_agent_orchestrator()
    all_res = client.get("/api/suppliers/demo-session/risk")
    gstin = all_res.json()[0]["supplier_gstin"]

    req = AgentInvestigateRequest(
        session_id="demo-session",
        question=f"Show me the historical filing trend and history for vendor {gstin}",
    )
    resp = orchestrator.investigate(req)
    assert resp.intent == "SUPPLIER_HISTORY"
    assert "tool_get_supplier_history" in resp.tools_used
    assert len(resp.evidence) > 0
