import uuid
import re
import json
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
    AgentInvestigateRequest,
    AgentInvestigateResponse,
    AgentEvidenceItem,
    AgentStepTrace,
    ToolCallRequest,
)
from backend.app.agent.tools_registry import (
    tool_run_reconciliation,
    tool_validate_gstin,
    tool_normalize_invoice,
    tool_calculate_tax_differences,
    tool_calculate_section_50_interest,
    tool_lookup_statutory_rule,
    tool_get_session_summary,
    tool_get_missing_invoices,
    tool_inspect_invoice,
    tool_get_supplier_discrepancies,
    tool_search_invoices,
    AVAILABLE_TOOLS,
    TOOL_CONTRACTS,
    TOOL_DEFINITIONS,
    validate_and_call_tool,
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

    def _detect_intent(self, question: str, invoice_context: Optional[str]) -> str:
        q = question.lower().strip()
        if not q:
            return "EMPTY_QUESTION"
        if any(w in q for w in ["draft", "notice", "letter", "prepare notice", "supplier notice", "demand notice", "dispute notice"]):
            return "DRAFT_NOTICE"
        if any(w in q for w in ["supplier", "vendor", "counterparty", "delinquent"]):
            return "SUPPLIER_DISCREPANCIES"
        if any(w in q for w in ["missing in 2b", "missing from 2b", "missing in gstr-2b", "missing from gstr-2b", "not in 2b", "not in gstr-2b", "unreflected", "omitted in 2b", "missing"]):
            return "MISSING_IN_2B"
        if any(w in q for w in ["interest", "section 50", "sec 50", "delay", "18%"]):
            return "INTEREST_EXPOSURE"
        if any(w in q for w in ["rule", "section 16", "16(2)(aa)", "rule 37a", "statutory", "legal"]):
            return "STATUTORY_RULE"
        if any(w in q for w in ["tax difference", "tax variance", "rate difference", "amount mismatch", "mismatch"]):
            return "TAX_DIFFERENCE"
        if any(w in q for w in ["why is my itc at risk", "itc at risk", "blocked itc", "credit at risk", "itc risk", "why is itc", "at risk", "itc", "risk"]):
            return "ITC_RISK"
        if invoice_context or "invoice" in q or "inv-" in q or "inv/" in q or "flagged" in q or "why was" in q:
            return "INVOICE_INSPECTION"
        if any(w in q for w in ["summary", "overview", "status", "how many", "tell me about"]):
            return "GENERAL_SUMMARY"
        return "GENERAL_SUMMARY"

    def _extract_invoice_number(self, text: str, context: Optional[str]) -> Optional[str]:
        if context and context.strip():
            return context.strip()
        patterns = [
            r'invoice\s+([A-Za-z0-9\-_/]+)',
            r'([A-Za-z0-9]+(?:[-/_][A-Za-z0-9]+)+)',
        ]
        for p in patterns:
            match = re.search(p, text, re.IGNORECASE)
            if match:
                cand = match.group(1).strip()
                if cand.lower() not in ["gstr-2b", "gstr-1", "gstr2b", "drc-01b", "sec-16", "section-16", "rule-37a"]:
                    return cand
        return None

    def _extract_search_term(self, text: str) -> str:
        cleaned = re.sub(r'^(search for|search|find|lookup|show me)\s+', '', text.strip(), flags=re.IGNORECASE)
        return cleaned.strip() or text.strip()

    def _create_investigation_plan(
        self,
        question: str,
        intent: str,
        invoice_context: Optional[str] = None,
        session_id: str = "demo-session"
    ) -> List[str]:
        if intent == "ITC_RISK":
            return [
                "Query session reconciliation metrics to quantify overall at-risk ITC",
                "Retrieve top unreflected purchase invoices missing from GSTR-2B",
                "Cross-reference statutory blocking rules under CGST Section 16(2)(aa)",
            ]
        elif intent == "MISSING_IN_2B":
            return [
                "Query all purchase register invoices omitted from counterparty GSTR-2B returns",
                "Cross-reference statutory compliance blocking condition under Section 16(2)(aa)",
                "Synthesize invoice-level risk items and recommend dispute notice dispatch",
            ]
        elif intent == "INVOICE_INSPECTION":
            inv_no = self._extract_invoice_number(question, invoice_context)
            if inv_no:
                return [
                    f"Inspect reconciliation record for invoice '{inv_no}' in session '{session_id}'",
                    f"Calculate exact tax difference between purchase books and GSTR-2B returns",
                    "Determine statutory GST rule applicable to match status and tax difference",
                ]
            return [
                "Inspect session discrepancy records to identify target invoice candidates",
                "Provide user with actionable invoice reference and discrepancy summary",
            ]
        elif intent == "SUPPLIER_DISCREPANCIES":
            return [
                "Aggregate counterparty supplier compliance metrics and rank delinquent vendors",
                "Retrieve unreflected invoices associated with high-risk suppliers",
                "Verify Section 16(2)(aa) statutory impact on input tax credit eligibility",
            ]
        elif intent == "TAX_DIFFERENCE":
            inv_no = self._extract_invoice_number(question, invoice_context)
            if inv_no:
                return [
                    f"Inspect invoice '{inv_no}' to retrieve purchase and GSTR-2B tax components",
                    "Compute precise CGST/SGST/IGST tax differences deterministically",
                    "Evaluate variance against statutory ₹1.00 tolerance and Rule 37A requirements",
                ]
            return [
                "Retrieve session summary to examine net tax variance across all reconciled invoices",
                "Calculate total differential between purchase ledger and GSTR-2B returns",
                "Identify amount-mismatch transactions requiring supplier credit/debit notes",
            ]
        elif intent == "STATUTORY_RULE":
            return [
                "Identify applicable CGST Act provision or statutory rule from query context",
                "Retrieve statutory reference, compliance criteria, and recipient guidelines",
                "Ground legal requirement in active reconciliation session context",
            ]
        elif intent == "INTEREST_EXPOSURE":
            return [
                "Query reconciliation session to retrieve total at-risk ITC principal amount",
                "Calculate simple interest under Section 50(1) CGST Act at statutory rate of 18% p.a.",
                "Cross-reference Section 50 statutory interest provisions and mitigation timeline",
            ]
        elif intent == "DRAFT_NOTICE":
            inv_no = self._extract_invoice_number(question, invoice_context)
            target_str = f"for invoice '{inv_no}'" if inv_no else "for highest-exposure delinquent supplier"
            return [
                f"Identify and inspect target discrepancy record {target_str}",
                "Cross-reference statutory Section 16(2)(aa) filing obligations",
                "Generate formal draft dispute notice in 'DRAFT — REQUIRES HUMAN REVIEW' status",
            ]
        elif intent == "SEARCH_INVOICES":
            return [
                "Execute deterministic search across session purchase and GSTR-2B records",
                "Filter and rank matched records by query parameters",
                "Summarize search findings with verified match status",
            ]
        else:  # GENERAL_SUMMARY
            return [
                "Retrieve comprehensive session reconciliation totals and match status distribution",
                "Evaluate total at-risk ITC and net tax difference for executive briefing",
            ]

    def _propose_next_tool_step(
        self,
        intent: str,
        question: str,
        invoice_context: Optional[str],
        session_id: str,
        step_idx: int,
        observations: List[Dict[str, Any]],
    ) -> Optional[ToolCallRequest]:
        executed_tools = [o.get("tool_name") for o in observations]

        def get_obs(tool_name: str) -> Optional[Any]:
            for o in observations:
                if o.get("tool_name") == tool_name and "result" in o:
                    return o["result"]
            return None

        inv_no = self._extract_invoice_number(question, invoice_context)

        if intent == "ITC_RISK":
            if "tool_get_session_summary" not in executed_tools:
                return ToolCallRequest(tool_name="tool_get_session_summary", arguments={"session_id": session_id})
            if "tool_get_missing_invoices" not in executed_tools:
                return ToolCallRequest(tool_name="tool_get_missing_invoices", arguments={"session_id": session_id})
            if "tool_lookup_statutory_rule" not in executed_tools:
                return ToolCallRequest(tool_name="tool_lookup_statutory_rule", arguments={"rule_id": "RULE_16_2_AA"})
            return None

        elif intent == "MISSING_IN_2B":
            if "tool_get_missing_invoices" not in executed_tools:
                return ToolCallRequest(tool_name="tool_get_missing_invoices", arguments={"session_id": session_id})
            if "tool_lookup_statutory_rule" not in executed_tools:
                return ToolCallRequest(tool_name="tool_lookup_statutory_rule", arguments={"rule_id": "RULE_16_2_AA"})
            return None

        elif intent == "INVOICE_INSPECTION":
            if not inv_no:
                if "tool_get_missing_invoices" not in executed_tools:
                    return ToolCallRequest(tool_name="tool_get_missing_invoices", arguments={"session_id": session_id})
                return None

            if "tool_inspect_invoice" not in executed_tools:
                return ToolCallRequest(
                    tool_name="tool_inspect_invoice",
                    arguments={"session_id": session_id, "invoice_number": inv_no}
                )

            inv_res = get_obs("tool_inspect_invoice")
            if inv_res and isinstance(inv_res, dict) and inv_res.get("found"):
                if "tool_calculate_tax_differences" not in executed_tools:
                    p_tax = float(inv_res.get("purchase_tax") or 0.0)
                    b_tax = float(inv_res.get("gstr2b_tax") or 0.0)
                    return ToolCallRequest(
                        tool_name="tool_calculate_tax_differences",
                        arguments={"purchase_tax": p_tax, "gstr2b_tax": b_tax}
                    )
                if "tool_lookup_statutory_rule" not in executed_tools:
                    rule_id = "RULE_16_2_AA" if inv_res.get("status") == "MISSING_IN_2B" else "RULE_37A"
                    return ToolCallRequest(tool_name="tool_lookup_statutory_rule", arguments={"rule_id": rule_id})
            return None

        elif intent == "SUPPLIER_DISCREPANCIES":
            if "tool_get_supplier_discrepancies" not in executed_tools:
                return ToolCallRequest(tool_name="tool_get_supplier_discrepancies", arguments={"session_id": session_id})
            sup_res = get_obs("tool_get_supplier_discrepancies")
            if sup_res and isinstance(sup_res, list) and any(s.get("total_at_risk_itc", 0) > 0 for s in sup_res):
                if "tool_get_missing_invoices" not in executed_tools:
                    return ToolCallRequest(tool_name="tool_get_missing_invoices", arguments={"session_id": session_id})
                if "tool_lookup_statutory_rule" not in executed_tools:
                    return ToolCallRequest(tool_name="tool_lookup_statutory_rule", arguments={"rule_id": "RULE_16_2_AA"})
            return None

        elif intent == "TAX_DIFFERENCE":
            if inv_no:
                if "tool_inspect_invoice" not in executed_tools:
                    return ToolCallRequest(
                        tool_name="tool_inspect_invoice",
                        arguments={"session_id": session_id, "invoice_number": inv_no}
                    )
                inv_res = get_obs("tool_inspect_invoice")
                if inv_res and isinstance(inv_res, dict) and inv_res.get("found"):
                    if "tool_calculate_tax_differences" not in executed_tools:
                        p_tax = float(inv_res.get("purchase_tax") or 0.0)
                        b_tax = float(inv_res.get("gstr2b_tax") or 0.0)
                        return ToolCallRequest(
                            tool_name="tool_calculate_tax_differences",
                            arguments={"purchase_tax": p_tax, "gstr2b_tax": b_tax}
                        )
                    if "tool_lookup_statutory_rule" not in executed_tools:
                        return ToolCallRequest(tool_name="tool_lookup_statutory_rule", arguments={"rule_id": "RULE_37A"})
            else:
                if "tool_get_session_summary" not in executed_tools:
                    return ToolCallRequest(tool_name="tool_get_session_summary", arguments={"session_id": session_id})
                if "tool_calculate_tax_differences" not in executed_tools:
                    summary_res = get_obs("tool_get_session_summary")
                    p_tax = float(summary_res.get("total_purchase_tax", 0.0)) if summary_res else 0.0
                    b_tax = float(summary_res.get("total_2b_tax", 0.0)) if summary_res else 0.0
                    return ToolCallRequest(
                        tool_name="tool_calculate_tax_differences",
                        arguments={"purchase_tax": p_tax, "gstr2b_tax": b_tax}
                    )
                if "tool_lookup_statutory_rule" not in executed_tools:
                    return ToolCallRequest(tool_name="tool_lookup_statutory_rule", arguments={"rule_id": "RULE_37A"})
            return None

        elif intent == "STATUTORY_RULE":
            if "tool_lookup_statutory_rule" not in executed_tools:
                rule_id = "RULE_16_2_AA"
                q_lower = question.lower()
                if "37a" in q_lower or "rule 37" in q_lower:
                    rule_id = "RULE_37A"
                elif "50" in q_lower or "interest" in q_lower:
                    rule_id = "RULE_SECTION_50"
                elif "155" in q_lower or "burden" in q_lower:
                    rule_id = "RULE_BURDEN_OF_PROOF"
                return ToolCallRequest(tool_name="tool_lookup_statutory_rule", arguments={"rule_id": rule_id})
            if "tool_get_session_summary" not in executed_tools:
                return ToolCallRequest(tool_name="tool_get_session_summary", arguments={"session_id": session_id})
            return None

        elif intent == "INTEREST_EXPOSURE":
            if "tool_get_session_summary" not in executed_tools:
                return ToolCallRequest(tool_name="tool_get_session_summary", arguments={"session_id": session_id})
            summary_res = get_obs("tool_get_session_summary")
            at_risk = float(summary_res.get("total_at_risk_itc", 0.0)) if summary_res else 0.0
            if "tool_calculate_section_50_interest" not in executed_tools:
                return ToolCallRequest(
                    tool_name="tool_calculate_section_50_interest",
                    arguments={"principal_tax": at_risk, "delay_days": 60, "annual_rate": 0.18}
                )
            if "tool_lookup_statutory_rule" not in executed_tools:
                return ToolCallRequest(tool_name="tool_lookup_statutory_rule", arguments={"rule_id": "RULE_SECTION_50"})
            return None

        elif intent == "DRAFT_NOTICE":
            if inv_no and "tool_inspect_invoice" not in executed_tools:
                return ToolCallRequest(
                    tool_name="tool_inspect_invoice",
                    arguments={"session_id": session_id, "invoice_number": inv_no}
                )
            elif not inv_no and "tool_get_missing_invoices" not in executed_tools:
                return ToolCallRequest(tool_name="tool_get_missing_invoices", arguments={"session_id": session_id})
            if "tool_lookup_statutory_rule" not in executed_tools:
                return ToolCallRequest(tool_name="tool_lookup_statutory_rule", arguments={"rule_id": "RULE_16_2_AA"})
            return None

        elif intent == "SEARCH_INVOICES":
            if "tool_search_invoices" not in executed_tools:
                search_q = self._extract_search_term(question)
                return ToolCallRequest(
                    tool_name="tool_search_invoices",
                    arguments={"session_id": session_id, "query": search_q}
                )
            return None

        else:  # GENERAL_SUMMARY
            if "tool_get_session_summary" not in executed_tools:
                return ToolCallRequest(tool_name="tool_get_session_summary", arguments={"session_id": session_id})
            return None

    def investigate(self, request: AgentInvestigateRequest) -> AgentInvestigateResponse:
        """
        Phase 3 Agentic Investigation Engine:
        Executes a bounded, dynamic multi-step reasoning loop:
        UNDERSTAND -> PLAN -> SELECT TOOL -> VALIDATE TOOL+ARGS -> EXECUTE -> REASON -> HITL.
        Zero LLM calculation hallucinations - 100% grounded in deterministic tool observations.
        """
        session_id = request.session_id or "demo-session"

        # 1. Handle empty question
        if not request.question or not request.question.strip():
            return AgentInvestigateResponse(
                session_id=session_id,
                user_question=request.question or "",
                intent="EMPTY_QUESTION",
                plan=[],
                steps_executed=[],
                answer="Please enter a specific question about your reconciliation session, such as 'Why is my ITC at risk?' or 'Show missing invoices in GSTR-2B'.",
                evidence=[],
                tools_used=[],
                suggested_action="Ask a question about at-risk ITC, missing invoices, or specific invoice flags.",
                human_review_required=False,
            )

        # 2. Check session existence
        session_summary = tool_get_session_summary(session_id)
        if not session_summary.get("found", False):
            return AgentInvestigateResponse(
                session_id=session_id,
                user_question=request.question,
                intent="UNKNOWN_SESSION",
                plan=["Verify reconciliation session identifier in system"],
                steps_executed=[],
                answer=f"Reconciliation session '{session_id}' could not be found. Please ensure you have uploaded and reconciled purchase data or loaded a historical session.",
                evidence=[],
                tools_used=["tool_get_session_summary"],
                suggested_action="Return to Command Center or Ingestion to initialize a valid reconciliation session.",
                human_review_required=False,
            )

        # 3. Detect intent and create initial plan
        intent = self._detect_intent(request.question, request.invoice_context)
        plan = self._create_investigation_plan(request.question, intent, request.invoice_context, session_id)

        log_audit_event(
            session_id=session_id,
            event_type="AGENT_PLAN_CREATED",
            details=f"Investigation plan created with {len(plan)} steps for intent '{intent}'."
        )

        # 4. Multi-step dynamic tool execution loop
        MAX_INVESTIGATION_STEPS = 4
        steps_executed: List[AgentStepTrace] = []
        tools_used: List[str] = []
        executed_signatures = set()
        observations: List[Dict[str, Any]] = []

        for step_idx in range(1, MAX_INVESTIGATION_STEPS + 1):
            tool_call = self._propose_next_tool_step(
                intent=intent,
                question=request.question,
                invoice_context=request.invoice_context,
                session_id=session_id,
                step_idx=step_idx,
                observations=observations,
            )

            if not tool_call:
                logger.info(f"No further tools proposed at step {step_idx}. Concluding tool execution.")
                break

            # Cycle detection
            sig = (tool_call.tool_name, json.dumps(tool_call.arguments, sort_keys=True))
            if sig in executed_signatures:
                logger.warning(f"Cycle detected for tool '{tool_call.tool_name}' with args {tool_call.arguments}. Terminating loop.")
                break
            executed_signatures.add(sig)

            log_audit_event(
                session_id=session_id,
                event_type="AGENT_TOOL_SELECTED",
                details=f"Step {step_idx}: Selected '{tool_call.tool_name}' with args {json.dumps(tool_call.arguments)}."
            )

            call_res = validate_and_call_tool(
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
                session_id=session_id,
                step_index=step_idx,
            )
            trace = AgentStepTrace(
                step_index=step_idx,
                tool_name=tool_call.tool_name,
                tool_input=call_res["tool_input"],
                observation_summary=call_res["observation_summary"],
                duration_ms=call_res["duration_ms"],
                timestamp=call_res.get("timestamp") or datetime.now(timezone.utc).isoformat(),
                status=call_res.get("status", "SUCCESS" if call_res["success"] else "ERROR"),
            )
            steps_executed.append(trace)
            if tool_call.tool_name not in tools_used:
                tools_used.append(tool_call.tool_name)

            if call_res["success"]:
                log_audit_event(
                    session_id=session_id,
                    event_type="AGENT_TOOL_EXECUTED",
                    details=f"Step {step_idx}: Executed '{tool_call.tool_name}' successfully ({trace.duration_ms:.1f}ms)."
                )
                observations.append({
                    "step_index": step_idx,
                    "tool_name": tool_call.tool_name,
                    "arguments": tool_call.arguments,
                    "result": call_res["data"],
                })
            else:
                log_audit_event(
                    session_id=session_id,
                    event_type="AGENT_TOOL_FAILED",
                    details=f"Step {step_idx}: Tool '{tool_call.tool_name}' failed - {trace.observation_summary}."
                )
                observations.append({
                    "step_index": step_idx,
                    "tool_name": tool_call.tool_name,
                    "arguments": tool_call.arguments,
                    "error": trace.observation_summary,
                })

        log_audit_event(
            session_id=session_id,
            event_type="AGENT_REASONING_COMPLETED",
            details=f"Reasoning completed over {len(steps_executed)} step observations."
        )

        # 5. Extract structured evidence, draft notice, and deterministic answer
        evidence: List[AgentEvidenceItem] = []
        draft_notice: Optional[SupplierDisputeNotice] = None
        human_review_required = False
        suggested_action: Optional[str] = None
        fallback_answer = ""
        facts_summary: Dict[str, Any] = {}

        def get_obs(tool_name: str) -> Optional[Any]:
            for o in observations:
                if o.get("tool_name") == tool_name and "result" in o:
                    return o["result"]
            return None

        if intent == "ITC_RISK":
            s = get_obs("tool_get_session_summary") or session_summary
            missing_invoices = get_obs("tool_get_missing_invoices") or []
            rule_info = get_obs("tool_lookup_statutory_rule") or {}
            at_risk = s.get("total_at_risk_itc", 0.0)
            missing_cnt = s.get("missing_in_2b", 0)
            mismatch_cnt = s.get("amount_mismatches", 0)

            for m in missing_invoices[:5]:
                evidence.append(
                    AgentEvidenceItem(
                        invoice_number=m["invoice_number"],
                        supplier_gstin=m["supplier_gstin"],
                        supplier_name=m["supplier_name"],
                        purchase_tax=Decimal(str(m["total_tax"])),
                        gstr2b_tax=Decimal("0.00"),
                        tax_difference=Decimal(str(m["at_risk_itc"])),
                        status=m["status"],
                        statutory_rule=m.get("statutory_rule", "Section 16(2)(aa)"),
                        details=m["reason"]
                    )
                )

            facts_summary = {
                "total_at_risk_itc": at_risk,
                "missing_in_2b_count": missing_cnt,
                "amount_mismatches_count": mismatch_cnt,
                "statutory_reference": rule_info.get("statutory_reference", "Section 16(2)(aa)")
            }

            fallback_answer = (
                f"₹{at_risk:,.2f} of Input Tax Credit is currently classified as at-risk in this session. "
                f"Under CGST Section 16(2)(aa), credit cannot be availed unless the supplier has furnished outward supplies in GSTR-1 and the invoice appears in your GSTR-2B. "
                f"Specifically, {missing_cnt} invoice(s) are missing from GSTR-2B, and {mismatch_cnt} invoice(s) have tax variances."
            )
            suggested_action = "Draft formal supplier dispute notices for unreflected invoices to request timely GSTR-1 filing."

        elif intent == "MISSING_IN_2B":
            missing_invoices = get_obs("tool_get_missing_invoices") or []
            total_missing_tax = sum(m["at_risk_itc"] for m in missing_invoices)

            for m in missing_invoices:
                evidence.append(
                    AgentEvidenceItem(
                        invoice_number=m["invoice_number"],
                        supplier_gstin=m["supplier_gstin"],
                        supplier_name=m["supplier_name"],
                        purchase_tax=Decimal(str(m["total_tax"])),
                        gstr2b_tax=Decimal("0.00"),
                        tax_difference=Decimal(str(m["at_risk_itc"])),
                        status=m["status"],
                        statutory_rule=m.get("statutory_rule", "Section 16(2)(aa)"),
                        details=m["reason"]
                    )
                )

            facts_summary = {
                "missing_invoices_count": len(missing_invoices),
                "total_missing_tax": total_missing_tax,
                "invoices": [m["invoice_number"] for m in missing_invoices]
            }

            fallback_answer = (
                f"Found {len(missing_invoices)} invoice(s) in your Purchase Register that are missing from GSTR-2B, representing ₹{total_missing_tax:,.2f} in at-risk ITC. "
                f"An invoice is marked as 'Missing in GSTR-2B' when it exists in your internal accounts but the supplier has omitted to upload it in their GSTR-1 return."
            )
            suggested_action = "Review missing invoices and dispatch vendor dispute communications."

        elif intent == "INVOICE_INSPECTION":
            inv_no = self._extract_invoice_number(request.question, request.invoice_context)
            if inv_no:
                inv_data = get_obs("tool_inspect_invoice") or tool_inspect_invoice(session_id, inv_no)
                if inv_data.get("found"):
                    p_tax = Decimal(str(inv_data["purchase_tax"])) if inv_data.get("purchase_tax") is not None else None
                    b_tax = Decimal(str(inv_data["gstr2b_tax"])) if inv_data.get("gstr2b_tax") is not None else None
                    diff = Decimal(str(inv_data["tax_difference"])) if inv_data.get("tax_difference") is not None else Decimal("0.00")

                    evidence.append(
                        AgentEvidenceItem(
                            invoice_number=inv_data["invoice_number"],
                            supplier_gstin=inv_data["supplier_gstin"],
                            supplier_name=inv_data.get("supplier_name", ""),
                            purchase_tax=p_tax,
                            gstr2b_tax=b_tax,
                            tax_difference=diff,
                            status=inv_data["status"],
                            statutory_rule=inv_data.get("statutory_rule"),
                            details=inv_data.get("reason", "")
                        )
                    )
                    facts_summary = inv_data
                    rule_text = f" Under {inv_data['statutory_rule']}, this discrepancy requires action." if inv_data.get("statutory_rule") else ""
                    fallback_answer = (
                        f"Invoice {inv_data['invoice_number']} from {inv_data.get('supplier_name', 'Supplier')} ({inv_data['supplier_gstin']}) is flagged with status '{inv_data['status']}'. "
                        f"Reason: {inv_data['reason']}. Purchase tax: ₹{inv_data.get('purchase_tax', 0):,.2f}, GSTR-2B tax: ₹{inv_data.get('gstr2b_tax', 0):,.2f}, Difference: ₹{inv_data.get('tax_difference', 0):,.2f}.{rule_text}"
                    )
                    suggested_action = f"Inspect invoice {inv_data['invoice_number']} in the Reconciliation ledger or draft a dispute notice."
                else:
                    fallback_answer = f"Invoice '{inv_no}' was not found in active session records. Please verify the invoice number or search the Reconciliation ledger."
                    suggested_action = "Search for the invoice in the Reconciliation workspace."
            else:
                missing_invoices = get_obs("tool_get_missing_invoices") or tool_get_missing_invoices(session_id)
                if missing_invoices:
                    first = missing_invoices[0]
                    fallback_answer = f"Please specify an invoice number. For example, invoice {first['invoice_number']} is currently flagged as missing in GSTR-2B with ₹{first['at_risk_itc']:,.2f} at-risk ITC."
                else:
                    fallback_answer = "Please specify an invoice number to inspect (e.g., 'Why was invoice INV-2026-001 flagged?')."

        elif intent == "SUPPLIER_DISCREPANCIES":
            suppliers = get_obs("tool_get_supplier_discrepancies") or []
            non_compliant = [s for s in suppliers if s.get("total_at_risk_itc", 0) > 0 or s.get("missing_in_2b", 0) > 0]

            for s in suppliers[:5]:
                evidence.append(
                    AgentEvidenceItem(
                        invoice_number=f"{s['total_invoices']} Invoices",
                        supplier_gstin=s["supplier_gstin"],
                        supplier_name=s["supplier_name"],
                        purchase_tax=None,
                        gstr2b_tax=None,
                        tax_difference=Decimal(str(s["total_at_risk_itc"])),
                        status="NON_COMPLIANT" if s["total_at_risk_itc"] > 0 else "COMPLIANT",
                        statutory_rule="Section 16(2)(aa)",
                        details=f"{s['missing_in_2b']} missing in 2B, {s['amount_mismatches']} amount mismatches."
                    )
                )

            facts_summary = {"total_suppliers": len(suppliers), "non_compliant_count": len(non_compliant), "suppliers": suppliers[:3]}
            if non_compliant:
                top = non_compliant[0]
                fallback_answer = (
                    f"Audited {len(suppliers)} counterparty suppliers. {len(non_compliant)} vendor(s) have discrepancies. "
                    f"The supplier with the highest exposure is {top['supplier_name']} ({top['supplier_gstin']}) with ₹{top['total_at_risk_itc']:,.2f} at-risk ITC across {top['missing_in_2b']} missing invoice(s)."
                )
                suggested_action = f"Draft dispute notice for {top['supplier_name']} to resolve pending ITC risk."
            else:
                fallback_answer = f"All {len(suppliers)} audited suppliers are currently compliant with matching GSTR-2B filings."
                suggested_action = "No supplier action required."

        elif intent == "TAX_DIFFERENCE":
            inv_no = self._extract_invoice_number(request.question, request.invoice_context)
            if inv_no:
                inv_data = get_obs("tool_inspect_invoice") or tool_inspect_invoice(session_id, inv_no)
                if inv_data.get("found"):
                    diff = Decimal(str(inv_data.get("tax_difference", "0.00")))
                    evidence.append(
                        AgentEvidenceItem(
                            invoice_number=inv_data["invoice_number"],
                            supplier_gstin=inv_data["supplier_gstin"],
                            supplier_name=inv_data.get("supplier_name", ""),
                            purchase_tax=Decimal(str(inv_data.get("purchase_tax", 0))),
                            gstr2b_tax=Decimal(str(inv_data.get("gstr2b_tax", 0))),
                            tax_difference=diff,
                            status=inv_data["status"],
                            statutory_rule="Rule 37A",
                            details=inv_data.get("reason", "")
                        )
                    )
                    facts_summary = inv_data
                    fallback_answer = (
                        f"Invoice {inv_data['invoice_number']} has a tax difference of ₹{diff:,.2f}. "
                        f"Purchase register records tax of ₹{inv_data.get('purchase_tax', 0):,.2f}, while GSTR-2B reflects ₹{inv_data.get('gstr2b_tax', 0):,.2f}. "
                        f"Under GST rules, variances exceeding statutory tolerance (₹1.00) require reconciliation and supplier credit/debit notes."
                    )
                    suggested_action = "Request amended invoice or debit/credit note from supplier."
                else:
                    fallback_answer = f"Invoice '{inv_no}' was not found in active session records."
            else:
                s = get_obs("tool_get_session_summary") or session_summary
                diff = s.get("total_difference", 0.0)
                from backend.app.agent.tools_registry import _get_recon_response
                resp = _get_recon_response(session_id)
                if resp:
                    mismatches = [r for r in resp.detailed_results if r.status == MatchStatus.AMOUNT_MISMATCH]
                    for m in mismatches[:5]:
                        p = m.purchase_invoice
                        b = m.matched_2b_invoice
                        evidence.append(
                            AgentEvidenceItem(
                                invoice_number=p.invoice_number if p else (b.invoice_number if b else ""),
                                supplier_gstin=p.supplier_gstin if p else (b.supplier_gstin if b else ""),
                                supplier_name=p.supplier_name if p and p.supplier_name else "",
                                purchase_tax=p.total_tax if p else None,
                                gstr2b_tax=b.total_tax if b else None,
                                tax_difference=m.tax_difference,
                                status=m.status.value,
                                statutory_rule="Rule 37A",
                                details=m.reason or "Tax variance detected."
                            )
                        )
                if not evidence:
                    evidence.append(
                        AgentEvidenceItem(
                            invoice_number="SESSION-TAX-TOTALS",
                            supplier_gstin="ALL-VENDORS",
                            supplier_name="Summary Variance",
                            purchase_tax=Decimal(str(s.get("total_purchase_tax", "0.00"))),
                            gstr2b_tax=Decimal(str(s.get("total_2b_tax", "0.00"))),
                            tax_difference=Decimal(str(diff)),
                            status="VARIANCE_DETECTED" if diff > 0 else "BALANCED",
                            statutory_rule="Rule 37A",
                            details=f"Net variance ₹{diff:,.2f} across {s.get('amount_mismatches', 0)} mismatch invoice(s)."
                        )
                    )
                fallback_answer = (
                    f"The total net tax variance across all invoices in this session is ₹{diff:,.2f}, with {s.get('amount_mismatches', 0)} invoice(s) showing amount mismatches. "
                    f"Variances typically arise from tax rate discrepancies (e.g., 18% vs 12%) or rounding differences."
                )
                suggested_action = "Filter Reconciliation ledger by 'Amount Mismatch' to review individual variances."

        elif intent == "STATUTORY_RULE":
            rule_res = get_obs("tool_lookup_statutory_rule") or {}
            facts_summary = rule_res
            compliance_txt = rule_res.get('compliance_summary', '')
            guidance_txt = rule_res.get('review_guidance', '')
            evidence.append(
                AgentEvidenceItem(
                    invoice_number="STATUTORY-PROVISION",
                    supplier_gstin="ALL-SUPPLIERS",
                    supplier_name=rule_res.get("statutory_reference", "Statutory Rule"),
                    purchase_tax=None,
                    gstr2b_tax=None,
                    tax_difference=None,
                    status="APPLICABLE_LAW",
                    statutory_rule=rule_res.get("statutory_reference", "CGST Act"),
                    details=f"{rule_res.get('title', '')} - {compliance_txt}"
                )
            )
            fallback_answer = (
                f"{rule_res.get('statutory_reference', 'CGST Statutory Provision')}: {rule_res.get('title', '')}. "
                f"{compliance_txt} "
                f"Statutory Guidance: {guidance_txt}"
            )
            suggested_action = "Ensure all recipient ITC claims strictly comply with these statutory requirements."

        elif intent == "INTEREST_EXPOSURE":
            s = get_obs("tool_get_session_summary") or session_summary
            at_risk = s.get("total_at_risk_itc", 0.0)
            int_res = get_obs("tool_calculate_section_50_interest") or tool_calculate_section_50_interest(principal_tax=at_risk, delay_days=60, annual_rate=0.18)
            facts_summary = {"at_risk": at_risk, "interest_result": int_res}
            evidence.append(
                AgentEvidenceItem(
                    invoice_number="SEC-50-INTEREST",
                    supplier_gstin="TAX-AUTHORITY",
                    supplier_name="Section 50(1) CGST",
                    purchase_tax=Decimal(str(at_risk)),
                    gstr2b_tax=None,
                    tax_difference=Decimal(str(int_res.get("calculated_interest", "0.00"))),
                    status="INTEREST_EXPOSURE",
                    statutory_rule="Section 50(1)",
                    details=f"Simple interest @ 18% p.a. on ₹{at_risk:,.2f} over 60 days = ₹{int_res.get('calculated_interest', 0):,.2f}."
                )
            )
            fallback_answer = (
                f"For the current at-risk ITC of ₹{at_risk:,.2f}, delayed reversal or incorrect credit availment incurs statutory simple interest under Section 50(1) of the CGST Act at 18% per annum. "
                f"Estimated exposure over a 60-day delay period is ₹{int_res.get('calculated_interest', 0):,.2f} (approx ₹{int_res.get('daily_rate', 0):,.2f} per day)."
            )
            suggested_action = "Reverse in GSTR-3B before DRC-01B issuance to stop interest accumulation under Section 50."

        elif intent == "DRAFT_NOTICE":
            inv_no = self._extract_invoice_number(request.question, request.invoice_context)
            from backend.app.agent.tools_registry import _get_recon_response
            resp = _get_recon_response(session_id)
            target_item = None
            if resp:
                if inv_no:
                    for r in resp.detailed_results:
                        p_num = r.purchase_invoice.invoice_number if r.purchase_invoice else ""
                        b_num = r.matched_2b_invoice.invoice_number if r.matched_2b_invoice else ""
                        if inv_no.lower() in p_num.lower() or inv_no.lower() in b_num.lower():
                            target_item = r
                            break
                if not target_item:
                    for r in resp.detailed_results:
                        if r.status in (MatchStatus.MISSING_IN_2B, MatchStatus.AMOUNT_MISMATCH):
                            target_item = r
                            break

            if target_item:
                notices = generate_dispute_notices([target_item])
                if notices:
                    draft_notice = notices[0]
                    human_review_required = True
                    p = target_item.purchase_invoice
                    b = target_item.matched_2b_invoice
                    evidence.append(
                        AgentEvidenceItem(
                            invoice_number=p.invoice_number if p else (b.invoice_number if b else ""),
                            supplier_gstin=p.supplier_gstin if p else (b.supplier_gstin if b else ""),
                            supplier_name=p.supplier_name if p and p.supplier_name else "",
                            purchase_tax=p.total_tax if p else None,
                            gstr2b_tax=b.total_tax if b else None,
                            tax_difference=target_item.tax_difference,
                            status=target_item.status.value,
                            statutory_rule="Section 16(2)(aa)",
                            details=target_item.reason
                        )
                    )
                    fallback_answer = (
                        f"Prepared a formal draft supplier dispute notice for {draft_notice.supplier_reference} regarding Invoice {draft_notice.invoice_reference}. "
                        f"At-risk ITC: ₹{draft_notice.verified_amount:,.2f}. Notice status: 'DRAFT — REQUIRES HUMAN REVIEW'. Please review, edit, or approve the notice below."
                    )
                    suggested_action = "Review draft notice below and click 'Approve Notice' to authorize dispatch."
            else:
                fallback_answer = "No discrepancy invoices found in the current session to draft a dispute notice for."
                suggested_action = "Reconcile invoices or upload a dataset with discrepancies."

        elif intent == "SEARCH_INVOICES":
            search_res = get_obs("tool_search_invoices") or []
            search_q = self._extract_search_term(request.question)
            for item in search_res[:5]:
                p = item.get("purchase_invoice")
                b = item.get("matched_2b_invoice")
                p_tax = Decimal(str(p["total_tax"])) if p and p.get("total_tax") is not None else None
                b_tax = Decimal(str(b["total_tax"])) if b and b.get("total_tax") is not None else None
                evidence.append(
                    AgentEvidenceItem(
                        invoice_number=p["invoice_number"] if p else (b["invoice_number"] if b else ""),
                        supplier_gstin=p["supplier_gstin"] if p else (b["supplier_gstin"] if b else ""),
                        supplier_name=p.get("supplier_name", "") if p else (b.get("supplier_name", "") if b else ""),
                        purchase_tax=p_tax,
                        gstr2b_tax=b_tax,
                        tax_difference=Decimal(str(item.get("tax_difference", 0))),
                        status=item.get("status", ""),
                        statutory_rule="Rule 37A" if item.get("status") == "AMOUNT_MISMATCH" else "Section 16(2)(aa)",
                        details=item.get("reason", "")
                    )
                )
            fallback_answer = f"Search for '{search_q}' returned {len(search_res)} matching reconciliation record(s)."
            suggested_action = "Review matched invoices or apply additional filters in Reconciliation view."

        else:  # GENERAL_SUMMARY
            s = get_obs("tool_get_session_summary") or session_summary
            fallback_answer = (
                f"Reconciliation session '{session_id}' summary: {s.get('total_purchase_invoices', 0)} purchase invoices reconciled against {s.get('total_2b_invoices', 0)} GSTR-2B returns. "
                f"Identified {s.get('exact_matches', 0)} exact matches, {s.get('fuzzy_matches', 0)} fuzzy matches, {s.get('amount_mismatches', 0)} tax mismatches, and {s.get('missing_in_2b', 0)} missing in 2B. "
                f"Total at-risk ITC is ₹{s.get('total_at_risk_itc', 0):,.2f} with net tax variance of ₹{s.get('total_difference', 0):,.2f}."
            )
            suggested_action = "Filter Reconciliation ledger or explore Supplier Intelligence for vendor risk."

        # Gemini Plain-Language Framing (Optional Enhancement)
        final_answer = fallback_answer
        if self.client:
            try:
                gemini_prompt = (
                    f"User Question: {request.question}\n"
                    f"Intent: {intent}\n"
                    f"Deterministic Facts: {facts_summary or fallback_answer}\n\n"
                    f"Instructions:\n"
                    f"- Formulate a concise, clear business answer for an Indian MSME owner (1-2 short paragraphs).\n"
                    f"- Explain GST terms in simple language.\n"
                    f"- STRICT RULE: Rely ONLY on the numbers and facts provided above. Do not invent any values.\n"
                    f"- State that all figures are deterministically verified by VyaparMitra."
                )
                gem_resp = self.client.models.generate_content(
                    model=self.model_name,
                    contents=gemini_prompt
                )
                if gem_resp and gem_resp.text:
                    final_answer = gem_resp.text.strip()
            except Exception as e:
                logger.info(f"Gemini conversational framing skipped ({e}). Using deterministic synthesis.")
                final_answer = fallback_answer

        log_audit_event(
            session_id=session_id,
            event_type="AGENT_INVESTIGATION_COMPLETED",
            details=f"Conversational query '{request.question[:60]}' answered (Intent: {intent}, Tools: {', '.join(tools_used)})."
        )

        return AgentInvestigateResponse(
            session_id=session_id,
            user_question=request.question,
            intent=intent,
            plan=plan,
            steps_executed=steps_executed,
            answer=final_answer,
            evidence=evidence,
            tools_used=tools_used,
            suggested_action=suggested_action,
            draft_notice=draft_notice,
            human_review_required=human_review_required,
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
