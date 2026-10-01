import io
import json
import pytest
from fastapi.testclient import TestClient
import pandas as pd

from backend.app.main import app
from backend.app.config import settings

client = TestClient(app)

SAMPLE_PURCHASE_CSV = """# Comment line
Supplier GSTIN,Invoice No,Invoice Date,Taxable Amount,CGST,SGST,IGST,Total Amount
27AAPFU0939F1ZV,INV-001,2026-04-10,10000.00,900.00,900.00,0.00,11800.00
06AAACB1234F1ZD,INV-002,2026-04-12,25000.00,0.00,0.00,4500.00,29500.00
"""

SAMPLE_GSTR2B_CSV = """supplier_gstin,invoice_number,invoice_date,taxable_value,cgst,sgst,igst
27AAPFU0939F1ZV,INV-001,2026-04-10,10000.00,900.00,900.00,0.00
06AAACB1234F1ZD,INV-002,2026-04-12,25000.00,0.00,0.00,4500.00
"""

SAMPLE_GSTR2B_JSON = {
    "data": {
        "b2b": [
            {
                "ctin": "27AAPFU0939F1ZV",
                "inv": [
                    {
                        "inum": "INV-001",
                        "idt": "10-04-2026",
                        "val": 11800.00,
                        "items": [
                            {"itm_det": {"txval": 10000.00, "camt": 900.00, "samt": 900.00, "iamt": 0.00}}
                        ]
                    }
                ]
            }
        ]
    }
}

def test_upload_purchase_register_csv():
    files = {"file": ("my_purchase_book.csv", SAMPLE_PURCHASE_CSV.encode("utf-8"), "text/csv")}
    response = client.post("/api/reconciliation/upload/purchase-register", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"].startswith("sess-")
    assert data["detected_format"] == "CSV"
    assert data["row_count"] == 2
    assert data["validation_status"] == "VALID"
    assert len(data["validation_errors"]) == 0
    assert len(data["preview_rows"]) == 2

def test_upload_purchase_register_xlsx():
    # Build Excel bytes in memory using pandas
    df = pd.DataFrame([
        {
            "Supplier GSTIN": "27AAPFU0939F1ZV",
            "Invoice No": "INV-XLSX-1",
            "Invoice Date": "2026-04-15",
            "Taxable Value": 15000.00,
            "CGST": 1350.00,
            "SGST": 1350.00,
            "IGST": 0.00
        }
    ])
    excel_buffer = io.BytesIO()
    df.to_excel(excel_buffer, index=False, engine="openpyxl")
    excel_bytes = excel_buffer.getvalue()

    files = {"file": ("vendor_invoices.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    response = client.post("/api/reconciliation/upload/purchase-register", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["detected_format"] == "XLSX"
    assert data["row_count"] == 1
    assert data["validation_status"] == "VALID"

def test_upload_gstr2b_csv():
    files = {"file": ("gstr2b_april.csv", SAMPLE_GSTR2B_CSV.encode("utf-8"), "text/csv")}
    response = client.post("/api/reconciliation/upload/gstr2b", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["detected_format"] == "CSV"
    assert data["row_count"] == 2
    assert data["validation_status"] == "VALID"

def test_upload_gstr2b_json():
    json_bytes = json.dumps(SAMPLE_GSTR2B_JSON).encode("utf-8")
    files = {"file": ("gstr2b_portal.json", json_bytes, "application/json")}
    response = client.post("/api/reconciliation/upload/gstr2b", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["detected_format"] == "JSON"
    assert data["row_count"] == 1
    assert data["validation_status"] == "VALID"

def test_empty_file_upload_rejected():
    files = {"file": ("empty.csv", b"", "text/csv")}
    res = client.post("/api/reconciliation/upload/purchase-register", files=files)
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()

def test_missing_required_columns_validation():
    invalid_csv = "Vendor Name,Amount,Date\nSupplier Inc,5000,2026-04-01\n"
    files = {"file": ("invalid_columns.csv", invalid_csv.encode("utf-8"), "text/csv")}
    res = client.post("/api/reconciliation/upload/purchase-register", files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["validation_status"] == "INVALID"
    assert any("Missing required statutory columns" in err for err in data["validation_errors"])

def test_invalid_gstin_flagged():
    bad_gstin_csv = "supplier_gstin,invoice_number,taxable_value\nINVALID_GSTIN_123,INV-999,1000.00\n"
    files = {"file": ("bad_gstin.csv", bad_gstin_csv.encode("utf-8"), "text/csv")}
    res = client.post("/api/reconciliation/upload/purchase-register", files=files)
    assert res.status_code == 200
    data = res.json()
    assert any("Invalid GSTIN" in err for err in data["validation_errors"])

def test_filename_sanitization_and_path_traversal():
    traversal_filename = "../../../../../etc/passwd"
    files = {"file": (traversal_filename, SAMPLE_PURCHASE_CSV.encode("utf-8"), "text/csv")}
    res = client.post("/api/reconciliation/upload/purchase-register", files=files)
    assert res.status_code == 200
    data = res.json()
    # Ensure sanitized filename contains no directory traversal slashes
    assert "/" not in data["filename"]
    assert "\\" not in data["filename"]
    assert ".." not in data["filename"]

def test_file_size_limit_protection(monkeypatch):
    # Temporarily set max size to 100 bytes for testing
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 100)
    big_content = b"x" * 200
    files = {"file": ("oversized.csv", big_content, "text/csv")}
    res = client.post("/api/reconciliation/upload/purchase-register", files=files)
    assert res.status_code == 413
