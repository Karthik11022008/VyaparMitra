import csv
from decimal import Decimal
from pathlib import Path
from typing import List, Tuple, Union, Optional, Dict, Any
from datetime import datetime, timezone
import io
import json

from backend.app.schemas.invoice import (
    PurchaseInvoice,
    GSTR2BInvoice,
    ReconciliationResult,
    ReconciliationSummary,
    ReconciliationResponse,
    MatchStatus,
)
from backend.app.tools.matching_engine import InvoiceMatchingEngine
from backend.app.config import BASE_DIR
from backend.app.database import save_or_update_session, get_reconciliation_session, log_audit_event

# In-memory session cache for fast access to active uploaded datasets
SESSION_DATA_CACHE: Dict[str, Dict[str, Any]] = {}

def get_session_cache(session_id: str) -> Dict[str, Any]:
    if session_id not in SESSION_DATA_CACHE:
        SESSION_DATA_CACHE[session_id] = {
            "purchase_invoices": [],
            "gstr2b_invoices": [],
            "purchase_filename": "",
            "gstr2b_filename": "",
            "reconciliation_response": None,
        }
    return SESSION_DATA_CACHE[session_id]

def parse_purchase_csv(content: Union[str, Path, io.StringIO]) -> List[PurchaseInvoice]:
    invoices: List[PurchaseInvoice] = []
    if isinstance(content, Path):
        with open(content, "r", encoding="utf-8") as f:
            lines = [line for line in f if not line.strip().startswith("#")]
    elif isinstance(content, str):
        lines = [line for line in content.splitlines() if not line.strip().startswith("#")]
    else:
        lines = [line for line in content.getvalue().splitlines() if not line.strip().startswith("#")]

    reader = csv.DictReader(lines)
    for row in reader:
        if not row or not any(row.values()):
            continue
        invoices.append(
            PurchaseInvoice(
                supplier_gstin=row.get("supplier_gstin", "").strip(),
                invoice_number=row.get("invoice_number", "").strip(),
                invoice_date=row.get("invoice_date", "").strip(),
                taxable_value=Decimal(str(row.get("taxable_value", "0")).strip()),
                cgst=Decimal(str(row.get("cgst", "0")).strip() or "0"),
                sgst=Decimal(str(row.get("sgst", "0")).strip() or "0"),
                igst=Decimal(str(row.get("igst", "0")).strip() or "0"),
                total_value=Decimal(str(row.get("total_value", "0")).strip() or "0"),
                tax_period=row.get("tax_period", "").strip(),
            )
        )
    return invoices

def parse_gstr2b_csv(content: Union[str, Path, io.StringIO]) -> List[GSTR2BInvoice]:
    invoices: List[GSTR2BInvoice] = []
    if isinstance(content, Path):
        with open(content, "r", encoding="utf-8") as f:
            lines = [line for line in f if not line.strip().startswith("#")]
    elif isinstance(content, str):
        lines = [line for line in content.splitlines() if not line.strip().startswith("#")]
    else:
        lines = [line for line in content.getvalue().splitlines() if not line.strip().startswith("#")]

    reader = csv.DictReader(lines)
    for row in reader:
        if not row or not any(row.values()):
            continue
        invoices.append(
            GSTR2BInvoice(
                supplier_gstin=row.get("supplier_gstin", "").strip(),
                invoice_number=row.get("invoice_number", "").strip(),
                invoice_date=row.get("invoice_date", "").strip(),
                taxable_value=Decimal(str(row.get("taxable_value", "0")).strip()),
                cgst=Decimal(str(row.get("cgst", "0")).strip() or "0"),
                sgst=Decimal(str(row.get("sgst", "0")).strip() or "0"),
                igst=Decimal(str(row.get("igst", "0")).strip() or "0"),
                tax_period=row.get("tax_period", "").strip(),
            )
        )
    return invoices

