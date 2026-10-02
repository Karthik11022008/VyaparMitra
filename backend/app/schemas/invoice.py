from decimal import Decimal
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator

class MatchStatus(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    FUZZY_MATCH_REQUIRES_REVIEW = "FUZZY_MATCH_REQUIRES_REVIEW"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    MISSING_IN_2B = "MISSING_IN_2B"
    MISSING_IN_PURCHASE_REGISTER = "MISSING_IN_PURCHASE_REGISTER"
    DUPLICATE_CANDIDATE = "DUPLICATE_CANDIDATE"
    INVALID_DATA = "INVALID_DATA"

class PurchaseInvoice(BaseModel):
    supplier_gstin: str
    invoice_number: str
    invoice_date: str
    taxable_value: Decimal = Field(..., ge=0)
    cgst: Decimal = Field(default=Decimal("0.00"), ge=0)
    sgst: Decimal = Field(default=Decimal("0.00"), ge=0)
    igst: Decimal = Field(default=Decimal("0.00"), ge=0)
    total_value: Decimal = Field(default=Decimal("0.00"), ge=0)
    tax_period: str = Field(default="")
    supplier_name: Optional[str] = Field(default="")

    @field_validator("taxable_value", "cgst", "sgst", "igst", "total_value", mode="before")
    @classmethod
    def parse_decimal(cls, v):
        if isinstance(v, (int, float, str)):
            return round(Decimal(str(v).strip()), 2)
        return v

    @property
    def total_tax(self) -> Decimal:
        return self.cgst + self.sgst + self.igst

class GSTR2BInvoice(BaseModel):
    supplier_gstin: str
    invoice_number: str
    invoice_date: str
    taxable_value: Decimal = Field(..., ge=0)
    cgst: Decimal = Field(default=Decimal("0.00"), ge=0)
    sgst: Decimal = Field(default=Decimal("0.00"), ge=0)
    igst: Decimal = Field(default=Decimal("0.00"), ge=0)
    tax_period: str = Field(default="")
    supplier_name: Optional[str] = Field(default="")

    @field_validator("taxable_value", "cgst", "sgst", "igst", mode="before")
    @classmethod
    def parse_decimal(cls, v):
        if isinstance(v, (int, float, str)):
            return round(Decimal(str(v).strip()), 2)
        return v

    @property
    def total_tax(self) -> Decimal:
        return self.cgst + self.sgst + self.igst

class ReconciliationResult(BaseModel):
    status: MatchStatus
    purchase_invoice: Optional[PurchaseInvoice] = None
    matched_2b_invoice: Optional[GSTR2BInvoice] = None
    taxable_difference: Decimal = Decimal("0.00")
    tax_difference: Decimal = Decimal("0.00")
    confidence: float = 1.0
    reason: str
    rules_flagged: List[str] = Field(default_factory=list)

class SupplierSummary(BaseModel):
    supplier_gstin: str
    supplier_name: str = ""
    total_invoices: int = 0
    exact_matches: int = 0
    fuzzy_matches: int = 0
    amount_mismatches: int = 0
    missing_in_2b: int = 0
    missing_in_purchase_register: int = 0
    total_at_risk_itc: Decimal = Decimal("0.00")
    total_taxable_value: Decimal = Decimal("0.00")
    total_tax: Decimal = Decimal("0.00")

class ReconciliationSummary(BaseModel):
    total_purchase_invoices: int = 0
    total_2b_invoices: int = 0
    exact_matches: int = 0
    fuzzy_matches: int = 0
    amount_mismatches: int = 0
    missing_in_2b: int = 0
    missing_in_purchase_register: int = 0
    duplicate_candidates: int = 0
    invalid_records: int = 0
    total_purchase_itc: Decimal = Decimal("0.00")
    total_2b_itc: Decimal = Decimal("0.00")
    total_difference: Decimal = Decimal("0.00")
    total_at_risk_itc: Decimal = Decimal("0.00")

class ReconciliationResponse(BaseModel):
    status: str
    summary: ReconciliationSummary
    detailed_results: List[ReconciliationResult]
    session_id: Optional[str] = None
    supplier_summaries: List[SupplierSummary] = Field(default_factory=list)
