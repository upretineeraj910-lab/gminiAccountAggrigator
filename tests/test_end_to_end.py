"""
End-to-End Integration Tests for Forensic Statement Processing.
Tests PNB, HDFC, SBI, and Tampered PDF files.
"""

import os
import pytest
from bank_forensics.engine import BankForensicsEngine
from bank_forensics.models import DecisionVerdict, RiskGrade
from bank_forensics.sample_generator import generate_all_samples


@pytest.fixture(scope="module")
def sample_pdfs():
    return generate_all_samples("samples")


def test_e2e_pnb_reverse_statement(sample_pdfs):
    pdf_path = sample_pdfs["pnb_reverse"]
    engine = BankForensicsEngine()
    report = engine.analyze_pdf(pdf_path)

    # 1. Bank and Metadata
    assert report.metadata.bank_code == "PNB"
    assert report.metadata.customer_name == "VIKRAM SHARMA"
    assert report.metadata.account_number == "0145000100234567"

    # 2. Reverse Chronology & Ledger Math
    assert report.ledger_audit.was_reverse_chronological is True
    assert report.ledger_audit.is_verified is True
    assert report.ledger_audit.discrepancy_count == 0

    # 3. Credit Card Rotation
    wallet_data = report.forensics["wallet_rotation"]
    assert wallet_data["flag_raised"] is True
    assert wallet_data["total_rotated_volume"] > 0
    assert len(wallet_data["detected_cycles"]) >= 1

    # 4. Speculation & Gambling
    spec_data = report.forensics["speculative_risk"]
    assert spec_data["critical_credit_risk"] is True
    assert spec_data["gambling_outflows"] > 0
    assert spec_data["stock_trading_outflows"] > 0

    # 5. Bounce & Penalty
    bounce_data = report.forensics["bounce_forensics"]
    assert bounce_data["nach_mandate_bounces"] >= 1
    assert bounce_data["total_penalty_fees"] >= 295.0

    # 6. Loan Recovery
    emi_data = report.forensics["emi_default_analysis"]
    assert len(emi_data["partial_loan_recoveries"]) >= 1

    # 7. Verdict
    assert report.verdict.decision == DecisionVerdict.REJECT
    assert report.verdict.risk_grade == RiskGrade.REJECTED
    assert "RECOMMENDATION: REJECT" in report.memorandum_markdown


def test_e2e_hdfc_prime_statement(sample_pdfs):
    pdf_path = sample_pdfs["hdfc_prime"]
    engine = BankForensicsEngine()
    report = engine.analyze_pdf(pdf_path)

    assert report.metadata.bank_code == "HDFC"
    assert report.metadata.customer_name == "ANANYA IYER"
    assert report.ledger_audit.is_verified is True
    assert report.financial_metrics.average_net_monthly_salary == 145000.0
    assert report.financial_metrics.foir_percentage < 35.0
    assert report.forensics["bounce_forensics"]["inward_cheque_bounces"] == 0
    assert report.forensics["bounce_forensics"]["nach_mandate_bounces"] == 0
    assert report.verdict.decision == DecisionVerdict.APPROVE
    assert report.verdict.risk_grade == RiskGrade.A1_PRIME
    assert "RECOMMENDATION: APPROVE" in report.memorandum_markdown


def test_e2e_sbi_cash_stress_statement(sample_pdfs):
    pdf_path = sample_pdfs["sbi_cash_stress"]
    engine = BankForensicsEngine()
    report = engine.analyze_pdf(pdf_path)

    assert report.metadata.bank_code == "SBI"
    assert report.metadata.customer_name == "RAJESH PATEL"
    assert report.financial_metrics.cash_inflow_ratio > 0.40
    assert report.financial_metrics.zero_balance_days_count >= 5
    assert report.verdict.decision == DecisionVerdict.MANUAL_REVIEW
    assert "MANUAL REVIEW" in report.memorandum_markdown


def test_e2e_tampered_statement(sample_pdfs):
    pdf_path = sample_pdfs["tampered"]
    engine = BankForensicsEngine()
    report = engine.analyze_pdf(pdf_path)

    assert report.ledger_audit.is_verified is False
    assert report.ledger_audit.tampering_suspected is True
    assert report.ledger_audit.discrepancy_count >= 1
    assert report.verdict.decision == DecisionVerdict.REJECT
