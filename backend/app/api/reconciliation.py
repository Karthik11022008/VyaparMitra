import uuid
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Response
from pydantic import BaseModel

from backend.app.config import settings
from backend.app.schemas.invoice import ReconciliationResponse
from backend.app.services.reconciliation_service import (
    reconcile_demo_dataset,
    reconcile_session,
    get_session_cache,
    generate_csv_report,
    generate_html_report,
    restore_session_from_db,
)
from backend.app.services.file_parser import parse_and_validate_file
from backend.app.database import (
    save_or_update_session,
    get_reconciliation_session,
    log_audit_event,
    get_audit_events,
    get_reconciliation_history,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reconciliation", tags=["Reconciliation"])

class RunReconciliationRequest(BaseModel):
    session_id: str

class UploadResponse(BaseModel):
    session_id: str
    filename: str
    detected_format: str
    row_count: int
    columns_detected: List[str]
    validation_status: str
    validation_errors: List[str]
    preview_rows: List[Dict[str, Any]]

def sanitize_filename(filename: str) -> str:
    """Strips directory traversal sequences and unsafe characters."""
    base_name = Path(filename).name
    # Keep alphanumeric, dot, underscore, dash
    clean = re.sub(r"[^a-zA-Z0-9._-]", "_", base_name)
    return clean or "uploaded_file"

@router.post("/demo", response_model=ReconciliationResponse)
async def run_demo_reconciliation():
    """
    Executes deterministic GST reconciliation on the verified synthetic demo dataset.
    Identifies exact matches, fuzzy matches, amount variances, missing invoices, and statutory flags.
    """
    try:
        response = reconcile_demo_dataset()
        return response
    except Exception as e:
        logger.error(f"Error during reconciliation run: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while executing the deterministic reconciliation engine."
        )

@router.post("/upload/purchase-register", response_model=UploadResponse)
async def upload_purchase_register(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None)
):
    """
    Ingests and validates a Purchase Register file (CSV or XLSX).
    Enforces maximum file size, header alias normalization, and GSTIN/Decimal validation.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided in upload.")

    safe_name = sanitize_filename(file.filename)
    active_session_id = session_id or f"sess-{uuid.uuid4().hex[:8]}"

    # Read content with size guard
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_BYTES // (1024*1024)} MB."
        )

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="The uploaded file is empty (0 bytes).")

    # Content-based format checking and parsing
    parse_result = parse_and_validate_file(content, safe_name, target_type="purchase")

    # Secure file save
    target_path = settings.UPLOAD_DIR / f"{active_session_id}_purchase_{safe_name}"
    try:
        with open(target_path, "wb") as f:
            f.write(content)
    except Exception as e:
        logger.error(f"Failed to persist upload file securely: {e}")

    # Update in-memory session cache
    cache = get_session_cache(active_session_id)
    cache["purchase_invoices"] = parse_result.purchase_invoices
    cache["purchase_filename"] = safe_name

    # Persist in DB and log audit event
    val_status = "VALID" if parse_result.success else "INVALID"
    save_or_update_session(
        session_id=active_session_id,
        status="PURCHASE_UPLOADED" if parse_result.success else "PURCHASE_INVALID",
        purchase_filename=safe_name,
        purchase_row_count=parse_result.row_count,
        purchase_filepath=str(target_path.name)
    )

    log_audit_event(
        session_id=active_session_id,
        event_type="FILE_UPLOADED",
        details=f"Uploaded Purchase Register '{safe_name}' ({parse_result.row_count} records detected, format: {parse_result.detected_format})."
    )
    log_audit_event(
        session_id=active_session_id,
        event_type="FILE_VALIDATED",
        details=f"Validation status: {val_status}. Errors: {len(parse_result.validation_errors)}."
    )

    return UploadResponse(
        session_id=active_session_id,
        filename=safe_name,
        detected_format=parse_result.detected_format,
        row_count=parse_result.row_count,
        columns_detected=parse_result.columns_detected,
        validation_status=val_status,
        validation_errors=parse_result.validation_errors,
        preview_rows=parse_result.preview_rows
    )

@router.post("/upload/gstr2b", response_model=UploadResponse)
async def upload_gstr2b(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None)
):
    """
    Ingests and validates a GSTR-2B file (CSV, JSON, or XLSX).
    Supports official JSON portal schemas and flexible column aliases.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided in upload.")

    safe_name = sanitize_filename(file.filename)
    active_session_id = session_id or f"sess-{uuid.uuid4().hex[:8]}"

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_BYTES // (1024*1024)} MB."
        )

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="The uploaded file is empty (0 bytes).")

    parse_result = parse_and_validate_file(content, safe_name, target_type="gstr2b")

    target_path = settings.UPLOAD_DIR / f"{active_session_id}_gstr2b_{safe_name}"
    try:
        with open(target_path, "wb") as f:
            f.write(content)
    except Exception as e:
        logger.error(f"Failed to persist upload file securely: {e}")

    cache = get_session_cache(active_session_id)
    cache["gstr2b_invoices"] = parse_result.gstr2b_invoices
    cache["gstr2b_filename"] = safe_name

    val_status = "VALID" if parse_result.success else "INVALID"
    save_or_update_session(
        session_id=active_session_id,
        status="GSTR2B_UPLOADED" if parse_result.success else "GSTR2B_INVALID",
        gstr2b_filename=safe_name,
        gstr2b_row_count=parse_result.row_count,
        gstr2b_filepath=str(target_path.name)
    )

    log_audit_event(
        session_id=active_session_id,
        event_type="FILE_UPLOADED",
        details=f"Uploaded GSTR-2B '{safe_name}' ({parse_result.row_count} records detected, format: {parse_result.detected_format})."
    )
    log_audit_event(
        session_id=active_session_id,
        event_type="FILE_VALIDATED",
        details=f"Validation status: {val_status}. Errors: {len(parse_result.validation_errors)}."
    )

    return UploadResponse(
        session_id=active_session_id,
        filename=safe_name,
        detected_format=parse_result.detected_format,
        row_count=parse_result.row_count,
        columns_detected=parse_result.columns_detected,
        validation_status=val_status,
        validation_errors=parse_result.validation_errors,
        preview_rows=parse_result.preview_rows
    )

