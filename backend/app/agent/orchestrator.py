import uuid
import logging
from decimal import Decimal
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from backend.app.config import settings
from backend.app.schemas.invoice import ReconciliationResult, MatchStatus
from backend.app.agent.models import (
    AgentRequest,
    AgentAnalyzeResponse,
    AgentFinding,
    AgentSessionState,
    AgentSessionStep,
    SupplierDisputeNotice,
)
from backend.app.agent.tools_registry import (
    tool_run_reconciliation,
    tool_validate_gstin,
    tool_normalize_invoice,
    tool_calculate_tax_differences,
    tool_calculate_section_50_interest,
    tool_lookup_statutory_rule,
    AVAILABLE_TOOLS,
)
from backend.app.agent.dispute_notice import generate_dispute_notices
from backend.app.services.reconciliation_service import (
    get_session_cache,
    reconcile_session,
    SESSION_DATA_CACHE,
)
from backend.app.database import log_audit_event

logger = logging.getLogger(__name__)

# Strict loop safety control
MAX_AGENT_ITERATIONS = 5

class VyaparMitraOrchestrator:
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self.model_name = model_name or settings.GEMINI_MODEL
        self.client = None

        if self.api_key and self.api_key.strip() and self.api_key != "your_key_here":
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info("VyaparMitra Gemini Client initialized successfully.")
            except Exception as e:
                logger.warning(f"Could not initialize Gemini Client: {e}. Graceful fallback enabled.")
                self.client = None
        else:
            logger.info("Gemini API key not configured or demo key used. Graceful fallback enabled.")

    def analyze(self, request: AgentRequest) -> AgentAnalyzeResponse:
        session_id = request.session_id or f"sess-{uuid.uuid4().hex[:8]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        log_audit_event(
            session_id=session_id,
            event_type="AGENT_ANALYSIS_STARTED",
            details=f"Agent orchestration started for user prompt: '{request.request[:100]}'."
        )

        session_state = AgentSessionState(
            session_id=session_id,
            user_request=request.request,
            current_step="UNDERSTAND",
            steps=[],
            tools_used=[],
            timestamp=now_iso
        )

        step_idx = 1

        # Step 1: UNDERSTAND
        session_state.steps.append(
            AgentSessionStep(
                step_index=step_idx,
                current_step="UNDERSTAND",
                reasoning_summary="Analyzed user request for GST reconciliation and dispute assistance.",
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        )
        step_idx += 1

        # Step 2: PLAN
        session_state.current_step = "PLAN"
        session_state.steps.append(
            AgentSessionStep(
                step_index=step_idx,
                current_step="PLAN",
                reasoning_summary="Planned execution: run deterministic reconciliation engine on current ledger records.",
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        )
        step_idx += 1

        # Step 3: SELECT TOOL & EXECUTE DETERMINISTIC TOOL
        session_state.current_step = "EXECUTE_TOOL"
        tool_name = "tool_run_reconciliation"
        session_state.tools_used.append(tool_name)
        
        # Check if an active session exists in SESSION_DATA_CACHE
        recon_data = None
        if request.session_id and request.session_id in SESSION_DATA_CACHE:
            cache = get_session_cache(request.session_id)
            if cache.get("reconciliation_response"):
                recon_data = cache["reconciliation_response"].model_dump(mode="json")
            elif cache.get("purchase_invoices") and cache.get("gstr2b_invoices"):
                res = reconcile_session(request.session_id)
                recon_data = res.model_dump(mode="json")

        if recon_data is None:
            recon_data = tool_run_reconciliation()

        session_state.steps.append(
            AgentSessionStep(
                step_index=step_idx,
                current_step="OBSERVE",
                selected_tool=tool_name,
                tool_input={"session_id": session_id},
                tool_output={
                    "total_purchase_invoices": recon_data["summary"]["total_purchase_invoices"],
                    "total_at_risk_itc": recon_data["summary"]["total_at_risk_itc"]
                },
                reasoning_summary="Reconciliation completed. Extracted variance figures and identified discrepancies.",
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        )
        step_idx += 1

        # Step 4: REASON & STATUTORY RULE CORRELATION
        session_state.current_step = "REASON"
        findings: List[AgentFinding] = []
        summary_data = recon_data["summary"]
        detailed_items = recon_data["detailed_results"]

        # Parse detailed items into ReconciliationResult objects
        recon_results: List[ReconciliationResult] = [
            ReconciliationResult(**item) for item in detailed_items
        ]

        if summary_data["missing_in_2b"] > 0:
            rule_info = tool_lookup_statutory_rule("RULE_16_2_AA")
            findings.append(
                AgentFinding(
                    category="Missing in GSTR-2B",
                    description=f"{summary_data['missing_in_2b']} invoice(s) recorded in buyer books were not reported by suppliers in GSTR-2B.",
                    amount=Decimal(str(summary_data["total_at_risk_itc"])),
                    severity="high",
                    recommended_action="Draft vendor notice requesting inclusion in next GSTR-1 outward supply return."
                )
            )

        if summary_data["amount_mismatches"] > 0:
            findings.append(
                AgentFinding(
                    category="Amount Mismatch",
                    description=f"{summary_data['amount_mismatches']} invoice(s) have tax variances between purchase register and GSTR-2B.",
                    amount=Decimal(str(summary_data["total_difference"])),
                    severity="high",
                    recommended_action="Reconcile taxable value and tax rate differences. Request amended debit/credit note."
                )
            )

        if summary_data["fuzzy_matches"] > 0:
            findings.append(
                AgentFinding(
                    category="Fuzzy Invoice Number Match",
                    description=f"{summary_data['fuzzy_matches']} invoice(s) matched on GSTIN with minor numbering variances (requires review).",
                    amount=Decimal("0.00"),
                    severity="medium",
                    recommended_action="Confirm transaction identity and update internal ERP invoice reference to match supplier return."
                )
            )

        if summary_data["duplicate_candidates"] > 0:
            findings.append(
                AgentFinding(
                    category="Duplicate Entries",
                    description=f"{summary_data['duplicate_candidates']} duplicate record(s) detected in internal purchase books for the same invoice.",
                    amount=None,
                    severity="medium",
                    recommended_action="Review internal accounts ledger to eliminate double-counted invoice entries."
                )
            )

        if summary_data["invalid_records"] > 0:
            findings.append(
                AgentFinding(
                    category="Invalid GSTIN",
                    description=f"{summary_data['invalid_records']} invoice record(s) have invalid GSTIN format or checksum failure.",
                    amount=None,
                    severity="high",
                    recommended_action="Request correct statutory GSTIN from vendor before proceeding with filing."
                )
            )

        session_state.steps.append(
            AgentSessionStep(
                step_index=step_idx,
                current_step="REASON",
                reasoning_summary=f"Evaluated {len(findings)} compliance categories. Identified Rs. {summary_data['total_at_risk_itc']} total at-risk ITC.",
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        )
        step_idx += 1

        # Step 5: SYNTHESIZE ACTION (Dispute Notice Generation)
        session_state.current_step = "SYNTHESIZE_ACTION"
        dispute_notices = generate_dispute_notices(recon_results)
        
        for notice in dispute_notices:
            log_audit_event(
                session_id=session_id,
                event_type="NOTICE_DRAFT_CREATED",
                details=f"Drafted dispute notice {notice.notice_id} for supplier {notice.supplier_reference} ({notice.invoice_reference})."
            )

        total_at_risk = Decimal(str(summary_data.get("total_at_risk_itc", "0.00")))
        # Build natural language summary
        summary_text = (
            f"VyaparMitra reconciled {summary_data['total_purchase_invoices']} purchase invoices against "
            f"{summary_data['total_2b_invoices']} GSTR-2B records. "
            f"Successfully identified {summary_data['exact_matches']} exact matches and {summary_data['fuzzy_matches']} format-compatible matches. "
            f"Identified Rs. {total_at_risk:,.2f} in total at-risk ITC across {summary_data['missing_in_2b']} missing invoice(s) "
            f"and {summary_data['amount_mismatches']} amount variance(s). "
            f"Prepared {len(dispute_notices)} draft supplier dispute communication(s) for your review."
        )

        # Optional Gemini enhancement for natural language narrative if client is configured
        if self.client:
            try:
                prompt = (
                    f"User Request: {request.request}\n"
                    f"Reconciliation Summary: {summary_data}\n"
                    f"Key Findings: {[f.model_dump() for f in findings]}\n\n"
                    f"Provide a concise, professional executive briefing in 2 paragraphs for the MSME business owner. "
                    f"Highlight the at-risk ITC of Rs. {summary_data['total_at_risk_itc']} and advise reviewing the generated draft notices. "
                    f"Do not invent any numbers. Do not calculate arithmetic. State that human approval is required."
                )
                gemini_res = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                if gemini_res and gemini_res.text:
                    summary_text = gemini_res.text.strip()
            except Exception as e:
                logger.info(f"Gemini natural language enhancement skipped ({e}). Using deterministic summary.")
                summary_text = (
                    f"AI analysis unavailable — deterministic reconciliation results are still available.\n\n"
                    + summary_text
                )

        session_state.final_action = f"Generated {len(dispute_notices)} reviewable supplier notices."

        log_audit_event(
            session_id=session_id,
            event_type="AGENT_ANALYSIS_COMPLETED",
            details=f"Agent analysis complete. Generated {len(findings)} findings and {len(dispute_notices)} draft notices."
        )

        return AgentAnalyzeResponse(
            status="success",
            session_id=session_id,
            summary=summary_text,
            findings=findings,
            actions=dispute_notices,
            tools_used=session_state.tools_used,
            human_review_required=True,
            disclaimer=(
                "VyaparMitra is an accounting and reconciliation assistance system. "
                "It does not constitute statutory legal advice. "
                "All supplier communications require human review and approval."
            )
        )

_orchestrator_instance = None

def get_agent_orchestrator() -> VyaparMitraOrchestrator:
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = VyaparMitraOrchestrator()
    return _orchestrator_instance
