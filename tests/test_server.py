"""
Integration tests for the Web API Server & Endpoints.
"""

import os
import pytest
from fastapi.testclient import TestClient
from bank_forensics.server import app

client = TestClient(app)


def test_index_route():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Bank Statement Underwriting Console" in response.text


def test_sample_pnb_route():
    response = client.get("/api/sample/pnb")
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["bank_code"] == "PNB"
    assert data["verdict"]["decision"] == "REJECT"
    assert data["ledger_audit"]["was_reverse_chronological"] is True
    assert data["forensics"]["wallet_rotation"]["flag_raised"] is True


def test_sample_hdfc_route():
    response = client.get("/api/sample/hdfc")
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["bank_code"] == "HDFC"
    assert data["verdict"]["decision"] == "APPROVE"
    assert data["verdict"]["risk_grade"] == "A1_PRIME"


def test_sample_sbi_route():
    response = client.get("/api/sample/sbi")
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["bank_code"] == "SBI"
    assert data["verdict"]["decision"] == "MANUAL_REVIEW"


def test_upload_pdf_analyze_endpoint():
    pdf_path = "samples/hdfc_statement_prime_salaried.pdf"
    assert os.path.exists(pdf_path)

    with open(pdf_path, "rb") as f:
        response = client.post(
            "/api/analyze",
            files={"file": ("my_statement.pdf", f, "application/pdf")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["customer_name"] == "ANANYA IYER"
    assert data["verdict"]["decision"] == "APPROVE"
    assert len(data["transactions"]) > 0
    # Verify visual tags are present in uploaded transaction output
    first_txn = data["transactions"][0]
    assert "tags" in first_txn
    assert "is_salary" in first_txn["tags"]
