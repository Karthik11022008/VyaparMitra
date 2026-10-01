import io
import json
import csv
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Union
import pandas as pd

from backend.app.schemas.invoice import PurchaseInvoice, GSTR2BInvoice
from backend.app.tools.gstin_validator import validate_gstin
from backend.app.tools.normalization import normalize_invoice_number, normalize_gstin

# Standard aliases for matching various ERP & government naming conventions
COLUMN_ALIASES: Dict[str, List[str]] = {
    "supplier_gstin": [
        "supplier_gstin", "supplier gstin", "gstin", "vendor_gstin", "vendor gstin",
        "supplier_tin", "gstin/uin of supplier", "gstin/uin", "seller_gstin", "ctin",
        "supplier gstin/uin"
    ],
    "invoice_number": [
        "invoice_number", "invoice no", "invoice_no", "invoice number", "inv_no",
        "inv no", "inv_num", "bill_no", "bill no", "document_number", "document no",
        "doc no", "inum"
    ],
    "invoice_date": [
        "invoice_date", "invoice date", "inv_date", "inv date", "date",
        "bill_date", "bill date", "document_date", "doc date", "idt"
    ],
    "taxable_value": [
        "taxable_value", "taxable amount", "taxable_amount", "taxable value",
        "taxable", "taxable_val", "assessable_value", "total_taxable_value", "txval"
    ],
    "cgst": [
        "cgst", "cgst_amount", "cgst amount", "central_tax", "central tax", "camt"
    ],
    "sgst": [
        "sgst", "sgst_amount", "sgst amount", "state_tax", "state tax", "utgst", "samt"
    ],
    "igst": [
        "igst", "igst_amount", "igst amount", "integrated_tax", "integrated tax", "iamt"
    ],
    "total_value": [
        "total_value", "total amount", "total_amount", "invoice_value",
        "invoice value", "invoice_total", "val", "grand total"
    ],
    "tax_period": [
        "tax_period", "tax period", "period", "return_period", "return period"
    ]
}

def clean_header_name(header: str) -> str:
    """Normalizes header string by lowercasing and trimming punctuation/spaces."""
    h = str(header).strip().lower()
    h = re.sub(r"[\s\-_/\\.]+", " ", h).strip()
    return h

def map_column_headers(raw_headers: List[str]) -> Tuple[Dict[str, str], List[str]]:
    """
    Maps detected column names to canonical schema keys.
    Returns: (canonical_to_raw_mapping, list_of_detected_columns)
    """
    mapping: Dict[str, str] = {}
    detected_cols: List[str] = [str(h).strip() for h in raw_headers if str(h).strip()]

    cleaned_raw_to_original = {clean_header_name(h): h for h in detected_cols}

    for canonical, aliases in COLUMN_ALIASES.items():
        matched_original = None
        for alias in aliases:
            cleaned_alias = clean_header_name(alias)
            if cleaned_alias in cleaned_raw_to_original:
                matched_original = cleaned_raw_to_original[cleaned_alias]
                break
        if matched_original:
            mapping[canonical] = matched_original

    return mapping, detected_cols

def parse_decimal_safe(val: Any, default: Decimal = Decimal("0.00")) -> Decimal:
    """Parses numeric value strictly as Python Decimal, stripping currency symbols and commas."""
    if val is None:
        return default
    s = str(val).strip().replace(",", "").replace("Rs.", "").replace("₹", "")
    if not s or s.lower() in ("nan", "none", "null", "-"):
        return default
    try:
        return round(Decimal(s), 2)
    except (InvalidOperation, ValueError):
        return default

def flatten_gstr2b_json(data: Any) -> List[Dict[str, Any]]:
    """
    Extracts flat invoice records from either:
    1. A list of flat dictionaries
    2. A dictionary with 'data', 'invoices', or government standard 'b2b' structure
    """
    rows: List[Dict[str, Any]] = []

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                rows.append(item)
        return rows

    if isinstance(data, dict):
        # Case A: nested under "data"
        if "data" in data and isinstance(data["data"], (dict, list)):
            return flatten_gstr2b_json(data["data"])

        # Case B: wrapped in "invoices"
        if "invoices" in data and isinstance(data["invoices"], list):
            return data["invoices"]

        # Case C: official GSTR-2B portal structure with "b2b" array
        if "b2b" in data and isinstance(data["b2b"], list):
            for supplier in data["b2b"]:
                ctin = supplier.get("ctin") or supplier.get("supplier_gstin") or ""
                inv_list = supplier.get("inv") or supplier.get("invoices") or []
                for inv in inv_list:
                    inum = inv.get("inum") or inv.get("invoice_number") or ""
                    idt = inv.get("idt") or inv.get("invoice_date") or ""
                    val = inv.get("val") or inv.get("total_value") or 0

                    items = inv.get("items") or []
                    txval_sum = Decimal("0.00")
                    camt_sum = Decimal("0.00")
                    samt_sum = Decimal("0.00")
                    iamt_sum = Decimal("0.00")

                    if items:
                        for itm in items:
                            itm_det = itm.get("itm_det", itm)
                            txval_sum += parse_decimal_safe(itm_det.get("txval", 0))
                            camt_sum += parse_decimal_safe(itm_det.get("camt", 0))
                            samt_sum += parse_decimal_safe(itm_det.get("samt", 0))
                            iamt_sum += parse_decimal_safe(itm_det.get("iamt", 0))
                    else:
                        txval_sum = parse_decimal_safe(inv.get("taxable_value", 0))
                        camt_sum = parse_decimal_safe(inv.get("cgst", 0))
                        samt_sum = parse_decimal_safe(inv.get("sgst", 0))
                        iamt_sum = parse_decimal_safe(inv.get("igst", 0))

                    rows.append({
                        "supplier_gstin": ctin,
                        "invoice_number": inum,
                        "invoice_date": idt,
                        "taxable_value": float(txval_sum),
                        "cgst": float(camt_sum),
                        "sgst": float(samt_sum),
                        "igst": float(iamt_sum),
                        "total_value": float(val),
                        "tax_period": inv.get("tax_period", "")
                    })
            return rows

    return rows

