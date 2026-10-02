import pytest
import uuid
from decimal import Decimal
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import (
    create_conversation,
    get_conversations,
    get_conversation,
    save_agent_message,
    get_conversation_messages,
    delete_conversation,
    get_audit_events,
)
from backend.app.agent.orchestrator import get_agent_orchestrator
from backend.app.agent.models import AgentInvestigateRequest

client = TestClient(app)

def test_database_conversation_crud_lifecycle():
    """Validates complete database lifecycle for persistent agent conversations."""
    session_id = f"test-sess-{uuid.uuid4().hex[:6]}"

    # 1. Create conversation
    conv = create_conversation(session_id=session_id, title="Test Conversation Title")
    assert conv["session_id"] == session_id
    assert conv["title"] == "Test Conversation Title"
    conv_id = conv["conversation_id"]

    # 2. List conversations
    conv_list = get_conversations(session_id=session_id)
    assert any(c["conversation_id"] == conv_id for c in conv_list)

    # 3. Save user and assistant messages
    msg1 = save_agent_message(
        conversation_id=conv_id,
        session_id=session_id,
        role="user",
        content="Why is my ITC at risk?",
        intent="ITC_RISK",
        context_data={"topic": "itc"},
    )
    assert msg1["message_id"] is not None

    msg2 = save_agent_message(
        conversation_id=conv_id,
        session_id=session_id,
        role="assistant",
        content="Rs. 18,360 ITC is at risk under Section 16(2)(aa).",
        intent="ITC_RISK",
        tools_used=["tool_get_session_summary", "tool_get_missing_invoices"],
        suggested_action="Review missing invoices.",
    )
    assert msg2["message_id"] is not None

    # 4. Fetch messages
    messages = get_conversation_messages(conv_id)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert "tool_get_session_summary" in messages[1]["tools_used"]

    # 5. Delete conversation
    deleted = delete_conversation(conv_id)
    assert deleted is True
    assert len(get_conversation_messages(conv_id)) == 0
    assert not any(c["conversation_id"] == conv_id for c in get_conversations(session_id))

def test_context_reuse_supplier_followup():
    """
    Follow-up query 'Why are they risky?' seamlessly reuses supplier_context from Turn 1,
    logging AGENT_CONTEXT_REUSED.
    """
    orchestrator = get_agent_orchestrator()
    session_id = "demo-session"
    conv_id = f"conv-supplier-reuse-{uuid.uuid4().hex[:6]}"

    # Turn 1: Explicit supplier query
    turn1_req = AgentInvestigateRequest(
        session_id=session_id,
        conversation_id=conv_id,
        question="What is the risk profile of supplier 27AAPFU0939F1ZV?",
    )
    turn1_resp = orchestrator.investigate(turn1_req)
    assert turn1_resp.intent == "SUPPLIER_PROFILE"
    assert turn1_resp.conversation_id == conv_id
    assert turn1_resp.message_id is not None

    # Turn 2: Follow-up question using pronoun 'they'
    turn2_req = AgentInvestigateRequest(
        session_id=session_id,
        conversation_id=conv_id,
        question="Why are they risky and what invoices are affected?",
    )
    turn2_resp = orchestrator.investigate(turn2_req)
    assert turn2_resp.intent == "SUPPLIER_PROFILE"
    assert "tool_get_supplier_profile" in turn2_resp.tools_used

    # Verify AGENT_CONTEXT_REUSED was recorded in audit log
    audit_events = get_audit_events(session_id)
    assert any(e["event_type"] == "AGENT_CONTEXT_REUSED" for e in audit_events)

def test_context_reuse_invoice_followup():
    """
    Follow-up query 'What is the tax mismatch on it?' reuses invoice_context from Turn 1.
    """
    orchestrator = get_agent_orchestrator()
    session_id = "demo-session"
    conv_id = f"conv-invoice-reuse-{uuid.uuid4().hex[:6]}"

    # Turn 1: Inspect invoice
    turn1_req = AgentInvestigateRequest(
        session_id=session_id,
        conversation_id=conv_id,
        question="Inspect invoice INV-2026-001",
    )
    turn1_resp = orchestrator.investigate(turn1_req)
    assert turn1_resp.intent == "INVOICE_INSPECTION"

    # Turn 2: Follow-up question referring to 'it'
    turn2_req = AgentInvestigateRequest(
        session_id=session_id,
        conversation_id=conv_id,
        question="What is the tax mismatch on it?",
    )
    turn2_resp = orchestrator.investigate(turn2_req)
    assert turn2_resp.intent in ("TAX_DIFFERENCE", "INVOICE_INSPECTION")
    assert "tool_inspect_invoice" in turn2_resp.tools_used

def test_api_conversations_endpoints():
    """Tests FastAPI conversation endpoints: create, list, messages, delete."""
    session_id = f"api-sess-{uuid.uuid4().hex[:6]}"

    # 1. POST /api/agent/conversations
    create_res = client.post("/api/agent/conversations", json={"session_id": session_id, "title": "API Test Chat"})
    assert create_res.status_code == 200
    conv_data = create_res.json()
    conv_id = conv_data["conversation_id"]

    # 2. GET /api/agent/conversations/{session_id}
    list_res = client.get(f"/api/agent/conversations/{session_id}")
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) >= 1
    assert items[0]["conversation_id"] == conv_id

    # 3. POST /api/agent/investigate with conversation_id
    inv_res = client.post("/api/agent/investigate", json={
        "session_id": "demo-session",
        "conversation_id": conv_id,
        "question": "Why is my ITC at risk?",
    })
    assert inv_res.status_code == 200
    inv_data = inv_res.json()
    assert inv_data["conversation_id"] == conv_id
    assert inv_data["message_id"] is not None

    # 4. GET /api/agent/conversations/{conversation_id}/messages
    msg_res = client.get(f"/api/agent/conversations/{conv_id}/messages")
    assert msg_res.status_code == 200
    msgs = msg_res.json()
    assert len(msgs) == 2  # user question and assistant answer
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"

    # 5. DELETE /api/agent/conversations/{conversation_id}
    del_res = client.delete(f"/api/agent/conversations/{conv_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True
