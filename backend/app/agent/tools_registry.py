from decimal import Decimal
from typing import Dict, Any, List
from backend.app.tools.normalization import normalize_invoice_number, normalize_gstin
from backend.app.tools.gstin_validator import validate_gstin
from backend.app.tools.tax_calculator import calculate_tax_differences
from backend.app.tools.interest_calculator import calculate_section_50_interest
from backend.app.tools.statutory_rules import STATUTORY_RULES_CATALOG
from backend.app.services.reconciliation_service import reconcile_demo_dataset

def tool_normalize_invoice(invoice_number: str) -> Dict[str, Any]:
    """Deterministically normalizes an invoice string by removing harmless separators."""
    normalized = normalize_invoice_number(invoice_number)
    return {
        "original": invoice_number,
        "normalized": normalized
    }

def tool_validate_gstin(gstin: str) -> Dict[str, Any]:
    """Validates an Indian 15-character GSTIN structure and Luhn Mod 36 checksum."""
    res = validate_gstin(gstin)
    return res.model_dump()

def tool_calculate_tax_differences(
    purchase_taxable: float,
    purchase_cgst: float,
    purchase_sgst: float,
    purchase_igst: float,
    gstr2b_taxable: float,
    gstr2b_cgst: float,
    gstr2b_sgst: float,
    gstr2b_igst: float,
    tolerance: float = 1.00
) -> Dict[str, Any]:
    """Deterministically computes monetary variance between purchase records and GSTR-2B using Decimal."""
    res = calculate_tax_differences(
        Decimal(str(purchase_taxable)),
        Decimal(str(purchase_cgst)),
        Decimal(str(purchase_sgst)),
        Decimal(str(purchase_igst)),
        Decimal(str(gstr2b_taxable)),
        Decimal(str(gstr2b_cgst)),
        Decimal(str(gstr2b_sgst)),
        Decimal(str(gstr2b_igst)),
        Decimal(str(tolerance))
    )
    return {
        "taxable_diff": float(res.taxable_diff),
        "cgst_diff": float(res.cgst_diff),
        "sgst_diff": float(res.sgst_diff),
        "igst_diff": float(res.igst_diff),
        "total_tax_diff": float(res.total_tax_diff),
        "is_within_tolerance": res.is_within_tolerance
    }

def tool_calculate_section_50_interest(
    principal_tax: float,
    delay_days: int,
    annual_rate: float = 0.18
) -> Dict[str, Any]:
    """Computes statutory simple interest on delayed tax payment under Section 50."""
    res = calculate_section_50_interest(
        Decimal(str(principal_tax)),
        delay_days,
        Decimal(str(annual_rate))
    )
    return {
        "principal": float(res.principal),
        "annual_rate": float(res.annual_rate),
        "delay_days": res.delay_days,
        "calculated_interest": float(res.calculated_interest),
        "daily_rate": float(res.daily_rate)
    }

def tool_lookup_statutory_rule(rule_id: str) -> Dict[str, Any]:
    """Looks up compliance reference and non-legal guidance for statutory rule."""
    rule = STATUTORY_RULES_CATALOG.get(rule_id.upper())
    if not rule:
        return {"error": f"Rule '{rule_id}' not found in statutory catalog."}
    return rule.model_dump()

def tool_run_reconciliation() -> Dict[str, Any]:
    """Runs the deterministic multi-stage reconciliation engine on the verified dataset."""
    res = reconcile_demo_dataset()
    return res.model_dump(mode="json")

# Tool metadata for Agent registration & dispatch
AVAILABLE_TOOLS = {
    "tool_run_reconciliation": tool_run_reconciliation,
    "tool_validate_gstin": tool_validate_gstin,
    "tool_normalize_invoice": tool_normalize_invoice,
    "tool_calculate_tax_differences": tool_calculate_tax_differences,
    "tool_calculate_section_50_interest": tool_calculate_section_50_interest,
    "tool_lookup_statutory_rule": tool_lookup_statutory_rule,
}

TOOL_DEFINITIONS = [
    {
        "name": "tool_run_reconciliation",
        "description": "Executes full multi-stage reconciliation between purchase registers and GSTR-2B. Returns exact matches, fuzzy matches, amount variances, missing invoices, and flagged statutory rules.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "tool_validate_gstin",
        "description": "Validates 15-character Indian GSTIN structure and Luhn Mod 36 checksum.",
        "parameters": {
            "type": "object",
            "properties": {
                "gstin": {"type": "string", "description": "The 15-character GSTIN to validate."}
            },
            "required": ["gstin"]
        }
    },
    {
        "name": "tool_normalize_invoice",
        "description": "Normalizes invoice number by stripping harmless delimiters and whitespace.",
        "parameters": {
            "type": "object",
            "properties": {
                "invoice_number": {"type": "string", "description": "Raw invoice number string."}
            },
            "required": ["invoice_number"]
        }
    },
    {
        "name": "tool_calculate_tax_differences",
        "description": "Calculates tax differences and validates within statutory tolerance.",
        "parameters": {
            "type": "object",
            "properties": {
                "purchase_taxable": {"type": "number"},
                "purchase_cgst": {"type": "number"},
                "purchase_sgst": {"type": "number"},
                "purchase_igst": {"type": "number"},
                "gstr2b_taxable": {"type": "number"},
                "gstr2b_cgst": {"type": "number"},
                "gstr2b_sgst": {"type": "number"},
                "gstr2b_igst": {"type": "number"}
            },
            "required": ["purchase_taxable", "purchase_cgst", "purchase_sgst", "purchase_igst", "gstr2b_taxable", "gstr2b_cgst", "gstr2b_sgst", "gstr2b_igst"]
        }
    },
    {
        "name": "tool_calculate_section_50_interest",
        "description": "Deterministically calculates Section 50 interest for delayed tax payment using Decimal math.",
        "parameters": {
            "type": "object",
            "properties": {
                "principal_tax": {"type": "number", "description": "The principal tax amount in dispute or delay."},
                "delay_days": {"type": "integer", "description": "Number of days of delay."},
                "annual_rate": {"type": "number", "description": "Annual interest rate (default 0.18 for 18%)."}
            },
            "required": ["principal_tax", "delay_days"]
        }
    },
    {
        "name": "tool_lookup_statutory_rule",
        "description": "Retrieves statutory rule metadata and review guidance from statutory catalog.",
        "parameters": {
            "type": "object",
            "properties": {
                "rule_id": {"type": "string", "description": "Rule identifier (e.g. RULE_16_2_AA, RULE_37A, RULE_AMOUNT_MISMATCH)."}
            },
            "required": ["rule_id"]
        }
    }
]
