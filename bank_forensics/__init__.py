"""
Bank Forensics & Credit Underwriting Package.
Deterministic, multi-bank statement parsing, forensic pattern detection, and underwriting matrix.
"""

from bank_forensics.engine import BankForensicsEngine
from bank_forensics.forensic_rules import ForensicRulesEngine
from bank_forensics.models import (
    BounceForensicsAnalysis,
    DecisionVerdict,
    EMIDefaultAnalysis,
    FinancialMetrics,
    LedgerVerificationResult,
    RiskGrade,
    RotationCycle,
    SpeculativeRiskAnalysis,
    StatementMetadata,
    Transaction,
    TransactionCategory,
    UnderwritingReport,
    UnderwritingVerdict,
    VisualHighlightTags,
    WalletRotationAnalysis,
)
from bank_forensics.normalizer import TransactionNormalizer
from bank_forensics.pdf_extractor import PDFExtractionError, PDFExtractor
from bank_forensics.templates import BankTemplateEngine, parse_indian_date

__all__ = [
    "BankForensicsEngine",
    "ForensicRulesEngine",
    "TransactionNormalizer",
    "PDFExtractor",
    "PDFExtractionError",
    "BankTemplateEngine",
    "parse_indian_date",
    "StatementMetadata",
    "Transaction",
    "TransactionCategory",
    "VisualHighlightTags",
    "LedgerVerificationResult",
    "RotationCycle",
    "WalletRotationAnalysis",
    "SpeculativeRiskAnalysis",
    "BounceForensicsAnalysis",
    "EMIDefaultAnalysis",
    "FinancialMetrics",
    "UnderwritingVerdict",
    "UnderwritingReport",
    "DecisionVerdict",
    "RiskGrade",
]
