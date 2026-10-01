import re
from typing import Optional, List
from pydantic import BaseModel

VALID_STATE_CODES = {
    f"{i:02d}" for i in range(1, 39)
}.union({"97", "99"})

GSTIN_PATTERN = re.compile(
    r"^([0-9]{2})([A-Z]{5}[0-9]{4}[A-Z]{1})([1-9A-Z]{1})(Z)([0-9A-Z]{1})$"
)

CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

def compute_gstin_checksum(gstin_first_14: str) -> str:
    """
    Computes official GSTIN Luhn Mod 36 checksum character for first 14 chars.
    """
    factor = 1
    total = 0
    for char in gstin_first_14.upper():
        if char not in CHARS:
            return ""
        code_point = CHARS.index(char)
        product = code_point * factor
        factor = 2 if factor == 1 else 1
        quotient = product // 36
        remainder = product % 36
        total += quotient + remainder
    remainder = total % 36
    check_code_point = (36 - remainder) % 36
    return CHARS[check_code_point]

class GSTINValidationResult(BaseModel):
    is_valid: bool
    gstin: str
    state_code: Optional[str] = None
    pan: Optional[str] = None
    entity_code: Optional[str] = None
    checksum_valid: bool = False
    errors: List[str] = []

def validate_gstin(raw_gstin: str) -> GSTINValidationResult:
    """
    Deterministically validates a 15-character statutory Indian GSTIN.
    """
    errors: List[str] = []
    if not raw_gstin:
        return GSTINValidationResult(is_valid=False, gstin="", errors=["GSTIN cannot be empty"])
    
    gstin = str(raw_gstin).strip().upper()
    
    if len(gstin) != 15:
        errors.append(f"Invalid GSTIN length ({len(gstin)} characters). Must be exactly 15 characters.")
        return GSTINValidationResult(is_valid=False, gstin=gstin, errors=errors)
    
    match = GSTIN_PATTERN.match(gstin)
    if not match:
        errors.append("GSTIN does not conform to standard format (2-digit state + 10-char PAN + entity + Z + check-digit).")
        return GSTINValidationResult(is_valid=False, gstin=gstin, errors=errors)
    
    state_code, pan, entity_code, z_char, check_digit = match.groups()
    
    if state_code not in VALID_STATE_CODES:
        errors.append(f"Invalid state code '{state_code}'. Must be between 01-38, 97, or 99.")
    
    # Checksum validation
    expected_check = compute_gstin_checksum(gstin[:14])
    checksum_valid = (expected_check == check_digit)
    if not checksum_valid:
        errors.append(f"Invalid checksum digit '{check_digit}'. Expected '{expected_check}'.")
    
    is_valid = len(errors) == 0
    return GSTINValidationResult(
        is_valid=is_valid,
        gstin=gstin,
        state_code=state_code,
        pan=pan,
        entity_code=entity_code,
        checksum_valid=checksum_valid,
        errors=errors
    )
