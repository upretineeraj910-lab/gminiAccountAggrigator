"""
Unit tests for Underwriting Metrics, FOIR, ABB, Zero Balance Days, and Decision Matrix.
"""

from datetime import date
import pytest
from bank_forensics.models import (
    BounceForensicsAnalysis,
    DecisionVerdict,
    EMIDefaultAnalysis,
    LedgerVerificationResult,
    RiskGrade,
    SpeculativeRiskAnalysis,
    StatementMetadata,
    Transaction,
    VisualHighlightTags,
    WalletRotationAnalysis,
)
from bank_forensics.underwriter import CreditUnderwriter


def test_underwriting_approval_prime():
    metadata = StatementMetadata(
        bank_name="HDFC Bank",
        customer_name="ANANYA IYER",
        opening_balance=50000.0,
    )
    # Prime salaried profile: Salary 1,50,000, EMI 35,000 => FOIR 23.3%
    t1 = Transaction(
        txn_id="TXN_001",
        date=date(2026, 10, 1),
        narration="CMS/SAL/INFOSYS LTD/OCT 2026/SALARY",
        credit=150000.0,
        debit=0.0,
        balance=200000.0,
        tags=VisualHighlightTags(is_salary=True),
    )
    t2 = Transaction(
        txn_id="TXN_002",
        date=date(2026, 10, 5),
        narration="ACH/HDFC HOME LOAN EMI",
        credit=0.0,
        debit=35000.0,
        balance=165000.0,
        tags=VisualHighlightTags(is_emi=True),
    )
    txns = [t1, t2]

    ledger = LedgerVerificationResult(
        is_verified=True,
        total_transactions=2,
        was_reverse_chronological=False,
        opening_balance=50000.0,
        closing_balance=165000.0,
        calculated_closing_balance=165000.0,
    )

    underwriter = CreditUnderwriter(
        metadata=metadata,
        transactions=txns,
        ledger_audit=ledger,
        wallet_analysis=WalletRotationAnalysis(),
        speculative_analysis=SpeculativeRiskAnalysis(),
        bounce_analysis=BounceForensicsAnalysis(),
        emi_analysis=EMIDefaultAnalysis(),
    )

    metrics, verdict, memo = underwriter.evaluate()

    assert verdict.decision == DecisionVerdict.APPROVE
    assert verdict.risk_grade == RiskGrade.A1_PRIME
    assert metrics.foir_percentage == 23.33
    assert metrics.average_net_monthly_salary == 150000.0
    assert metrics.total_monthly_obligations == 35000.0
    assert "RECOMMENDATION: APPROVE" in memo


def test_underwriting_hard_rejections():
    metadata = StatementMetadata(customer_name="RISKY APPLICANT")
    t1 = Transaction(
        txn_id="TXN_001",
        date=date(2026, 10, 1),
        narration="SALARY CREDIT",
        credit=50000.0,
        balance=50000.0,
        tags=VisualHighlightTags(is_salary=True),
    )
    t2 = Transaction(
        txn_id="TXN_002",
        date=date(2026, 10, 5),
        narration="LOAN REPAYMENT",
        debit=40000.0,
        balance=10000.0,
        tags=VisualHighlightTags(is_emi=True),
    )  # FOIR = 80% > 65%

    txns = [t1, t2]
    ledger = LedgerVerificationResult(
        is_verified=True,
        total_transactions=2,
        was_reverse_chronological=False,
        opening_balance=0.0,
        closing_balance=10000.0,
        calculated_closing_balance=10000.0,
    )

    bounce_analysis = BounceForensicsAnalysis(
        inward_cheque_bounces=1,
        total_penalty_fees=295.0,
    )
    wallet_analysis = WalletRotationAnalysis(
        flag_raised=True,
        total_rotated_volume=50000.0,
    )

    underwriter = CreditUnderwriter(
        metadata=metadata,
        transactions=txns,
        ledger_audit=ledger,
        wallet_analysis=wallet_analysis,
        speculative_analysis=SpeculativeRiskAnalysis(),
        bounce_analysis=bounce_analysis,
        emi_analysis=EMIDefaultAnalysis(),
    )

    metrics, verdict, memo = underwriter.evaluate()

    assert verdict.decision == DecisionVerdict.REJECT
    assert verdict.risk_grade == RiskGrade.REJECTED
    assert any("HIGH_DEBT_BURDEN" in r for r in verdict.hard_rejection_reasons)
    assert any("DELINQUENCY_BREACH" in r for r in verdict.hard_rejection_reasons)
    assert any("CREDIT_CARD_ROTATION" in r for r in verdict.hard_rejection_reasons)
    assert "RECOMMENDATION: REJECT" in memo
