from decimal import Decimal
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class SupplierRiskSignal(BaseModel):
    code: str = Field(..., description="Deterministic signal code: MISSING_2B, TAX_MISMATCH, etc.")
    label: str = Field(..., description="Human-readable signal label")
    severity: str = Field(..., description="Severity level: LOW, MEDIUM, HIGH, CRITICAL")
    reason: str = Field(..., description="Factual, deterministic explanation of the signal")
    count: int = Field(default=0, description="Number of supporting invoices")
    amount: Decimal = Field(default=Decimal("0.00"), description="Associated financial exposure in INR")


class SupplierRiskProfile(BaseModel):
    supplier_gstin: str
    supplier_name: str
    total_invoices: int = 0
    exact_matches: int = 0
    fuzzy_matches: int = 0
    tax_mismatches: int = 0
    missing_in_2b: int = 0
    missing_in_purchase_register: int = 0
    duplicate_candidates: int = 0
    invalid_records: int = 0
    total_purchase_tax: Decimal = Decimal("0.00")
    at_risk_itc: Decimal = Decimal("0.00")
    net_tax_variance: Decimal = Decimal("0.00")
    risk_score: int = Field(default=0, ge=0, le=100, description="Deterministic risk score 0-100")
    risk_category: str = Field(default="LOW", description="LOW, MEDIUM, HIGH, CRITICAL")
    score_breakdown: Dict[str, int] = Field(default_factory=dict)
    signals: List[SupplierRiskSignal] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    affected_invoices: List[Dict[str, Any]] = Field(default_factory=list)
    last_session_status: str = "ACTIVE"


class SupplierHistoryTrend(BaseModel):
    session_id: str
    created_at: str
    total_invoices: int = 0
    discrepancy_count: int = 0
    missing_in_2b: int = 0
    tax_mismatches: int = 0
    at_risk_itc: Decimal = Decimal("0.00")


class SupplierHistoryProfile(BaseModel):
    supplier_gstin: str
    supplier_name: str
    sessions_seen_count: int = 0
    has_sufficient_history: bool = False
    total_historical_invoices: int = 0
    total_historical_discrepancies: int = 0
    total_historical_at_risk_itc: Decimal = Decimal("0.00")
    detected_patterns: List[str] = Field(default_factory=list)
    trends: List[SupplierHistoryTrend] = Field(default_factory=list)