class ParsedDatasetResult:
    def __init__(
        self,
        success: bool,
        detected_format: str,
        row_count: int,
        columns_detected: List[str],
        validation_errors: List[str],
        purchase_invoices: Optional[List[PurchaseInvoice]] = None,
        gstr2b_invoices: Optional[List[GSTR2BInvoice]] = None,
        preview_rows: Optional[List[Dict[str, Any]]] = None,
    ):
        self.success = success
        self.detected_format = detected_format
        self.row_count = row_count
        self.columns_detected = columns_detected
        self.validation_errors = validation_errors
        self.purchase_invoices = purchase_invoices or []
        self.gstr2b_invoices = gstr2b_invoices or []
        self.preview_rows = preview_rows or []

def parse_and_validate_file(
    content_bytes: bytes,
    original_filename: str,
    target_type: str  # "purchase" or "gstr2b"
) -> ParsedDatasetResult:
    """
    Validates and parses uploaded file content (CSV, XLSX, JSON) with content-based sniffing,
    column alias mapping, and statutory data validation.
    """
    validation_errors: List[str] = []
    fname_lower = original_filename.lower()

    if not content_bytes or len(content_bytes) == 0:
        return ParsedDatasetResult(
            success=False,
            detected_format="EMPTY",
            row_count=0,
            columns_detected=[],
            validation_errors=["The uploaded file is empty (0 bytes)."]
        )

    # 1. Format Detection
    detected_format = "UNKNOWN"
    df: Optional[pd.DataFrame] = None

    if content_bytes.startswith(b"PK\x03\x04") or fname_lower.endswith(".xlsx"):
        detected_format = "XLSX"
        try:
            df = pd.read_excel(io.BytesIO(content_bytes), engine="openpyxl")
        except Exception as e:
            return ParsedDatasetResult(
                success=False,
                detected_format="XLSX",
                row_count=0,
                columns_detected=[],
                validation_errors=[f"Failed to parse Excel workbook: {str(e)}"]
            )
    elif fname_lower.endswith(".json") or content_bytes.strip().startswith((b"{", b"[")):
        detected_format = "JSON"
        try:
            json_text = content_bytes.decode("utf-8-sig", errors="replace")
            parsed_json = json.loads(json_text)
            flat_rows = flatten_gstr2b_json(parsed_json)
            if not flat_rows:
                return ParsedDatasetResult(
                    success=False,
                    detected_format="JSON",
                    row_count=0,
                    columns_detected=[],
                    validation_errors=["JSON structure contained no invoice records or unrecognized schema."]
                )
            df = pd.DataFrame(flat_rows)
        except Exception as e:
            return ParsedDatasetResult(
                success=False,
                detected_format="JSON",
                row_count=0,
                columns_detected=[],
                validation_errors=[f"Malformed JSON content: {str(e)}"]
            )
    else:
        # Default to CSV / Text
        detected_format = "CSV"
        try:
            csv_text = content_bytes.decode("utf-8-sig", errors="replace")
            # Filter comments
            lines = [line for line in csv_text.splitlines() if not line.strip().startswith("#")]
            if not lines:
                return ParsedDatasetResult(
                    success=False,
                    detected_format="CSV",
                    row_count=0,
                    columns_detected=[],
                    validation_errors=["CSV contains no data rows."]
                )
            df = pd.read_csv(io.StringIO("\n".join(lines)))
        except Exception as e:
            return ParsedDatasetResult(
                success=False,
                detected_format="CSV",
                row_count=0,
                columns_detected=[],
                validation_errors=[f"Malformed CSV content: {str(e)}"]
            )

    if df is None or df.empty:
        return ParsedDatasetResult(
            success=False,
            detected_format=detected_format,
            row_count=0,
            columns_detected=[],
            validation_errors=["File contains header but zero data records."]
        )

    # 2. Header Mapping
    raw_headers = list(df.columns)
    col_map, detected_cols = map_column_headers(raw_headers)

    # 3. Mandatory Column Verification
    required_cols = ["supplier_gstin", "invoice_number", "taxable_value"]
    missing_required = [req for req in required_cols if req not in col_map]
    if missing_required:
        return ParsedDatasetResult(
            success=False,
            detected_format=detected_format,
            row_count=len(df),
            columns_detected=detected_cols,
            validation_errors=[
                f"Missing required statutory columns: {', '.join(missing_required)}. "
                f"Detected columns: [{', '.join(detected_cols)}]. "
                "Ensure supplier GSTIN, invoice number, and taxable value are present."
            ]
        )

    # 4. Row Parsing & Validation
    purchase_list: List[PurchaseInvoice] = []
    gstr2b_list: List[GSTR2BInvoice] = []
    preview_rows: List[Dict[str, Any]] = []

    seen_invoices = set()

    for idx, row in df.iterrows():
        row_num = idx + 2  # 1-indexed accounting row considering header

        gstin_raw = str(row[col_map["supplier_gstin"]]).strip()
        inv_no_raw = str(row[col_map["invoice_number"]]).strip()
        date_raw = str(row[col_map["invoice_date"]]).strip() if "invoice_date" in col_map else ""
        period_raw = str(row[col_map["tax_period"]]).strip() if "tax_period" in col_map else ""

        if not gstin_raw or gstin_raw.lower() in ("nan", "none", ""):
            validation_errors.append(f"Row {row_num}: Supplier GSTIN is missing.")
            continue
        if not inv_no_raw or inv_no_raw.lower() in ("nan", "none", ""):
            validation_errors.append(f"Row {row_num}: Invoice Number is missing.")
            continue

        # GSTIN Validation check
        gstin_val = validate_gstin(gstin_raw)
        if not gstin_val.is_valid:
            validation_errors.append(f"Row {row_num}: Invalid GSTIN '{gstin_raw}' ({', '.join(gstin_val.errors)}).")

        taxable_val = parse_decimal_safe(row[col_map["taxable_value"]])
        if taxable_val < Decimal("0.00"):
            validation_errors.append(f"Row {row_num}: Negative taxable value ({taxable_val}) is not permitted.")

        cgst_val = parse_decimal_safe(row[col_map["cgst"]]) if "cgst" in col_map else Decimal("0.00")
        sgst_val = parse_decimal_safe(row[col_map["sgst"]]) if "sgst" in col_map else Decimal("0.00")
        igst_val = parse_decimal_safe(row[col_map["igst"]]) if "igst" in col_map else Decimal("0.00")
        total_val = parse_decimal_safe(row[col_map["total_value"]]) if "total_value" in col_map else (taxable_val + cgst_val + sgst_val + igst_val)

        # Duplicate check within file
        dedup_key = (normalize_gstin(gstin_raw), normalize_invoice_number(inv_no_raw))
        if dedup_key in seen_invoices:
            validation_errors.append(f"Row {row_num}: Duplicate invoice entry detected ({gstin_raw} / {inv_no_raw}).")
        seen_invoices.add(dedup_key)

        preview_data = {
            "supplier_gstin": gstin_raw,
            "invoice_number": inv_no_raw,
            "invoice_date": date_raw,
            "taxable_value": str(taxable_val),
            "cgst": str(cgst_val),
            "sgst": str(sgst_val),
            "igst": str(igst_val),
            "total_tax": str(cgst_val + sgst_val + igst_val),
            "total_value": str(total_val)
        }

        if len(preview_rows) < 5:
            preview_rows.append(preview_data)

        if target_type == "purchase":
            purchase_list.append(
                PurchaseInvoice(
                    supplier_gstin=gstin_raw,
                    invoice_number=inv_no_raw,
                    invoice_date=date_raw,
                    taxable_value=taxable_val,
                    cgst=cgst_val,
                    sgst=sgst_val,
                    igst=igst_val,
                    total_value=total_val,
                    tax_period=period_raw
                )
            )
        else:
            gstr2b_list.append(
                GSTR2BInvoice(
                    supplier_gstin=gstin_raw,
                    invoice_number=inv_no_raw,
                    invoice_date=date_raw,
                    taxable_value=taxable_val,
                    cgst=cgst_val,
                    sgst=sgst_val,
                    igst=igst_val,
                    tax_period=period_raw
                )
            )

    # Determine if valid: if critical errors occurred (e.g. 0 parsed invoices or all invalid)
    has_invoices = (len(purchase_list) > 0) if target_type == "purchase" else (len(gstr2b_list) > 0)
    is_success = has_invoices

    return ParsedDatasetResult(
        success=is_success,
        detected_format=detected_format,
        row_count=len(purchase_list) if target_type == "purchase" else len(gstr2b_list),
        columns_detected=detected_cols,
        validation_errors=validation_errors[:10],  # Return up to 10 actionable errors
        purchase_invoices=purchase_list,
        gstr2b_invoices=gstr2b_list,
        preview_rows=preview_rows
    )
