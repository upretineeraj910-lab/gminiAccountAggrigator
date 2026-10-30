"""
Unit tests for Reverse Chronology Fix and Mathematical Ledger Verification.
"""

from datetime import date
import pytest
from bank_forensics.models import StatementMetadata, Transaction
from bank_forensics.normalizer import TransactionNormalizer


def test_reverse_chronology_fix_and_ledger_verification():
    meta = StatementMetadata(
        bank_code="PNB",
        bank_name="Punjab National Bank",
        opening_balance=10000.0,
    )
    normalizer = TransactionNormalizer(meta)

    # Statement presented in REVERSE order (newest first)
    raw_rows = [
        {"date_str": "05/10/2026", "narration": "ATM WITHDRAWAL", "debit_str": "2000.00", "credit_str": "0.00", "balance_str": "18000.00"},
        {"date_str": "03/10/2026", "narration": "TRANSFER OUT", "debit_str": "5000.00", "credit_str": "0.00", "balance_str": "20000.00"},
        {"date_str": "01/10/2026", "narration": "SALARY CREDIT", "debit_str": "0.00", "credit_str": "15000.00", "balance_str": "25000.00"},
    ]

    txns, audit = normalizer.normalize(raw_rows)

    assert audit.was_reverse_chronological is True
    assert audit.is_verified is True
    assert len(txns) == 3

    # Check chronological ordering
    assert txns[0].date == date(2026, 10, 1)
    assert txns[0].credit == 15000.0
    assert txns[0].balance == 25000.0

    assert txns[1].date == date(2026, 10, 3)
    assert txns[1].debit == 5000.0
    assert txns[1].balance == 20000.0

    assert txns[2].date == date(2026, 10, 5)
    assert txns[2].debit == 2000.0
    assert txns[2].balance == 18000.0

    assert audit.discrepancy_count == 0
    assert audit.tampering_suspected is False


def test_tampered_ledger_detection():
    meta = StatementMetadata(
        bank_code="SBI",
        opening_balance=10000.0,
    )
    normalizer = TransactionNormalizer(meta)

    # Row 2 balance is tampered (reported 50000 instead of 8000)
    raw_rows = [
        {"date_str": "01/10/2026", "narration": "OPENING BALANCE", "debit_str": "0.00", "credit_str": "0.00", "balance_str": "10000.00"},
        {"date_str": "05/10/2026", "narration": "STORE SPEND", "debit_str": "2000.00", "credit_str": "0.00", "balance_str": "50000.00"},
    ]

    txns, audit = normalizer.normalize(raw_rows)

    assert audit.is_verified is False
    assert audit.tampering_suspected is True
    assert audit.discrepancy_count == 1
    assert audit.discrepancies[0]["expected_balance"] == 8000.0
    assert audit.discrepancies[0]["reported_balance"] == 50000.0
    assert audit.discrepancies[0]["discrepancy"] == 42000.0
