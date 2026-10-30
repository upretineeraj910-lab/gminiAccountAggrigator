"""
Data Models and Type Definitions for Forensic Bank Statement Analyzer & Credit Underwriting Engine.
Strictly typed schemas for transaction logs, forensic findings, financial metrics, and credit verdicts.
"""

from __future__ import annotations
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TransactionCategory(str, Enum):
    SALARY = "SALARY"
    EMI_OUTFLOW = "EMI_OUTFLOW"
    WALLET_GATEWAY = "WALLET_GATEWAY"
    CREDIT_CARD_BILLPAY = "CREDIT_CARD_BILLPAY"
    SPECULATIVE_TRADING = "SPECULATIVE_TRADING"
    GAMBLING_SPECULATION = "GAMBLING_SPECULATION"
    CRYPTO_VIRTUAL_ASSET = "CRYPTO_VIRTUAL_ASSET"
    CHEQUE_BOUNCE = "CHEQUE_BOUNCE"
    MANDATE_BOUNCE = "MANDATE_BOUNCE"
    BANK_PENALTY_CHARGE = "BANK_PENALTY_CHARGE"
    INTERNAL_LOAN_RECOVERY = "INTERNAL_LOAN_RECOVERY"
    FINTECH_BNPL_CHARGE = "FINTECH_BNPL_CHARGE"
    CASH_DEPOSIT = "CASH_DEPOSIT"
    CASH_WITHDRAWAL = "CASH_WITHDRAWAL"
    UTILITY_BILLS = "UTILITY_BILLS"
    TRANSFER = "TRANSFER"
    GENERAL = "GENERAL"


class DecisionVerdict(str, Enum):
    APPROVE = "APPROVE"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    REJECT = "REJECT"


class RiskGrade(str, Enum):
    A1_PRIME = "A1_PRIME"
    A2_LOW_RISK = "A2_LOW_RISK"
    B1_MODERATE = "B1_MODERATE"
    B2_ELEVATED_RISK = "B2_ELEVATED_RISK"
    C1_HIGH_RISK = "C1_HIGH_RISK"
    REJECTED = "REJECTED"


class VisualHighlightTags(BaseModel):
    """
    Boolean flags per transaction row to enable immediate visual UI rendering
    (e.g., green for salary, red for bounce/gambling, amber for CC rotation/partial recovery).
    """
    is_salary: bool = False
    is_bounce: bool = False
    is_gambling: bool = False
    is_wallet_rotation: bool = False
    is_emi: bool = False
    is_speculative: bool = False
    is_cash_deposit: bool = False
    is_penalty: bool = False
    is_partial_recovery: bool = False


class Transaction(BaseModel):
    """Normalized bank statement transaction item."""
    txn_id: str
    date: date
    value_date: Optional[date] = None
    narration: str
    chq_ref: Optional[str] = None
    debit: float = 0.0
    credit: float = 0.0
    balance: float = 0.0
    category: TransactionCategory = TransactionCategory.GENERAL
    tags: VisualHighlightTags = Field(default_factory=VisualHighlightTags)
    forensic_flags: List[str] = Field(default_factory=list)
    raw_row: Optional[Dict[str, Any]] = None


class StatementMetadata(BaseModel):
    """Header metadata extracted deterministically from statement."""
    bank_name: str = "Unknown Bank"
    bank_code: str = "GENERIC"  # PNB, SBI, HDFC, ICICI, AXIS, CANARA, GENERIC
    account_number: str = "UNKNOWN"
    account_type: str = "SAVINGS"
    customer_name: str = "UNKNOWN"
    ifsc_code: str = "UNKNOWN"
    branch: str = "UNKNOWN"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    currency: str = "INR"


class LedgerVerificationResult(BaseModel):
    """Mathematical balance integrity report."""
    is_verified: bool
    total_transactions: int
    was_reverse_chronological: bool
    opening_balance: float
    closing_balance: float
    calculated_closing_balance: float
    discrepancy_count: int = 0
    discrepancies: List[Dict[str, Any]] = Field(default_factory=list)
    tampering_suspected: bool = False
    reconciliation_message: str = ""


