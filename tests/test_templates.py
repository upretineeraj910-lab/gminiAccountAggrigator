"""
Unit tests for Multi-Bank Template Engine, Auto-Detection, and Metadata Parsing.
"""

from datetime import date
import pytest
from bank_forensics.templates import (
    BankTemplateEngine,
    PNBTemplate,
    SBITemplate,
    HDFCTemplate,
    ICICITemplate,
    AxisTemplate,
    CanaraTemplate,
    clean_amount,
    parse_indian_date,
)


def test_bank_auto_detection_by_ifsc():
    assert BankTemplateEngine.detect_bank("IFSC Code: PUNB0145000").bank_code == "PNB"
    assert BankTemplateEngine.detect_bank("IFSC Code: SBIN0004567").bank_code == "SBI"
    assert BankTemplateEngine.detect_bank("IFSC Code: HDFC0000123").bank_code == "HDFC"
    assert BankTemplateEngine.detect_bank("IFSC Code: ICIC0001234").bank_code == "ICICI"
    assert BankTemplateEngine.detect_bank("IFSC Code: UTIB0000005").bank_code == "AXIS"
    assert BankTemplateEngine.detect_bank("IFSC Code: CNRB0001001").bank_code == "CANARA"


def test_bank_auto_detection_by_header_text():
    assert BankTemplateEngine.detect_bank("PUNJAB NATIONAL BANK E-STATEMENT").bank_code == "PNB"
    assert BankTemplateEngine.detect_bank("STATE BANK OF INDIA ONLINESBI").bank_code == "SBI"
    assert BankTemplateEngine.detect_bank("HDFC BANK LIMITED ACCOUNT STATEMENT").bank_code == "HDFC"
    assert BankTemplateEngine.detect_bank("ICICI BANK STATEMENT OF TRANSACTIONS").bank_code == "ICICI"
    assert BankTemplateEngine.detect_bank("AXIS BANK ACCOUNT STATEMENT").bank_code == "AXIS"
    assert BankTemplateEngine.detect_bank("CANARA BANK STATEMENT").bank_code == "CANARA"


def test_metadata_extraction():
    header_sample = """
    PUNJAB NATIONAL BANK
    PNB ONE E-STATEMENT
    Customer Name: VIKRAM SHARMA IFSC Code: PUNB0014500
    Account Number: 0145000100234567 Statement Period: 01/10/2026 To 25/10/2026
    Account Type: SAVINGS Opening Balance: INR 35,000.00
    Branch Name: CONNAUGHT PLACE NEW DELHI Closing Balance: INR 43,194.37
    """
    meta = BankTemplateEngine.extract_metadata(header_sample)
    assert meta.bank_code == "PNB"
    assert meta.customer_name == "VIKRAM SHARMA"
    assert meta.account_number == "0145000100234567"
    assert meta.ifsc_code == "PUNB0014500"
    assert "CONNAUGHT PLACE" in meta.branch
    assert meta.account_type == "SAVINGS"
    assert meta.start_date == date(2026, 10, 1)
    assert meta.end_date == date(2026, 10, 25)
    assert meta.opening_balance == 35000.00
    assert meta.closing_balance == 43194.37


def test_date_parsing():
    assert parse_indian_date("01/10/2026") == date(2026, 10, 1)
    assert parse_indian_date("25-10-2026") == date(2026, 10, 25)
    assert parse_indian_date("15 Oct 2026") == date(2026, 10, 15)
    assert parse_indian_date("15-Oct-2026") == date(2026, 10, 15)
    assert parse_indian_date("2026-10-31") == date(2026, 10, 31)
    assert parse_indian_date("") is None
    assert parse_indian_date("invalid") is None


def test_clean_amount():
    assert clean_amount("1,45,000.00") == 145000.0
    assert clean_amount("₹ 50,000.50 Cr") == 50000.5
    assert clean_amount("295.00 Dr") == 295.0
    assert clean_amount("INR 12,345.67") == 12345.67
    assert clean_amount("-") == 0.0
    assert clean_amount(None) == 0.0
    assert clean_amount(100) == 100.0


def test_column_mapping():
    header = ["Txn Date", "Narration", "Chq No", "Debit", "Credit", "Balance"]
    mapped = BankTemplateEngine.map_columns(header)
    assert mapped["date"] == 0
    assert mapped["narration"] == 1
    assert mapped["chq_ref"] == 2
    assert mapped["debit"] == 3
    assert mapped["credit"] == 4
    assert mapped["balance"] == 5
