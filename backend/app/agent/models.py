from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class AgentRequest(BaseModel):
    request: str = Field(..., min_length=3, description="User request in natural language")
    session_id: Optional[str] = Field(default=None, description="Optional active reconciliation session ID")

class SupplierDisputeNotice(BaseModel):
    notice_id: str
    supplier_reference: str
    invoice_reference: str
    discrepancy: str
    verified_amount: Decimal
    applicable_statutory_reference: str
    requested_supplier_action: str
    human_review_status: str = "DRAFT — REQUIRES HUMAN REVIEW"
    notice_body: str

class NoticeActionRequest(BaseModel):
    session_id: Optional[str] = None
    action: str = Field(..., description="Action: APPROVE, REJECT, or EDIT")
    updated_body: Optional[str] = None

class NoticeActionResponse(BaseModel):
    notice_id: str
    action: str
    status: str
    message: str

class AgentSessionStep(BaseModel):
    step_index: int
    current_step: str
    selected_tool: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[Dict[str, Any]] = None
    reasoning_summary: str
    timestamp: str

class AgentSessionState(BaseModel):
    session_id: str
    user_request: str
    current_step: str
    steps: List[AgentSessionStep] = Field(default_factory=list)
    tools_used: List[str] = Field(default_factory=list)
    final_action: Optional[str] = None
    timestamp: str

class AgentFinding(BaseModel):
    category: str
    description: str
    amount: Optional[Decimal] = None
    severity: str = "medium"
    recommended_action: str

class AgentAnalyzeResponse(BaseModel):
    status: str
    session_id: str
    summary: str
    findings: List[AgentFinding]
    actions: List[SupplierDisputeNotice]
    tools_used: List[str]
    human_review_required: bool = True
    disclaimer: str = (
        "VyaparMitra is an accounting and reconciliation assistance system. "
        "It does not constitute statutory legal advice. "
        "All supplier communications require human review and approval."
    )

# --- Phase 2 & 3 Conversational & Agentic Investigation Models ---

class AgentStepTrace(BaseModel):
    step_index: int
    tool_name: str
    tool_input: Dict[str, Any] = Field(default_factory=dict)
    observation_summary: str
    duration_ms: float = 0.0
    timestamp: str = ""
    status: str = "success"

class ToolCallRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)

class AgentInvestigateRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Conversational query regarding reconciliation session")
    session_id: Optional[str] = Field(default=None, description="Active reconciliation session ID")
    invoice_context: Optional[str] = Field(default=None, description="Optional invoice number context")

class AgentEvidenceItem(BaseModel):
    invoice_number: str
    supplier_gstin: str
    supplier_name: Optional[str] = ""
    purchase_tax: Optional[Decimal] = None
    gstr2b_tax: Optional[Decimal] = None
    tax_difference: Optional[Decimal] = None
    status: str
    statutory_rule: Optional[str] = None
    details: Optional[str] = None

class AgentInvestigateResponse(BaseModel):
    status: str = "success"
    session_id: str
    user_question: str
    intent: str
    plan: List[str] = Field(default_factory=list)
    steps_executed: List[AgentStepTrace] = Field(default_factory=list)
    answer: str
    evidence: List[AgentEvidenceItem] = Field(default_factory=list)
    tools_used: List[str] = Field(default_factory=list)
    suggested_action: Optional[str] = None
    draft_notice: Optional[SupplierDisputeNotice] = None
    human_review_required: bool = False
    disclaimer: str = (
        "VyaparMitra is an accounting and reconciliation assistance system. "
        "It does not constitute statutory legal advice. "
        "All supplier communications require human review and approval."
    )