def build_summary(
    results: List[ReconciliationResult],
    purchase_invoices: List[PurchaseInvoice],
    gstr2b_invoices: List[GSTR2BInvoice],
) -> ReconciliationSummary:
    exact_matches = 0
    fuzzy_matches = 0
    amount_mismatches = 0
    missing_in_2b = 0
    missing_in_purchase = 0
    duplicate_candidates = 0
    invalid_records = 0

    total_at_risk_itc = Decimal("0.00")

    for item in results:
        if item.status == MatchStatus.EXACT_MATCH:
            exact_matches += 1
        elif item.status == MatchStatus.FUZZY_MATCH_REQUIRES_REVIEW:
            fuzzy_matches += 1
            if item.tax_difference > 0:
                total_at_risk_itc += item.tax_difference
        elif item.status == MatchStatus.AMOUNT_MISMATCH:
            amount_mismatches += 1
            if item.tax_difference > 0:
                total_at_risk_itc += item.tax_difference
        elif item.status == MatchStatus.MISSING_IN_2B:
            missing_in_2b += 1
            if item.purchase_invoice:
                total_at_risk_itc += item.purchase_invoice.total_tax
        elif item.status == MatchStatus.MISSING_IN_PURCHASE_REGISTER:
            missing_in_purchase += 1
        elif item.status == MatchStatus.DUPLICATE_CANDIDATE:
            duplicate_candidates += 1
            if item.purchase_invoice:
                total_at_risk_itc += item.purchase_invoice.total_tax
        elif item.status == MatchStatus.INVALID_DATA:
            invalid_records += 1
            if item.purchase_invoice:
                total_at_risk_itc += item.purchase_invoice.total_tax

    total_purchase_itc = sum(inv.total_tax for inv in purchase_invoices)
    total_2b_itc = sum(inv.total_tax for inv in gstr2b_invoices)
    total_difference = round(total_purchase_itc - total_2b_itc, 2)

    return ReconciliationSummary(
        total_purchase_invoices=len(purchase_invoices),
        total_2b_invoices=len(gstr2b_invoices),
        exact_matches=exact_matches,
        fuzzy_matches=fuzzy_matches,
        amount_mismatches=amount_mismatches,
        missing_in_2b=missing_in_2b,
        missing_in_purchase_register=missing_in_purchase,
        duplicate_candidates=duplicate_candidates,
        invalid_records=invalid_records,
        total_purchase_itc=round(total_purchase_itc, 2),
        total_2b_itc=round(total_2b_itc, 2),
        total_difference=total_difference,
        total_at_risk_itc=round(total_at_risk_itc, 2),
    )

def run_reconciliation(
    purchase_invoices: List[PurchaseInvoice],
    gstr2b_invoices: List[GSTR2BInvoice],
) -> ReconciliationResponse:
    """Executes deterministic multi-stage matching engine on provided invoice lists."""
    engine = InvoiceMatchingEngine()
    detailed_results = engine.reconcile(purchase_invoices, gstr2b_invoices)
    summary = build_summary(detailed_results, purchase_invoices, gstr2b_invoices)
    return ReconciliationResponse(
        status="success",
        summary=summary,
        detailed_results=detailed_results,
    )

def reconcile_demo_dataset(session_id: Optional[str] = None) -> ReconciliationResponse:
    """Runs deterministic reconciliation on the static synthetic demo dataset and establishes a valid session."""
    import uuid
    active_session_id = session_id or f"sess-demo-{uuid.uuid4().hex[:8]}"
    purchase_csv_path = BASE_DIR / "data" / "demo" / "purchase_register.csv"
    gstr2b_csv_path = BASE_DIR / "data" / "demo" / "gstr2b.csv"

    purchase_invoices = parse_purchase_csv(purchase_csv_path)
    gstr2b_invoices = parse_gstr2b_csv(gstr2b_csv_path)

    cache = get_session_cache(active_session_id)
    cache["purchase_invoices"] = purchase_invoices
    cache["gstr2b_invoices"] = gstr2b_invoices
    cache["purchase_filename"] = "purchase_register.csv"
    cache["gstr2b_filename"] = "gstr2b.csv"

    if active_session_id != "demo-session":
        demo_cache = get_session_cache("demo-session")
        demo_cache["purchase_invoices"] = purchase_invoices
        demo_cache["gstr2b_invoices"] = gstr2b_invoices
        demo_cache["purchase_filename"] = "purchase_register.csv"
        demo_cache["gstr2b_filename"] = "gstr2b.csv"

    save_or_update_session(
        session_id=active_session_id,
        status="FILES_UPLOADED",
        purchase_filename="purchase_register.csv",
        purchase_row_count=len(purchase_invoices),
        gstr2b_filename="gstr2b.csv",
        gstr2b_row_count=len(gstr2b_invoices),
    )

    log_audit_event(
        session_id=active_session_id,
        event_type="FILE_UPLOADED",
        details=f"Loaded demo dataset: Purchase Register ({len(purchase_invoices)} records), GSTR-2B ({len(gstr2b_invoices)} records)."
    )
    log_audit_event(
        session_id=active_session_id,
        event_type="FILE_VALIDATED",
        details="Validation status: VALID for both demo registers."
    )

    response = reconcile_session(active_session_id)
    response.session_id = active_session_id

    if active_session_id != "demo-session":
        demo_cache = get_session_cache("demo-session")
        demo_cache["reconciliation_response"] = response

    return response

