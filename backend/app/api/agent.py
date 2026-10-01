from fastapi import APIRouter, HTTPException, Depends
import logging
from backend.app.agent.models import (
    AgentRequest,
    AgentAnalyzeResponse,
    NoticeActionRequest,
    NoticeActionResponse,
)
from backend.app.agent.orchestrator import VyaparMitraOrchestrator, get_agent_orchestrator
from backend.app.database import log_audit_event

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
