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

def tool_get_supplier_profile(session_id: Optional[str] = None, supplier_gstin: str = "") -> Dict[str, Any]:
    """Retrieves full deterministic risk profile, score (0-100), signals, and affected invoices for a supplier."""
    from backend.app.services.supplier_risk_service import build_supplier_risk_profile
    prof = build_supplier_risk_profile(session_id, supplier_gstin)
    if not prof:
        return {"found": False, "supplier_gstin": supplier_gstin, "error": f"Supplier '{supplier_gstin}' not found in active session."}
    d = prof.model_dump(mode="json")
    d["found"] = True
    return d

def tool_get_all_supplier_risk_profiles(session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves deterministic risk profiles for all suppliers in the session ranked by risk score."""
    from backend.app.services.supplier_risk_service import build_all_supplier_risk_profiles
    profs = build_all_supplier_risk_profiles(session_id)
    return [p.model_dump(mode="json") for p in profs]

def tool_get_supplier_history(supplier_gstin: str = "") -> Dict[str, Any]:
    """Retrieves multi-session historical trends and recurring compliance patterns for a supplier."""
    from backend.app.services.supplier_risk_service import get_supplier_history_profile
    hist = get_supplier_history_profile(supplier_gstin)
    return hist.model_dump(mode="json")

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
    "tool_get_supplier_profile": tool_get_supplier_profile,
    "tool_get_all_supplier_risk_profiles": tool_get_all_supplier_risk_profiles,
    "tool_get_supplier_history": tool_get_supplier_history,
}

from dataclasses import dataclass, field
import time
from datetime import datetime, timezone

@dataclass
class ToolContract:
    name: str
    description: str
    category: str  # "reconciliation", "validation", "normalization", "calculation", "statutory_lookup", "data_retrieval"
    parameters: Dict[str, Any]
    required_params: List[str]
    is_deterministic: bool = True
    requires_session: bool = False
    side_effect: bool = False

TOOL_CONTRACTS: Dict[str, ToolContract] = {
    "tool_run_reconciliation": ToolContract(
        name="tool_run_reconciliation",
        description="Executes full multi-stage deterministic reconciliation engine on demo or active dataset.",
        category="reconciliation",
        parameters={},
        required_params=[],
        is_deterministic=True,
        requires_session=False,
    ),
    "tool_validate_gstin": ToolContract(
        name="tool_validate_gstin",
        description="Validates 15-character Indian GSTIN structure and Luhn Mod 36 checksum.",
        category="validation",
        parameters={
            "gstin": {"type": "string", "description": "15-character GSTIN string to validate."}
        },
        required_params=["gstin"],
        is_deterministic=True,
        requires_session=False,
    ),
    "tool_normalize_invoice": ToolContract(
        name="tool_normalize_invoice",
        description="Normalizes an invoice number string by removing harmless delimiters and whitespace.",
        category="normalization",
        parameters={
            "invoice_number": {"type": "string", "description": "Raw invoice number string."}
        },
        required_params=["invoice_number"],
        is_deterministic=True,
        requires_session=False,
    ),
    "tool_calculate_tax_differences": ToolContract(
        name="tool_calculate_tax_differences",
        description="Deterministically computes monetary variance between purchase records and GSTR-2B using Decimal math.",
        category="calculation",
        parameters={
            "purchase_taxable": {"type": "number", "description": "Purchase record taxable value."},
            "purchase_cgst": {"type": "number", "description": "Purchase CGST amount."},
            "purchase_sgst": {"type": "number", "description": "Purchase SGST amount."},
            "purchase_igst": {"type": "number", "description": "Purchase IGST amount."},
            "gstr2b_taxable": {"type": "number", "description": "GSTR-2B taxable value."},
            "gstr2b_cgst": {"type": "number", "description": "GSTR-2B CGST amount."},
            "gstr2b_sgst": {"type": "number", "description": "GSTR-2B SGST amount."},
            "gstr2b_igst": {"type": "number", "description": "GSTR-2B IGST amount."},
            "tolerance": {"type": "number", "description": "Statutory tolerance in INR (default 1.00)."}
        },
        required_params=["purchase_taxable", "purchase_cgst", "purchase_sgst", "purchase_igst", "gstr2b_taxable", "gstr2b_cgst", "gstr2b_sgst", "gstr2b_igst"],
        is_deterministic=True,
        requires_session=False,
    ),
    "tool_calculate_section_50_interest": ToolContract(
        name="tool_calculate_section_50_interest",
        description="Deterministically calculates Section 50 simple interest on delayed tax payment or reversal under CGST Act.",
        category="calculation",
        parameters={
            "principal_tax": {"type": "number", "description": "Principal tax amount in INR at risk."},
            "delay_days": {"type": "integer", "description": "Number of days of delay."},
            "annual_rate": {"type": "number", "description": "Annual interest rate (default 0.18 for 18%)."}
        },
        required_params=["principal_tax", "delay_days"],
        is_deterministic=True,
        requires_session=False,
    ),
    "tool_lookup_statutory_rule": ToolContract(
        name="tool_lookup_statutory_rule",
        description="Retrieves statutory rule metadata and compliance guidance from the CGST statutory catalog.",
        category="statutory_lookup",
        parameters={
            "rule_id": {"type": "string", "description": "Rule identifier (e.g. RULE_16_2_AA, RULE_37A, RULE_SECTION_50)."}
        },
        required_params=["rule_id"],
        is_deterministic=True,
        requires_session=False,
    ),
    "tool_get_session_summary": ToolContract(
        name="tool_get_session_summary",
        description="Retrieves high-level deterministic reconciliation KPIs, counts, and at-risk ITC for a session.",
        category="data_retrieval",
        parameters={
            "session_id": {"type": "string", "description": "Active reconciliation session ID."}
        },
        required_params=[],
        is_deterministic=True,
        requires_session=True,
    ),
    "tool_get_missing_invoices": ToolContract(
        name="tool_get_missing_invoices",
        description="Returns all invoices present in internal purchase books but missing from GSTR-2B returns.",
        category="data_retrieval",
        parameters={
            "session_id": {"type": "string", "description": "Active reconciliation session ID."}
        },
        required_params=[],
        is_deterministic=True,
        requires_session=True,
    ),
    "tool_inspect_invoice": ToolContract(
        name="tool_inspect_invoice",
        description="Deep drill-down inspection for a specific invoice number in the active reconciliation session.",
        category="data_retrieval",
        parameters={
            "session_id": {"type": "string", "description": "Active reconciliation session ID."},
            "invoice_number": {"type": "string", "description": "Invoice number to inspect."}
        },
        required_params=["invoice_number"],
        is_deterministic=True,
        requires_session=True,
    ),
    "tool_get_supplier_discrepancies": ToolContract(
        name="tool_get_supplier_discrepancies",
        description="Aggregates and ranks counterparty suppliers by total at-risk ITC and missing invoices.",
        category="data_retrieval",
        parameters={
            "session_id": {"type": "string", "description": "Active reconciliation session ID."}
        },
        required_params=[],
        is_deterministic=True,
        requires_session=True,
    ),
    "tool_search_invoices": ToolContract(
        name="tool_search_invoices",
        description="Free-text search across invoice numbers, supplier GSTINs, and supplier names in the session.",
        category="data_retrieval",
        parameters={
            "session_id": {"type": "string", "description": "Active reconciliation session ID."},
            "query": {"type": "string", "description": "Search term (invoice number, GSTIN, or vendor name)."}
        },
        required_params=["query"],
        is_deterministic=True,
        requires_session=True,
    ),
    "tool_get_supplier_profile": ToolContract(
        name="tool_get_supplier_profile",
        description="Retrieves deterministic risk profile, score (0-100), risk signals, and affected invoices for a specific supplier.",
        category="data_retrieval",
        parameters={
            "session_id": {"type": "string", "description": "Active reconciliation session ID."},
            "supplier_gstin": {"type": "string", "description": "Supplier GSTIN to inspect."}
        },
        required_params=["supplier_gstin"],
        is_deterministic=True,
        requires_session=True,
    ),
    "tool_get_all_supplier_risk_profiles": ToolContract(
        name="tool_get_all_supplier_risk_profiles",
        description="Retrieves ranked risk profiles and scores for all counterparty suppliers in the session.",
        category="data_retrieval",
        parameters={
            "session_id": {"type": "string", "description": "Active reconciliation session ID."}
        },
        required_params=[],
        is_deterministic=True,
        requires_session=True,
    ),
    "tool_get_supplier_history": ToolContract(
        name="tool_get_supplier_history",
        description="Retrieves multi-session historical compliance trends and recurring discrepancy patterns for a supplier.",
        category="data_retrieval",
        parameters={
            "supplier_gstin": {"type": "string", "description": "Supplier GSTIN to look up historical trends."}
        },
        required_params=["supplier_gstin"],
        is_deterministic=True,
        requires_session=False,
    ),
}

TOOL_DEFINITIONS = [
    {
        "name": c.name,
        "description": c.description,
        "parameters": {
            "type": "object",
            "properties": c.parameters,
            "required": c.required_params
        }
    }
    for c in TOOL_CONTRACTS.values()
]

def validate_and_call_tool(
    tool_name: str,
    arguments: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    step_index: int = 1,
) -> Dict[str, Any]:
    """
    Phase 3 Authoritative Tool Validation and Execution Adapter:
    1. Verifies tool exists in registered AVAILABLE_TOOLS.
    2. Enforces session_id if requires_session is True.
    3. Validates required parameters against ToolContract.
    4. Rejects unsafe arguments, prevents arbitrary execution, executes only registered Python functions.
    5. Measures execution duration (ms) and creates concise operational summary.
    """
    args = dict(arguments or {})
    start_time = time.perf_counter()
    now_iso = datetime.now(timezone.utc).isoformat()

    if tool_name not in AVAILABLE_TOOLS:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "success": False,
            "status": "ERROR",
            "step_index": step_index,
            "tool_name": tool_name,
            "tool_input": args,
            "data": None,
            "observation_summary": f"Rejected: Tool '{tool_name}' is not in the registered tool catalog.",
            "duration_ms": duration_ms,
            "timestamp": now_iso,
            "error": f"Tool '{tool_name}' not found."
        }

    contract = TOOL_CONTRACTS.get(tool_name)
    if not contract:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "success": False,
            "status": "ERROR",
            "step_index": step_index,
            "tool_name": tool_name,
            "tool_input": args,
            "data": None,
            "observation_summary": f"Rejected: Tool '{tool_name}' has no registered contract.",
            "duration_ms": duration_ms,
            "timestamp": now_iso,
            "error": f"Tool contract missing for '{tool_name}'."
        }

    # Session ID enforcement
    effective_session_id = session_id or args.get("session_id")
    if contract.requires_session:
        if not effective_session_id:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "success": False,
                "status": "ERROR",
                "step_index": step_index,
                "tool_name": tool_name,
                "tool_input": args,
                "data": None,
                "observation_summary": f"Rejected: Tool '{tool_name}' requires an active session_id.",
                "duration_ms": duration_ms,
                "timestamp": now_iso,
                "error": f"Session ID required for tool '{tool_name}'."
            }
        args["session_id"] = effective_session_id

    # Validate required parameters
    for req in contract.required_params:
        if req not in args or args[req] is None or (isinstance(args[req], str) and not args[req].strip()):
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "success": False,
                "status": "ERROR",
                "step_index": step_index,
                "tool_name": tool_name,
                "tool_input": args,
                "data": None,
                "observation_summary": f"Rejected: Missing required parameter '{req}' for tool '{tool_name}'.",
                "duration_ms": duration_ms,
                "timestamp": now_iso,
                "error": f"Missing required parameter '{req}'."
            }

    # Execute deterministic Python function
    fn = AVAILABLE_TOOLS[tool_name]
    try:
        # Pass only parameters accepted by fn
        import inspect
        sig = inspect.signature(fn)
        fn_params = set(sig.parameters.keys())
        filtered_args = {k: v for k, v in args.items() if k in fn_params}

        # Type conversion safeguards
        if "principal_tax" in filtered_args:
            filtered_args["principal_tax"] = float(filtered_args["principal_tax"])
        if "delay_days" in filtered_args:
            filtered_args["delay_days"] = int(filtered_args["delay_days"])
        if "annual_rate" in filtered_args:
            filtered_args["annual_rate"] = float(filtered_args["annual_rate"])
        for k in ["purchase_taxable", "purchase_cgst", "purchase_sgst", "purchase_igst", "gstr2b_taxable", "gstr2b_cgst", "gstr2b_sgst", "gstr2b_igst"]:
            if k in filtered_args:
                filtered_args[k] = float(filtered_args[k])

        result = fn(**filtered_args)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Build concise operational summary
        summary = _build_observation_summary(tool_name, filtered_args, result)

        return {
            "success": True,
            "status": "SUCCESS",
            "step_index": step_index,
            "tool_name": tool_name,
            "tool_input": filtered_args,
            "data": result,
            "observation_summary": summary,
            "duration_ms": duration_ms,
            "timestamp": now_iso,
            "error": None
        }
    except Exception as e:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "success": False,
            "status": "ERROR",
            "step_index": step_index,
            "tool_name": tool_name,
            "tool_input": args,
            "data": None,
            "observation_summary": f"Failed: Execution of '{tool_name}' raised {type(e).__name__}: {str(e)}.",
            "duration_ms": duration_ms,
            "timestamp": now_iso,
            "error": str(e)
        }

def _build_observation_summary(tool_name: str, args: Dict[str, Any], result: Any) -> str:
    """Builds a concise operational summary without exposing internal chain of thought."""
    if tool_name == "tool_get_session_summary":
        if isinstance(result, dict) and result.get("found"):
            return f"Retrieved session summary: {result.get('total_purchase_invoices', 0)} purchase vs {result.get('total_2b_invoices', 0)} 2B records, ₹{result.get('total_at_risk_itc', 0):,.2f} at-risk ITC."
        return "Session summary not found."

    if tool_name == "tool_get_missing_invoices":
        count = len(result) if isinstance(result, list) else 0
        total_risk = sum(r.get("at_risk_itc", 0) for r in result) if isinstance(result, list) else 0
        return f"Located {count} missing in GSTR-2B invoice(s) representing ₹{total_risk:,.2f} at-risk ITC."

    if tool_name == "tool_inspect_invoice":
        if isinstance(result, dict) and result.get("found"):
            return f"Inspected invoice {result.get('invoice_number')}: status={result.get('status')}, tax variance=₹{result.get('tax_difference', 0):,.2f}."
        inv = args.get("invoice_number", "")
        return f"Invoice '{inv}' not found in active session records."

    if tool_name == "tool_get_supplier_discrepancies":
        count = len(result) if isinstance(result, list) else 0
        discrepant = [s for s in result if s.get("total_at_risk_itc", 0) > 0] if isinstance(result, list) else []
        top = discrepant[0]["supplier_name"] if discrepant else "None"
        return f"Analyzed {count} counterparty suppliers ({len(discrepant)} with discrepancies). Highest risk: {top}."

    if tool_name == "tool_search_invoices":
        count = len(result) if isinstance(result, list) else 0
        q = args.get("query", "")
        return f"Search for '{q}' returned {count} matching invoice record(s)."

    if tool_name == "tool_calculate_tax_differences":
        diff = result.get("total_tax_diff", 0.0) if isinstance(result, dict) else 0.0
        tol = result.get("is_within_tolerance", True) if isinstance(result, dict) else True
        return f"Calculated tax variance: ₹{diff:,.2f} (within statutory tolerance: {tol})."

    if tool_name == "tool_calculate_section_50_interest":
        interest = result.get("calculated_interest", 0.0) if isinstance(result, dict) else 0.0
        rate = result.get("annual_rate", 0.18) if isinstance(result, dict) else 0.18
        days = result.get("delay_days", 0) if isinstance(result, dict) else 0
        return f"Computed Section 50 simple interest @ {rate*100:.0f}% p.a. for {days} days: ₹{interest:,.2f}."

    if tool_name == "tool_lookup_statutory_rule":
        if isinstance(result, dict) and "statutory_reference" in result:
            return f"Retrieved statutory citation: {result.get('statutory_reference')}."
        return f"Looked up rule {args.get('rule_id')}."

    if tool_name == "tool_validate_gstin":
        valid = result.get("is_valid", False) if isinstance(result, dict) else False
        return f"Validated GSTIN {args.get('gstin')}: checksum valid = {valid}."

    if tool_name == "tool_normalize_invoice":
        norm = result.get("normalized", "") if isinstance(result, dict) else ""
        return f"Normalized invoice number '{args.get('invoice_number')}' to '{norm}'."

    if tool_name == "tool_run_reconciliation":
        return "Executed deterministic reconciliation engine across active datasets."

    if tool_name == "tool_get_supplier_profile":
        if isinstance(result, dict) and result.get("found"):
            return f"Supplier {result.get('supplier_name', '')} ({result.get('supplier_gstin', '')}): Risk Score {result.get('risk_score', 0)}/100 ({result.get('risk_category', '')}), {len(result.get('signals', []))} signals, ₹{result.get('at_risk_itc', 0):,.2f} at-risk ITC."
        gstin = args.get("supplier_gstin", "")
        return f"Supplier '{gstin}' profile not found in active session."

    if tool_name == "tool_get_all_supplier_risk_profiles":
        count = len(result) if isinstance(result, list) else 0
        top = result[0].get("supplier_name") if count > 0 else "None"
        top_score = result[0].get("risk_score") if count > 0 else 0
        return f"Audited {count} suppliers across session. Highest risk: {top} ({top_score}/100)."

    if tool_name == "tool_get_supplier_history":
        cnt = result.get("sessions_seen_count", 0) if isinstance(result, dict) else 0
        pats = len(result.get("detected_patterns", [])) if isinstance(result, dict) else 0
        return f"Historical audit for {args.get('supplier_gstin')}: seen in {cnt} session(s), {pats} recurring pattern(s) identified."

    return f"Completed tool '{tool_name}' successfully."