@router.post("/run", response_model=ReconciliationResponse)
async def run_uploaded_reconciliation(req: RunReconciliationRequest):
    """
    Executes deterministic reconciliation between the uploaded Purchase Register and GSTR-2B datasets
    associated with the provided session ID.
    """
    try:
        return reconcile_session(req.session_id)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error executing uploaded reconciliation for session {req.session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while executing reconciliation for the uploaded dataset."
        )

@router.get("/history")
async def list_reconciliation_history(limit: int = 50):
    """Retrieves previous reconciliation sessions for recovery and audit examination."""
    sessions = get_reconciliation_history(limit=limit)
    return {
        "count": len(sessions),
        "sessions": sessions
    }

@router.get("/session/{session_id}")
async def get_session_info(session_id: str):
    """Retrieves session metadata, filenames, row counts, and current status."""
    info = get_reconciliation_session(session_id)
    if not info:
        raise HTTPException(status_code=404, detail="Reconciliation session not found.")
    return info

@router.get("/session/{session_id}/results", response_model=ReconciliationResponse)
async def get_session_reconciliation_results(session_id: str):
    """Retrieves full reconciliation results and supplier summaries, restoring from SQLite if needed."""
    cache = get_session_cache(session_id)
    response = cache.get("reconciliation_response")
    if not response:
        response = restore_session_from_db(session_id)
    if not response:
        raise HTTPException(
            status_code=404,
            detail="Reconciliation has not been executed or saved for this session."
        )
    return response

@router.get("/session/{session_id}/suppliers")
async def get_session_supplier_summaries(session_id: str):
    """Retrieves deterministic supplier-wise risk and invoice breakdown for the session."""
    cache = get_session_cache(session_id)
    response = cache.get("reconciliation_response")
    if not response:
        response = restore_session_from_db(session_id)
    if not response:
        raise HTTPException(
            status_code=404,
            detail="Reconciliation has not been executed or saved for this session."
        )
    return {
        "session_id": session_id,
        "supplier_count": len(response.supplier_summaries),
        "suppliers": [s.model_dump(mode="json") for s in response.supplier_summaries]
    }

@router.get("/export/{session_id}/csv")
async def export_reconciliation_csv(session_id: str):
    """Exports reconciliation results as an audit-friendly CSV document."""
    cache = get_session_cache(session_id)
    response = cache.get("reconciliation_response")
    if not response:
        response = restore_session_from_db(session_id)
    if not response:
        try:
            response = reconcile_session(session_id)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Reconciliation has not been executed for this session yet."
            )

    csv_data = generate_csv_report(response, session_id)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="VyaparMitra_Recon_{session_id}.csv"'}
    )

@router.get("/export/{session_id}/html")
async def export_reconciliation_html(session_id: str):
    """Exports reconciliation results as a professional, printable HTML audit report."""
    cache = get_session_cache(session_id)
    response = cache.get("reconciliation_response")
    if not response:
        response = restore_session_from_db(session_id)
    if not response:
        try:
            response = reconcile_session(session_id)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Reconciliation has not been executed for this session yet."
            )

    metadata = {
        "purchase_filename": cache.get("purchase_filename"),
        "gstr2b_filename": cache.get("gstr2b_filename"),
    }
    html_data = generate_html_report(response, session_id, metadata)
    return Response(
        content=html_data,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="VyaparMitra_Report_{session_id}.html"'}
    )

@router.get("/audit/{session_id}")
async def get_session_audit_trail(session_id: str):
    """Returns the immutable audit log events recorded for this reconciliation session."""
    events = get_audit_events(session_id)
    return {
        "session_id": session_id,
        "event_count": len(events),
        "events": events
    }