def reconcile_session(session_id: str) -> ReconciliationResponse:
    """Reconciles the uploaded datasets stored under a session ID."""
    cache = get_session_cache(session_id)
    purchase_invoices = cache.get("purchase_invoices", [])
    gstr2b_invoices = cache.get("gstr2b_invoices", [])

    if not purchase_invoices or not gstr2b_invoices:
        session_info = get_reconciliation_session(session_id)
        if session_info:
            p_file = session_info.get("purchase_filepath")
            b_file = session_info.get("gstr2b_filepath")
            if p_file and b_file:
                from backend.app.config import settings
                from backend.app.services.file_parser import parse_and_validate_file
                p_path = settings.UPLOAD_DIR / p_file
                b_path = settings.UPLOAD_DIR / b_file
                if p_path.exists() and b_path.exists():
                    with open(p_path, "rb") as f:
                        p_res = parse_and_validate_file(f.read(), session_info.get("purchase_filename", "purchase"), target_type="purchase")
                    with open(b_path, "rb") as f:
                        b_res = parse_and_validate_file(f.read(), session_info.get("gstr2b_filename", "gstr2b"), target_type="gstr2b")
                    if p_res.success and b_res.success:
                        purchase_invoices = p_res.purchase_invoices
                        gstr2b_invoices = b_res.gstr2b_invoices
                        cache["purchase_invoices"] = purchase_invoices
                        cache["gstr2b_invoices"] = gstr2b_invoices
                        cache["purchase_filename"] = session_info.get("purchase_filename")
                        cache["gstr2b_filename"] = session_info.get("gstr2b_filename")

    if not purchase_invoices:
        raise ValueError("Session does not contain valid Purchase Register records.")
    if not gstr2b_invoices:
        raise ValueError("Session does not contain valid GSTR-2B records.")

    log_audit_event(
        session_id=session_id,
        event_type="RECONCILIATION_STARTED",
        details=f"Executing deterministic reconciliation for {len(purchase_invoices)} purchase and {len(gstr2b_invoices)} GSTR-2B records."
    )

    response = run_reconciliation(purchase_invoices, gstr2b_invoices)
    response.session_id = session_id
    cache["reconciliation_response"] = response

    # Persist summary in DB
    summary_dict = response.summary.model_dump(mode="json")
    save_or_update_session(
        session_id=session_id,
        status="RECONCILED",
        summary_json=json.dumps(summary_dict)
    )

    log_audit_event(
        session_id=session_id,
        event_type="RECONCILIATION_COMPLETED",
        details=(
            f"Reconciliation completed: {response.summary.exact_matches} exact matches, "
            f"{response.summary.fuzzy_matches} fuzzy matches, {response.summary.missing_in_2b} missing in 2B, "
            f"Rs. {response.summary.total_at_risk_itc} at-risk ITC."
        )
    )

    return response

