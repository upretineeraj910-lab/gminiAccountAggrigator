"""
Unit tests for Forensic Detection Rules:
- Credit card & wallet rotation loops within 24-72 hours
- Speculative trading, crypto, and high-frequency gambling
- Inward vs Outward cheque bounces and penalty fee mapping
- EMI missed mandate and broken partial loan recoveries
"""

from datetime import date
import pytest
from bank_forensics.forensic_rules import ForensicRulesEngine
from bank_forensics.models import (
    Transaction,
    TransactionCategory,
    VisualHighlightTags,
)


def test_credit_card_wallet_rotation_detection():
    # User adds money from wallet to bank, exits to credit card bill pay within 48h
    txns = [
        Transaction(
            txn_id="TXN_001",
            date=date(2026, 10, 2),
            narration="UPI/CR/MOBIKWIK PPIW WALLET CASH OUT",
            credit=50000.0,
            debit=0.0,
            balance=60000.0,
        ),
        Transaction(
            txn_id="TXN_002",
            date=date(2026, 10, 4),
            narration="UPI/DR/billpay.axb@upi/CCBILLPAY AXIS CARD",
            credit=0.0,
            debit=49500.0,
            balance=10500.0,
        ),
    ]

    engine = ForensicRulesEngine(txns)
    wallet_res, _, _, _ = engine.run_all()

    assert wallet_res.flag_raised is True
    assert wallet_res.total_rotated_volume == 49500.0
    assert len(wallet_res.detected_cycles) == 1
    cycle = wallet_res.detected_cycles[0]
    assert cycle.cycle_type == "WALLET_TO_CC_BILLPAY"
    assert cycle.delta_hours == 48.0
    assert txns[0].tags.is_wallet_rotation is True
    assert txns[1].tags.is_wallet_rotation is True
    assert "CREDIT_CARD_ROTATION_SUSPECT" in txns[0].forensic_flags


def test_gambling_critical_risk_and_speculative_trading():
    # 3 gambling transactions in the same month triggers CRITICAL_CREDIT_RISK
    txns = [
        Transaction(
            txn_id="TXN_001",
            date=date(2026, 10, 5),
            narration="UPI/DR/DREAM11/ENTRY FEE",
            credit=0.0,
            debit=1500.0,
            balance=20000.0,
        ),
        Transaction(
            txn_id="TXN_002",
            date=date(2026, 10, 10),
            narration="UPI/DR/DREAM11/ENTRY FEE",
            credit=0.0,
            debit=2000.0,
            balance=18000.0,
        ),
        Transaction(
            txn_id="TXN_003",
            date=date(2026, 10, 15),
            narration="UPI/DR/DREAM11/ENTRY FEE",
            credit=0.0,
            debit=2500.0,
            balance=15500.0,
        ),
        Transaction(
            txn_id="TXN_004",
            date=date(2026, 10, 20),
            narration="UPI/DR/ZERODHA BROKING LTD/MARGIN",
            credit=0.0,
            debit=10000.0,
            balance=5500.0,
        ),
    ]

    engine = ForensicRulesEngine(txns)
    _, spec_res, _, _ = engine.run_all()

    assert spec_res.critical_credit_risk is True
    assert spec_res.gambling_outflows == 6000.0
    assert spec_res.stock_trading_outflows == 10000.0
    assert spec_res.total_speculative_outflow == 16000.0
    assert txns[0].tags.is_gambling is True
    assert txns[3].tags.is_speculative is True


def test_cheque_nach_bounce_and_penalty_mapping():
    txns = [
        # Inward cheque bounce
        Transaction(
            txn_id="TXN_001",
            date=date(2026, 10, 5),
            narration="CTS RET CHQ RETURN INSUFFICIENT FUNDS",
            credit=0.0,
            debit=0.0,
            balance=1000.0,
        ),
        # NACH Mandate bounce
        Transaction(
            txn_id="TXN_002",
            date=date(2026, 10, 6),
            narration="ACH RTN/BAJAJ FINANCE/MANDATE REJECT",
            credit=0.0,
            debit=0.0,
            balance=1000.0,
        ),
        # Bank penalty charge
        Transaction(
            txn_id="TXN_003",
            date=date(2026, 10, 6),
            narration="ECS RETURN CHRG/GST INCL/PENALTY",
            credit=0.0,
            debit=295.0,
            balance=705.0,
        ),
    ]

    engine = ForensicRulesEngine(txns)
    _, _, bounce_res, _ = engine.run_all()

    assert bounce_res.inward_cheque_bounces == 1
    assert bounce_res.nach_mandate_bounces == 1
    assert bounce_res.total_penalty_fees == 295.0
    assert bounce_res.penalty_breakdown["INR_295"] == 295.0
    assert txns[0].tags.is_bounce is True
    assert txns[1].tags.is_bounce is True
    assert txns[2].tags.is_penalty is True


def test_partial_loan_recovery_and_fintech_charges():
    txns = [
        # Broken loan recovery of ₹160.63
        Transaction(
            txn_id="TXN_001",
            date=date(2026, 10, 7),
            narration="LN REC DL REC SWEEP PARTIAL RECOVERY",
            credit=0.0,
            debit=160.63,
            balance=0.0,
        ),
        # Fintech overdue charge
        Transaction(
            txn_id="TXN_002",
            date=date(2026, 10, 8),
            narration="AXIO OVERDUE PENALTY FEE",
            credit=0.0,
            debit=118.0,
            balance=0.0,
        ),
    ]

    engine = ForensicRulesEngine(txns)
    _, _, _, emi_res = engine.run_all()

    assert len(emi_res.partial_loan_recoveries) == 1
    assert emi_res.partial_loan_recoveries[0]["amount"] == 160.63
    assert len(emi_res.fintech_overdue_charges) == 1
    assert txns[0].tags.is_partial_recovery is True
    assert txns[1].tags.is_penalty is True