class RotationCycle(BaseModel):
    """Identified circular credit/wallet rotation loop."""
    cycle_id: str
    inflow_txn_id: str
    inflow_date: date
    inflow_amount: float
    inflow_narration: str
    outflow_txn_id: str
    outflow_date: date
    outflow_amount: float
    outflow_narration: str
    delta_hours: float
    cycle_type: str
    rotated_volume: float


class WalletRotationAnalysis(BaseModel):
    """Credit Card & Wallet Cash-Out / Rotation Findings."""
    flag_raised: bool = False
    total_rotated_volume: float = 0.0
    monthly_rotated_volume: Dict[str, float] = Field(default_factory=dict)
    detected_cycles: List[RotationCycle] = Field(default_factory=list)
    details: str = ""


class SpeculativeRiskAnalysis(BaseModel):
    """High-risk trading, casino, gambling, and crypto operations."""
    stock_trading_inflows: float = 0.0
    stock_trading_outflows: float = 0.0
    stock_trading_turnover: float = 0.0
    stock_trading_drainage: float = 0.0
    gambling_outflows: float = 0.0
    gambling_frequency_monthly: Dict[str, int] = Field(default_factory=dict)
    crypto_outflows: float = 0.0
    total_speculative_outflow: float = 0.0
    speculative_pct_of_salary: float = 0.0
    critical_credit_risk: bool = False
    details: List[str] = Field(default_factory=list)


class BounceForensicsAnalysis(BaseModel):
    """Inward/outward cheque and mandate bounces with penalty fees."""
    inward_cheque_bounces: int = 0
    outward_cheque_bounces: int = 0
    nach_mandate_bounces: int = 0
    total_penalty_fees: float = 0.0
    penalty_breakdown: Dict[str, float] = Field(default_factory=dict)
    bounce_events: List[Dict[str, Any]] = Field(default_factory=list)


class EMIDefaultAnalysis(BaseModel):
    """Missed mandates, partial recoveries, and BNPL overdue charges."""
    missed_mandates: List[Dict[str, Any]] = Field(default_factory=list)
    partial_loan_recoveries: List[Dict[str, Any]] = Field(default_factory=list)
    fintech_overdue_charges: List[Dict[str, Any]] = Field(default_factory=list)
    total_penal_charges: float = 0.0


class FinancialMetrics(BaseModel):
    """Calculated underwriting ratios and cashflow health metrics."""
    average_net_monthly_salary: float = 0.0
    monthly_salaries: Dict[str, float] = Field(default_factory=dict)
    salary_consistency_score: float = 0.0
    total_monthly_obligations: float = 0.0
    obligations_breakdown: List[Dict[str, Any]] = Field(default_factory=list)
    foir_percentage: float = 0.0
    average_bank_balance: float = 0.0
    monthly_abb: Dict[str, float] = Field(default_factory=dict)
    zero_balance_days_count: int = 0
    zero_balance_days_monthly: Dict[str, int] = Field(default_factory=dict)
    cash_deposit_total: float = 0.0
    total_inflows: float = 0.0
    cash_inflow_ratio: float = 0.0


class UnderwritingVerdict(BaseModel):
    """Final credit decision and forensic scorecard."""
    decision: DecisionVerdict
    risk_grade: RiskGrade
    credit_score: int
    hard_rejection_reasons: List[str] = Field(default_factory=list)
    manual_review_triggers: List[str] = Field(default_factory=list)
    positive_factors: List[str] = Field(default_factory=list)
    underwriting_notes: List[str] = Field(default_factory=list)


class UnderwritingReport(BaseModel):
    """Complete consolidated output payload."""
    metadata: StatementMetadata
    ledger_audit: LedgerVerificationResult
    forensics: Dict[str, Any]
    financial_metrics: FinancialMetrics
    verdict: UnderwritingVerdict
    transactions: List[Transaction]
    memorandum_markdown: str
