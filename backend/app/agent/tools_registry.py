from decimal import Decimal
from typing import Dict, Any, List, Optional
from backend.app.schemas.invoice import MatchStatus, ReconciliationResponse
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

def _get_recon_response(session_id: Optional[str] = None) -> Optional[ReconciliationResponse]:
    """Helper to retrieve reconciliation data deterministically from active cache or SQLite."""
    from backend.app.services.reconciliation_service import (
        SESSION_DATA_CACHE,
        restore_session_from_db,
        reconcile_demo_dataset,
    )
    if not session_id:
        return reconcile_demo_dataset()

    cache = SESSION_DATA_CACHE.get(session_id)
    if cache and cache.get("reconciliation_response"):
        return cache["reconciliation_response"]

    restored = restore_session_from_db(session_id)
    if restored:
        return restored

    if session_id.startswith("sess-demo") or session_id == "demo-session":
        return reconcile_demo_dataset(session_id=session_id)

    return None

def tool_get_session_summary(session_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieves high-level deterministic reconciliation KPIs and summary figures for a session."""
    resp = _get_recon_response(session_id)
    if not resp:
        return {"found": False, "error": f"Session '{session_id}' not found."}
    s = resp.summary
    return {
        "found": True,
        "session_id": session_id or "demo-session",
        "total_purchase_invoices": s.total_purchase_invoices,
        "total_2b_invoices": s.total_2b_invoices,
        "exact_matches": s.exact_matches,
        "fuzzy_matches": s.fuzzy_matches,
        "amount_mismatches": s.amount_mismatches,
        "missing_in_2b": s.missing_in_2b,
        "missing_in_purchase_register": s.missing_in_purchase_register,
        "duplicate_candidates": s.duplicate_candidates,
        "invalid_records": s.invalid_records,
        "total_at_risk_itc": float(s.total_at_risk_itc),
        "total_difference": float(s.total_difference),
        "total_purchase_itc": float(s.total_purchase_itc),
        "total_2b_itc": float(s.total_2b_itc),
    }

def tool_get_missing_invoices(session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns all invoices present in internal purchase books but missing from GSTR-2B returns."""
    resp = _get_recon_response(session_id)
    if not resp:
        return []
    missing = []
    for r in resp.detailed_results:
        if r.status == MatchStatus.MISSING_IN_2B and r.purchase_invoice:
            p = r.purchase_invoice
            missing.append({
                "invoice_number": p.invoice_number,
                "supplier_gstin": p.supplier_gstin,
                "supplier_name": p.supplier_name or "",
                "taxable_value": float(p.taxable_value),
                "total_tax": float(p.total_tax),
                "at_risk_itc": float(p.total_tax),
                "status": "MISSING_IN_2B",
                "statutory_rule": "Section 16(2)(aa)",
                "reason": r.reason
            })
    return missing

def tool_inspect_invoice(session_id: Optional[str] = None, invoice_number: str = "") -> Dict[str, Any]:
    """Inspects a specific invoice in the reconciliation session and returns deterministic evidence."""
    if not invoice_number or not invoice_number.strip():
        return {"found": False, "error": "Invoice number cannot be empty."}
    resp = _get_recon_response(session_id)
    if not resp:
        return {"found": False, "error": f"Session '{session_id}' not found."}

    clean_target = normalize_invoice_number(invoice_number).upper()
    raw_target = invoice_number.strip().upper()

    for r in resp.detailed_results:
        p_num = r.purchase_invoice.invoice_number.strip().upper() if r.purchase_invoice else ""
        b_num = r.matched_2b_invoice.invoice_number.strip().upper() if r.matched_2b_invoice else ""

        p_norm = normalize_invoice_number(p_num).upper() if p_num else ""
        b_norm = normalize_invoice_number(b_num).upper() if b_num else ""

        if raw_target in (p_num, b_num) or clean_target in (p_norm, b_norm) or (clean_target and clean_target in p_norm) or (clean_target and clean_target in b_norm):
            p = r.purchase_invoice
            b = r.matched_2b_invoice
            rule = None
            if r.status == MatchStatus.MISSING_IN_2B:
                rule = "Section 16(2)(aa)"
            elif r.status == MatchStatus.AMOUNT_MISMATCH:
                rule = "Rule 37A / Tax Mismatch"
            elif r.status == MatchStatus.DUPLICATE_CANDIDATE:
                rule = "Internal Duplicate Prevention"
            elif r.status == MatchStatus.INVALID_DATA:
                rule = "Section 155 / GSTIN Validation"

            return {
                "found": True,
                "invoice_number": p.invoice_number if p else (b.invoice_number if b else invoice_number),
                "supplier_gstin": p.supplier_gstin if p else (b.supplier_gstin if b else ""),
                "supplier_name": p.supplier_name if p and p.supplier_name else (b.supplier_name if b and b.supplier_name else ""),
                "purchase_tax": float(p.total_tax) if p else None,
                "gstr2b_tax": float(b.total_tax) if b else None,
                "tax_difference": float(r.tax_difference) if r.tax_difference is not None else 0.0,
                "status": r.status.value,
                "confidence": r.confidence,
                "reason": r.reason,
                "statutory_rule": rule
            }

    return {
        "found": False,
        "invoice_number": invoice_number,
        "message": f"Invoice '{invoice_number}' not found in active session records."
    }

def tool_get_supplier_discrepancies(session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Ranks and aggregates suppliers by total at-risk ITC and discrepancy count."""
    resp = _get_recon_response(session_id)
    if not resp:
        return []
    return [
        {
            "supplier_gstin": s.supplier_gstin,
            "supplier_name": s.supplier_name,
            "total_invoices": s.total_invoices,
            "missing_in_2b": s.missing_in_2b,
            "amount_mismatches": s.amount_mismatches,
            "fuzzy_matches": s.fuzzy_matches,
            "exact_matches": s.exact_matches,
            "total_at_risk_itc": float(s.total_at_risk_itc),
        }
        for s in resp.supplier_summaries
    ]

def tool_search_invoices(session_id: Optional[str] = None, query: str = "") -> List[Dict[str, Any]]:
    """Performs multi-attribute search across invoice numbers, supplier GSTINs, and supplier names."""
    if not query or not query.strip():
        return []
    resp = _get_recon_response(session_id)
    if not resp:
        return []
    q = query.strip().lower()
    matches = []
    for r in resp.detailed_results:
        p = r.purchase_invoice
        b = r.matched_2b_invoice
        inv_no = (p.invoice_number if p else (b.invoice_number if b else "")).lower()
        gstin = (p.supplier_gstin if p else (b.supplier_gstin if b else "")).lower()
        name = (p.supplier_name if p and p.supplier_name else (b.supplier_name if b and b.supplier_name else "")).lower()

        if q in inv_no or q in gstin or q in name:
            matches.append({
                "invoice_number": p.invoice_number if p else (b.invoice_number if b else ""),
                "supplier_gstin": p.supplier_gstin if p else (b.supplier_gstin if b else ""),
                "supplier_name": p.supplier_name if p and p.supplier_name else (b.supplier_name if b and b.supplier_name else ""),
                "purchase_tax": float(p.total_tax) if p else None,
                "gstr2b_tax": float(b.total_tax) if b else None,
                "tax_difference": float(r.tax_difference) if r.tax_difference is not None else 0.0,
                "status": r.status.value,
                "reason": r.reason
            })
    return matches[:20]

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
    "tool_get_session_summary": tool_get_session_summary,
    "tool_get_missing_invoices": tool_get_missing_invoices,
    "tool_inspect_invoice": tool_inspect_invoice,
    "tool_get_supplier_discrepancies": tool_get_supplier_discrepancies,
    "tool_search_invoices": tool_search_invoices,
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
