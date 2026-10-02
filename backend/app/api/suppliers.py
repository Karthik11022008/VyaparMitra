from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
import logging

from backend.app.schemas.supplier_risk import SupplierRiskProfile, SupplierHistoryProfile
from backend.app.services.supplier_risk_service import (
    build_all_supplier_risk_profiles,
    build_supplier_risk_profile,
    get_supplier_history_profile,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/suppliers", tags=["Suppliers"])

@router.get("/{session_id}/risk", response_model=List[SupplierRiskProfile])
async def get_all_supplier_risks(session_id: str):
    """
    Returns deterministic risk profiles for all counterparties in the session,
    ranked by risk score (0-100) and at-risk ITC exposure.
    """
    try:
        profiles = build_all_supplier_risk_profiles(session_id)
        return profiles
    except Exception as e:
        logger.error(f"Error computing supplier risks for session {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to compute supplier risk intelligence profiles."
        )

@router.get("/{session_id}/{gstin}/profile", response_model=SupplierRiskProfile)
async def get_supplier_risk_profile_endpoint(session_id: str, gstin: str):
    """
    Returns a single supplier's deterministic risk score, breakdown components,
    active risk signals, and affected invoices.
    """
    try:
        profile = build_supplier_risk_profile(session_id, gstin)
        if not profile:
            raise HTTPException(
                status_code=404,
                detail=f"Supplier '{gstin}' was not found in session '{session_id}'."
            )
        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching profile for supplier {gstin}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve supplier risk profile."
        )

@router.get("/{session_id}/{gstin}/history", response_model=SupplierHistoryProfile)
async def get_supplier_history_endpoint(session_id: str, gstin: str):
    """
    Queries multi-session database history for the specified supplier GSTIN,
    evaluating recurring non-compliance patterns and historical filing trends.
    """
    try:
        history = get_supplier_history_profile(gstin)
        return history
    except Exception as e:
        logger.error(f"Error fetching history for supplier {gstin}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve supplier historical profile."
        )
