import re

def normalize_invoice_number(raw_inv: str) -> str:
    """
    Deterministically normalizes an invoice number for comparison:
    - Converts to uppercase
    - Trims outer whitespace
    - Strips harmless punctuation separators: spaces, hyphens, slashes, backslashes, underscores, dots
    - Retains letters and numbers
    
    The original raw invoice number must always be preserved in the underlying record.
    """
    if not raw_inv:
        return ""
    # Convert to uppercase and strip
    inv = str(raw_inv).strip().upper()
    # Remove separators: space, hyphens, slashes, dots, underscores
    normalized = re.sub(r'[\s\-_/\\.]', '', inv)
    return normalized

def normalize_gstin(raw_gstin: str) -> str:
    """
    Normalizes a GSTIN:
    - Converts to uppercase
    - Strips whitespace
    """
    if not raw_gstin:
        return ""
    return str(raw_gstin).strip().upper()
