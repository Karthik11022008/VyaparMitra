from fastapi import APIRouter, HTTPException, Depends
import logging
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from backend.app.agent.models import (
    AgentRequest,
    AgentAnalyzeResponse,
    NoticeActionRequest,
    NoticeActionResponse,
    AgentInvestigateRequest,
    AgentInvestigateResponse,
)
from backend.app.agent.orchestrator import VyaparMitraOrchestrator, get_agent_orchestrator
from backend.app.database import (
    log_audit_event,
    create_conversation,
    get_conversations,
    get_conversation,
    get_conversation_messages,
    delete_conversation,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["Agent"])

@router.post("/analyze", response_model=AgentAnalyzeResponse)
async def analyze_reconciliation(
    payload: AgentRequest,
    orchestrator: VyaparMitraOrchestrator = Depends(get_agent_orchestrator)
):
    """
    Agentic analysis endpoint:
    Orchestrates: UNDERSTAND -> PLAN -> SELECT TOOL -> EXECUTE DETERMINISTIC TOOL -> OBSERVE -> REASON -> SYNTHESIZE ACTION
    Produces structured findings and draft supplier dispute notices.
    """
    try:
        response = orchestrator.analyze(payload)
        return response
    except Exception as e:
        logger.error(f"Error in agent analyze endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while orchestrating the agent reconciliation workflow."
        )

@router.post("/investigate", response_model=AgentInvestigateResponse)
async def investigate_query(
    payload: AgentInvestigateRequest,
    orchestrator: VyaparMitraOrchestrator = Depends(get_agent_orchestrator)
):
    """
    Phase 2 Conversational Investigation Endpoint:
    Processes natural language queries regarding the active reconciliation session,
    producing plain-language answers grounded strictly in deterministic tool outputs.
    """
    try:
        response = orchestrator.investigate(payload)
        return response
    except Exception as e:
        logger.error(f"Error in agent investigate endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing the conversational investigation query."
        )

@router.post("/notice/{notice_id}/action", response_model=NoticeActionResponse)
async def handle_notice_action(notice_id: str, payload: NoticeActionRequest):
    """
    Records human-in-the-loop decisions (APPROVE, REJECT, or EDIT) on draft supplier dispute communications,
    logging immutable audit events.
    """
    action = payload.action.upper()
    if action not in ("APPROVE", "REJECT", "EDIT"):
        raise HTTPException(status_code=400, detail="Invalid action. Must be APPROVE, REJECT, or EDIT.")

    session_id = payload.session_id or "global"
    event_type = f"NOTICE_{action}D" if action in ("APPROVE", "REJECT") else "NOTICE_EDITED"
    details = f"User performed action '{action}' on dispute notice '{notice_id}'."

    log_audit_event(
        session_id=session_id,
        event_type=event_type,
        details=details
    )

    return NoticeActionResponse(
        notice_id=notice_id,
        action=action,
        status="success",
        message=f"Notice '{notice_id}' successfully marked as {action}."
    )

class CreateConversationRequest(BaseModel):
    session_id: str
    title: Optional[str] = "Reconciliation Inquiry"

@router.post("/conversations")
async def create_new_conversation(payload: CreateConversationRequest):
    """Initializes a new persistent agent conversation for the session."""
    try:
        conv = create_conversation(session_id=payload.session_id, title=payload.title)
        return conv
    except Exception as e:
        logger.error(f"Error creating conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create conversation.")

@router.get("/conversations/{session_id}")
async def list_conversations(session_id: str):
    """Lists all persistent conversations associated with a reconciliation session."""
    try:
        convs = get_conversations(session_id=session_id)
        return convs
    except Exception as e:
        logger.error(f"Error listing conversations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list conversations.")

@router.get("/conversations/{conversation_id}/messages")
async def get_messages_for_conversation(conversation_id: str):
    """Returns chronological message history with structured traces for a conversation."""
    try:
        messages = get_conversation_messages(conversation_id)
        return messages
    except Exception as e:
        logger.error(f"Error fetching conversation messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve conversation messages.")

@router.delete("/conversations/{conversation_id}")
async def delete_conversation_endpoint(conversation_id: str):
    """Deletes conversation and its message history."""
    try:
        deleted = delete_conversation(conversation_id)
        return {"status": "success", "conversation_id": conversation_id, "deleted": deleted}
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete conversation.")