def generate_csv_report(response: ReconciliationResponse, session_id: str) -> str:
    """Generates an audit-friendly CSV reconciliation export."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header metadata
    writer.writerow(["VYAPARMITRA GST RECONCILIATION AUDIT REPORT"])
    writer.writerow(["Session ID", session_id])
    writer.writerow(["Generated At (UTC)", datetime.now(timezone.utc).isoformat()])
    writer.writerow(["Total Purchase Invoices", response.summary.total_purchase_invoices])
    writer.writerow(["Total GSTR-2B Invoices", response.summary.total_2b_invoices])
    writer.writerow(["Exact Matches", response.summary.exact_matches])
    writer.writerow(["Fuzzy Matches (Requires Review)", response.summary.fuzzy_matches])
    writer.writerow(["Amount Mismatches", response.summary.amount_mismatches])
    writer.writerow(["Missing In GSTR-2B", response.summary.missing_in_2b])
    writer.writerow(["Total At-Risk ITC (Rs.)", str(response.summary.total_at_risk_itc)])
    writer.writerow(["Net ITC Variance (Rs.)", str(response.summary.total_difference)])
    writer.writerow([])
    writer.writerow([
        "Status",
        "Supplier GSTIN",
        "Purchase Invoice No",
        "GSTR-2B Invoice No",
        "Purchase Taxable",
        "Purchase Total Tax",
        "2B Total Tax",
        "Tax Difference",
        "Confidence Score",
        "Reason",
        "Flagged Rules"
    ])

    for res in response.detailed_results:
        p_inv = res.purchase_invoice
        b_inv = res.matched_2b_invoice

        gstin = (p_inv.supplier_gstin if p_inv else (b_inv.supplier_gstin if b_inv else ""))
        p_num = p_inv.invoice_number if p_inv else ""
        b_num = b_inv.invoice_number if b_inv else ""
        p_taxable = str(p_inv.taxable_value) if p_inv else "0.00"
        p_tax = str(p_inv.total_tax) if p_inv else "0.00"
        b_tax = str(b_inv.total_tax) if b_inv else "0.00"

        writer.writerow([
            res.status.value,
            gstin,
            p_num,
            b_num,
            p_taxable,
            p_tax,
            b_tax,
            str(res.tax_difference),
            f"{res.confidence:.2f}",
            res.reason,
            "; ".join(res.rules_flagged)
        ])

    writer.writerow([])
    writer.writerow([
        "STATUTORY DISCLAIMER: VyaparMitra is an accounting and reconciliation assistance system. "
        "It does not constitute statutory legal advice. All supplier communications require human review and approval."
    ])

    return output.getvalue()

def generate_html_report(response: ReconciliationResponse, session_id: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    """Generates a professional, standalone, printable HTML audit report."""
    meta = metadata or {}
    purchase_fn = meta.get("purchase_filename", "Uploaded Purchase Register")
    gstr2b_fn = meta.get("gstr2b_filename", "Uploaded GSTR-2B")
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    rows_html = ""
    for r in response.detailed_results:
        p_inv = r.purchase_invoice
        b_inv = r.matched_2b_invoice
        gstin = p_inv.supplier_gstin if p_inv else (b_inv.supplier_gstin if b_inv else "-")
        p_no = p_inv.invoice_number if p_inv else "-"
        b_no = b_inv.invoice_number if b_inv else "-"
        p_tax = f"Rs. {p_inv.total_tax:,.2f}" if p_inv else "-"
        b_tax = f"Rs. {b_inv.total_tax:,.2f}" if b_inv else "-"
        diff = f"Rs. {r.tax_difference:,.2f}"

        badge_class = "badge-success" if r.status == MatchStatus.EXACT_MATCH else (
            "badge-warning" if r.status in (MatchStatus.FUZZY_MATCH_REQUIRES_REVIEW, MatchStatus.AMOUNT_MISMATCH) else "badge-danger"
        )

        rows_html += f"""
        <tr>
            <td><span class="status-badge {badge_class}">{r.status.value}</span></td>
            <td><code>{gstin}</code></td>
            <td><strong>{p_no}</strong></td>
            <td><strong>{b_no}</strong></td>
            <td>{p_tax}</td>
            <td>{b_tax}</td>
            <td class="num-diff">{diff}</td>
            <td>{r.reason}</td>
            <td><small>{', '.join(r.rules_flagged) if r.rules_flagged else '-'}</small></td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>VyaparMitra GST Reconciliation Audit Report - {session_id}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 2rem; background: #fff; color: #1e293b; }}
        .header {{ border-bottom: 2px solid #0284c7; padding-bottom: 1rem; margin-bottom: 1.5rem; display: flex; justify-content: space-between; align-items: flex-end; }}
        h1 {{ margin: 0; color: #0f172a; font-size: 1.8rem; }}
        .subtitle {{ color: #64748b; font-size: 0.95rem; margin-top: 0.25rem; }}
        .meta-box {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; margin-bottom: 1.5rem; display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; }}
        .meta-item .label {{ font-size: 0.75rem; text-transform: uppercase; color: #64748b; font-weight: 600; display: block; }}
        .meta-item .val {{ font-size: 1rem; font-weight: 700; color: #0f172a; }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1.5rem; }}
        .metric-card {{ background: #f1f5f9; border-radius: 8px; padding: 1rem; text-align: center; border: 1px solid #cbd5e1; }}
        .metric-card .num {{ font-size: 1.5rem; font-weight: 800; color: #0f172a; margin-top: 0.25rem; }}
        .metric-card.danger .num {{ color: #dc2626; }}
        .metric-card.warning .num {{ color: #d97706; }}
        .metric-card.success .num {{ color: #16a34a; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; font-size: 0.85rem; }}
        th, td {{ border: 1px solid #e2e8f0; padding: 0.6rem 0.75rem; text-align: left; }}
        th {{ background: #f8fafc; font-weight: 700; color: #475569; }}
        .num-diff {{ font-weight: bold; color: #dc2626; }}
        .status-badge {{ font-size: 0.7rem; font-weight: 700; padding: 0.2rem 0.5rem; border-radius: 4px; display: inline-block; }}
        .badge-success {{ background: #dcfce7; color: #15803d; }}
        .badge-warning {{ background: #fef3c7; color: #b45309; }}
        .badge-danger {{ background: #fee2e2; color: #b91c1c; }}
        .disclaimer-box {{ margin-top: 2rem; padding: 1rem; background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; font-size: 0.825rem; color: #92400e; }}
        @media print {{ body {{ margin: 0; }} }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>VyaparMitra (व्यापार मित्र)</h1>
            <div class="subtitle">Autonomous MSME GST Reconciliation & Audit Report</div>
        </div>
        <div style="text-align: right; font-size: 0.85rem; color: #64748b;">
            <div><strong>Session:</strong> {session_id}</div>
            <div><strong>Generated:</strong> {generated_at}</div>
        </div>
    </div>

    <div class="meta-box">
        <div class="meta-item"><span class="label">Purchase Register File</span><span class="val">{purchase_fn}</span></div>
        <div class="meta-item"><span class="label">GSTR-2B Statement File</span><span class="val">{gstr2b_fn}</span></div>
        <div class="meta-item"><span class="label">Total Records Reconciled</span><span class="val">{response.summary.total_purchase_invoices} (Books) / {response.summary.total_2b_invoices} (2B)</span></div>
        <div class="meta-item"><span class="label">Audit Integrity</span><span class="val" style="color: #16a34a;">100% Deterministic Python</span></div>
    </div>

    <div class="metrics-grid">
        <div class="metric-card success"><span class="label">Exact Matches</span><div class="num">{response.summary.exact_matches}</div></div>
        <div class="metric-card warning"><span class="label">Requires Review / Fuzzy</span><div class="num">{response.summary.fuzzy_matches + response.summary.amount_mismatches}</div></div>
        <div class="metric-card danger"><span class="label">Missing in GSTR-2B</span><div class="num">{response.summary.missing_in_2b}</div></div>
        <div class="metric-card danger"><span class="label">Total At-Risk ITC</span><div class="num">Rs. {response.summary.total_at_risk_itc:,.2f}</div></div>
    </div>

    <h3>Detailed Reconciliation Ledger</h3>
    <table>
        <thead>
            <tr>
                <th>Status</th>
                <th>Supplier GSTIN</th>
                <th>Purchase Inv No</th>
                <th>GSTR-2B Inv No</th>
                <th>Purchase GST</th>
                <th>2B GST</th>
                <th>Difference</th>
                <th>Finding / Reasoning</th>
                <th>Rules Flagged</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>

    <div class="disclaimer-box">
        <strong>STATUTORY DISCLAIMER:</strong> VyaparMitra is an accounting and reconciliation assistance system.
        It does not constitute statutory legal advice. All supplier communications require human review and approval.
    </div>
</body>
</html>
"""
    return html
