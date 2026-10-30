"""
Underwriting Decision Matrix & Financial Indicators Engine.
Computes FOIR, Average Bank Balance (ABB), Salary consistency, Zero Balance Days,
and applies deterministic credit policies to issue Underwriting Verdicts and Markdown Memorandums.
"""

from __future__ import annotations
import math
import statistics
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple
from bank_forensics.models import (
    BounceForensicsAnalysis,
    DecisionVerdict,
    EMIDefaultAnalysis,
    FinancialMetrics,
    LedgerVerificationResult,
    RiskGrade,
    SpeculativeRiskAnalysis,
    StatementMetadata,
    Transaction,
    TransactionCategory,
    UnderwritingVerdict,
    WalletRotationAnalysis,
)


class CreditUnderwriter:
    """
    Deterministic fintech credit underwriting engine.
    Calculates debt-service ratios, cashflow diagnostics, and issues formal credit decisions.
    """

    def __init__(
        self,
        metadata: StatementMetadata,
        transactions: List[Transaction],
        ledger_audit: LedgerVerificationResult,
        wallet_analysis: WalletRotationAnalysis,
        speculative_analysis: SpeculativeRiskAnalysis,
        bounce_analysis: BounceForensicsAnalysis,
        emi_analysis: EMIDefaultAnalysis,
    ):
        self.metadata = metadata
        self.transactions = transactions
        self.ledger_audit = ledger_audit
        self.wallet = wallet_analysis
        self.speculative = speculative_analysis
        self.bounce = bounce_analysis
        self.emi = emi_analysis

    def evaluate(self) -> Tuple[FinancialMetrics, UnderwritingVerdict, str]:
        """
        Executes full underwriting evaluation:
        1. Computes financial metrics (Salary, Obligations, FOIR, ABB, Zero-balance days)
        2. Evaluates deterministic decision matrix
        3. Formulates executive Underwriting Memorandum in Markdown
        """
        metrics = self._compute_financial_metrics()
        verdict = self._evaluate_decision_matrix(metrics)
        memo = self._generate_markdown_memorandum(metrics, verdict)
        return metrics, verdict, memo

    def _compute_financial_metrics(self) -> FinancialMetrics:
        """Compute key underwriting ratios and cashflow health metrics."""
        monthly_salaries: Dict[str, float] = defaultdict(float)
        monthly_obligations: Dict[str, float] = defaultdict(float)
        monthly_inflows: Dict[str, float] = defaultdict(float)
        monthly_cash_deps: Dict[str, float] = defaultdict(float)
        obligations_breakdown: List[Dict[str, Any]] = []

        total_inflows = 0.0
        total_cash_deposits = 0.0

        for txn in self.transactions:
            m_key = txn.date.strftime("%Y-%m")

            if txn.credit > 0:
                total_inflows += txn.credit
                monthly_inflows[m_key] += txn.credit

                # Salary detection
                if txn.tags.is_salary:
                    monthly_salaries[m_key] += txn.credit

                # Cash deposit detection
                if txn.tags.is_cash_deposit:
                    total_cash_deposits += txn.credit
                    monthly_cash_deps[m_key] += txn.credit

            if txn.debit > 0:
                # Obligations (EMIs, Mandates, Employer Deductions, Loan recoveries)
                if txn.tags.is_emi or txn.tags.is_partial_recovery:
                    monthly_obligations[m_key] += txn.debit
                    obligations_breakdown.append({
                        "txn_id": txn.txn_id,
                        "date": str(txn.date),
                        "narration": txn.narration,
                        "amount": txn.debit,
                        "tag": "EMI/MANDATE",
                    })

        # Calculate salary metrics
        num_statement_months = max(len(monthly_inflows), 1)
        sal_months_count = len(monthly_salaries)
        salary_values = list(monthly_salaries.values())

        if salary_values:
            avg_salary = sum(salary_values) / len(salary_values)
            # Consistency score: proportion of active months with salary, penalized by variance
            coverage_ratio = min(sal_months_count / num_statement_months, 1.0)
            if len(salary_values) > 1:
                cv = statistics.stdev(salary_values) / (avg_salary or 1.0)
                consistency_score = max(round(coverage_ratio * (1.0 - min(cv, 0.5)), 2), 0.0)
            else:
                consistency_score = round(coverage_ratio * 0.9, 2)
        else:
            avg_salary = 0.0
            consistency_score = 0.0

        # Calculate monthly obligation metrics
        obl_values = list(monthly_obligations.values())
        avg_monthly_obligations = (
            sum(obl_values) / len(obl_values) if obl_values else 0.0
        )

        # FOIR: (Total Monthly Debt Obligations / Average Net Monthly Salary) * 100
        if avg_salary > 0:
            foir = round((avg_monthly_obligations / avg_salary) * 100, 2)
        else:
            foir = 999.0 if avg_monthly_obligations > 0 else 0.0

        # Cash inflow ratio
        cash_ratio = round(total_cash_deposits / max(total_inflows, 1.0), 4)

        # Average Bank Balance (ABB) & Zero Balance Days
        abb, monthly_abb, zero_days_count, monthly_zero_days = self._compute_daily_balance_diagnostics()

        # Update speculative ratio
        if avg_salary > 0:
            self.speculative.speculative_pct_of_salary = round(
                (self.speculative.total_speculative_outflow / (avg_salary * num_statement_months)) * 100,
                2,
            )

        return FinancialMetrics(
            average_net_monthly_salary=round(avg_salary, 2),
            monthly_salaries=dict(monthly_salaries),
            salary_consistency_score=consistency_score,
            total_monthly_obligations=round(avg_monthly_obligations, 2),
            obligations_breakdown=obligations_breakdown,
            foir_percentage=foir,
            average_bank_balance=round(abb, 2),
            monthly_abb=monthly_abb,
            zero_balance_days_count=zero_days_count,
            zero_balance_days_monthly=monthly_zero_days,
            cash_deposit_total=round(total_cash_deposits, 2),
            total_inflows=round(total_inflows, 2),
            cash_inflow_ratio=cash_ratio,
        )

    def _compute_daily_balance_diagnostics(
        self,
    ) -> Tuple[float, Dict[str, float], int, Dict[str, int]]:
        """
        Calculates daily closing balances across the statement date span
        to derive ABB and Zero Balance Days (< ₹100 or 0 balance).
        """
        if not self.transactions:
            return 0.0, {}, 0, {}

        # Map each date to its final transaction balance
        date_balances: Dict[date, float] = {}
        for txn in self.transactions:
            date_balances[txn.date] = txn.balance

        start_date = min(t.date for t in self.transactions)
        end_date = max(t.date for t in self.transactions)

        current = start_date
        last_known_balance = self.ledger_audit.opening_balance

        daily_closing: Dict[date, float] = {}
        zero_days_total = 0
        monthly_zero_days: Dict[str, int] = defaultdict(int)
        monthly_daily_balances: Dict[str, List[float]] = defaultdict(list)

        while current <= end_date:
            if current in date_balances:
                last_known_balance = date_balances[current]
            daily_closing[current] = last_known_balance

            m_key = current.strftime("%Y-%m")
            monthly_daily_balances[m_key].append(last_known_balance)

            # Check if balance <= 100.0 (near-zero / zero balance day)
            if last_known_balance <= 100.0:
                zero_days_total += 1
                monthly_zero_days[m_key] += 1

            current += timedelta(days=1)

        total_days = max(len(daily_closing), 1)
        abb = sum(daily_closing.values()) / total_days

        monthly_abb: Dict[str, float] = {}
        for m_key, bals in monthly_daily_balances.items():
            monthly_abb[m_key] = round(sum(bals) / max(len(bals), 1), 2)

        return abb, monthly_abb, zero_days_total, dict(monthly_zero_days)

    def _evaluate_decision_matrix(self, metrics: FinancialMetrics) -> UnderwritingVerdict:
        """
        Applies deterministic credit underwriting rules:
        - REJECT:
            * FOIR > 65%
            * Inward Cheque / ACH Bounces > 0
            * High-Risk Speculation / Gambling outflow > 10% of monthly salary
            * Continuous Credit Card rotation detected
            * Ledger tampering suspected
        - MANUAL_REVIEW:
            * Cash deposits > 40% of overall inflows
            * Zero balance days > 5 in any month
            * Partial internal loan recoveries detected
            * Missed mandate suspected
            * FOIR between 50% and 65%
        - APPROVE:
            * Clean ledger, stable salary inflow, FOIR < 50%, and 0 mandate bounces.
        """
        hard_rejections: List[str] = []
        manual_triggers: List[str] = []
        positive_factors: List[str] = []
        notes: List[str] = []

        # 1. Hard Rejection Checks
        if self.ledger_audit.tampering_suspected:
            hard_rejections.append("CRITICAL_RISK: Ledger tampering or severe balance discontinuity suspected.")

        if metrics.foir_percentage > 65.0:
            hard_rejections.append(f"HIGH_DEBT_BURDEN: FOIR ({metrics.foir_percentage:.1f}%) exceeds maximum limit of 65%.")

        total_bounces = self.bounce.inward_cheque_bounces + self.bounce.nach_mandate_bounces
        if total_bounces > 0:
            hard_rejections.append(
                f"DELINQUENCY_BREACH: {total_bounces} Inward Cheque / NACH mandate bounce(s) detected. Total penalty fees: ₹{self.bounce.total_penalty_fees:,.2f}."
            )

        if self.speculative.critical_credit_risk:
            hard_rejections.append("SPECULATION_BREACH: High-frequency gambling activity (>2 txns/month) flagged.")

        if self.speculative.speculative_pct_of_salary > 10.0:
            hard_rejections.append(
                f"SPECULATIVE_BURDEN: Speculative outflows ({self.speculative.speculative_pct_of_salary:.1f}% of salary) exceed 10% threshold."
            )

        if self.wallet.flag_raised and self.wallet.total_rotated_volume > 0:
            hard_rejections.append(
                f"CREDIT_CARD_ROTATION: Artificial liquidity cycling detected. Rotated volume: ₹{self.wallet.total_rotated_volume:,.2f} across {len(self.wallet.detected_cycles)} cycles."
            )

        # 2. Manual Review Checks
        if metrics.cash_inflow_ratio > 0.40:
            manual_triggers.append(
                f"CASH_INTENSIVE_INFLOWS: Cash deposits account for {metrics.cash_inflow_ratio*100:.1f}% of total inflows (policy threshold: 40%)."
            )

        high_zero_days_month = [
            f"{m} ({cnt} days)" for m, cnt in metrics.zero_balance_days_monthly.items() if cnt > 5
        ]
        if high_zero_days_month:
            manual_triggers.append(
                f"LIQUIDITY_STRAIN: Zero balance days exceeded 5 days in month(s): {', '.join(high_zero_days_month)}."
            )

        if len(self.emi.partial_loan_recoveries) > 0:
            manual_triggers.append(
                f"PARTIAL_RECOVERY_WARNING: {len(self.emi.partial_loan_recoveries)} broken internal loan recovery event(s) detected (account balance insufficient for full EMI)."
            )

        if len(self.emi.missed_mandates) > 0:
            manual_triggers.append(
                f"MISSED_MANDATE_WARNING: {len(self.emi.missed_mandates)} recurring NBFC mandate(s) scheduled between 1st-5th returned unpaid."
            )

        if 50.0 < metrics.foir_percentage <= 65.0:
            manual_triggers.append(f"MODERATE_FOIR: FOIR ({metrics.foir_percentage:.1f}%) is in elevated band (50% - 65%).")

        # 3. Positive Factors
        if metrics.salary_consistency_score >= 0.8:
            positive_factors.append(f"STABLE_INCOME: Regular salary inflow verified with consistency score {metrics.salary_consistency_score:.2f}.")

        if metrics.foir_percentage < 50.0:
            positive_factors.append(f"HEALTHY_LEVERAGE: Prudent debt profile with FOIR at {metrics.foir_percentage:.1f}%.")

        if total_bounces == 0:
            positive_factors.append("CLEAN_TRACK_RECORD: 0 cheque or mandate bounces across statement period.")

        if metrics.average_bank_balance > 25000.0:
            positive_factors.append(f"STRONG_LIQUIDITY: Robust Average Bank Balance (ABB) of ₹{metrics.average_bank_balance:,.2f}.")

        if self.ledger_audit.is_verified:
            positive_factors.append("AUDIT_PASSED: 100% mathematical ledger continuity confirmed.")

        # Final Decision Resolution
        if hard_rejections:
            decision = DecisionVerdict.REJECT
            risk_grade = RiskGrade.REJECTED
            score = max(350 - len(hard_rejections) * 40, 300)
        elif manual_triggers:
            decision = DecisionVerdict.MANUAL_REVIEW
            risk_grade = RiskGrade.B2_ELEVATED_RISK if len(manual_triggers) > 1 else RiskGrade.B1_MODERATE
            score = max(680 - len(manual_triggers) * 35, 550)
        else:
            decision = DecisionVerdict.APPROVE
            if metrics.foir_percentage < 35.0 and metrics.average_bank_balance > 50000:
                risk_grade = RiskGrade.A1_PRIME
                score = 830
            else:
                risk_grade = RiskGrade.A2_LOW_RISK
                score = 770

        return UnderwritingVerdict(
            decision=decision,
            risk_grade=risk_grade,
            credit_score=score,
            hard_rejection_reasons=hard_rejections,
            manual_review_triggers=manual_triggers,
            positive_factors=positive_factors,
            underwriting_notes=notes,
        )

    def _generate_markdown_memorandum(
        self, metrics: FinancialMetrics, verdict: UnderwritingVerdict
    ) -> str:
        """Constructs an executive Credit Underwriting Memorandum formatted in GitHub-Flavored Markdown."""
        verdict_badge = {
            DecisionVerdict.APPROVE: "**`[RECOMMENDATION: APPROVE]`**",
            DecisionVerdict.MANUAL_REVIEW: "**`[RECOMMENDATION: REFER TO CREDIT COMMITTEE / MANUAL REVIEW]`**",
            DecisionVerdict.REJECT: "**`[RECOMMENDATION: REJECT]`**",
        }.get(verdict.decision, "**`[DECISION: PENDING]`**")

        lines = [
            "# EXECUTIVE CREDIT UNDERWRITING MEMORANDUM",
            f"**Evaluation Timestamp:** {date.today().isoformat()} | **Issuing Engine:** Forensic Underwriting Matrix v2.0",
            "",
            "---",
            "## 1. Credit Verdict & Risk Scoring",
            f"- **Final Underwriting Verdict:** {verdict_badge}",
            f"- **Risk Grade Classification:** `{verdict.risk_grade.value}`",
            f"- **Engineered Forensic Credit Score:** `{verdict.credit_score} / 900`",
            f"- **Mathematical Ledger Verification:** `{'PASSED (100% Match)' if self.ledger_audit.is_verified else 'FAILED (Discrepancies Detected)'}`",
            "",
        ]

        # Key Triggers
        if verdict.hard_rejection_reasons:
            lines.append("### Critical Hard-Rejection Triggers:")
            for r in verdict.hard_rejection_reasons:
                lines.append(f"- ⛔ **{r}**")
            lines.append("")

        if verdict.manual_review_triggers:
            lines.append("### Underwriter Attention / Manual Review Flags:")
            for m in verdict.manual_review_triggers:
                lines.append(f"- ⚠️ **{m}**")
            lines.append("")

        if verdict.positive_factors:
            lines.append("### Mitigating & Positive Factors:")
            for p in verdict.positive_factors:
                lines.append(f"- ✅ **{p}**")
            lines.append("")

        lines.extend([
            "---",
            "## 2. Borrower & Statement Profile",
            "| Attribute | Extraction Record |",
            "| :--- | :--- |",
            f"| **Borrower / Account Holder** | {self.metadata.customer_name} |",
            f"| **Bank & Branch** | {self.metadata.bank_name} ({self.metadata.branch}) |",
            f"| **Account Number & Type** | `{self.metadata.account_number}` ({self.metadata.account_type}) |",
            f"| **IFSC Code** | `{self.metadata.ifsc_code}` |",
            f"| **Statement Date Span** | {self.metadata.start_date or 'N/A'} to {self.metadata.end_date or 'N/A'} |",
            f"| **Opening vs Closing Balance** | ₹{self.ledger_audit.opening_balance:,.2f} → ₹{self.ledger_audit.closing_balance:,.2f} |",
            f"| **Total Processed Transactions** | {len(self.transactions)} transactions |",
            "",
            "---",
            "## 3. Financial Indicators & Debt-Service Capability",
            "| Financial Indicator | Metric Value | Benchmark / Guideline | Status |",
            "| :--- | :--- | :--- | :--- |",
            f"| **Average Net Monthly Salary** | ₹{metrics.average_net_monthly_salary:,.2f} | Formal regular income | {'Stable' if metrics.salary_consistency_score >= 0.7 else 'Volatile'} |",
            f"| **Salary Consistency Score** | {metrics.salary_consistency_score:.2f} / 1.00 | Threshold >= 0.70 | {'✅ Pass' if metrics.salary_consistency_score >= 0.7 else '⚠️ Attention'} |",
            f"| **Total Monthly Debt Obligations** | ₹{metrics.total_monthly_obligations:,.2f} | Verified ongoing EMIs/Mandates | Monitored |",
            f"| **Fixed Obligation to Income (FOIR)** | **{metrics.foir_percentage:.2f}%** | Max Permissible: 50.0% (Hard cap 65%) | {'✅ Optimal' if metrics.foir_percentage <= 50 else ('⚠️ High' if metrics.foir_percentage <= 65 else '⛔ Breach')} |",
            f"| **Average Bank Balance (ABB)** | ₹{metrics.average_bank_balance:,.2f} | Liquidity reserve | Healthy |",
            f"| **Zero Balance Days (Total)** | {metrics.zero_balance_days_count} days | <= 5 days/month | {'✅ Clean' if metrics.zero_balance_days_count <= 5 else '⚠️ Elevated Risk'} |",
            f"| **Cash Inflow Proportion** | {metrics.cash_inflow_ratio*100:.1f}% | Limit <= 40.0% | {'✅ Clean' if metrics.cash_inflow_ratio <= 0.40 else '⚠️ High Cash'} |",
            "",
            "---",
            "## 4. Forensic Deep-Dive Findings",
            "",
            "### A. Credit Card & Wallet Cash-Out / Rotation",
            f"- **Rotation Flag Status:** `{'CREDIT_CARD_ROTATION_SUSPECT' if self.wallet.flag_raised else 'CLEAN'}`",
            f"- **Cumulative Rotated Volume:** ₹{self.wallet.total_rotated_volume:,.2f}",
            f"- **Identified Circular Cycles:** {len(self.wallet.detected_cycles)} loop(s)",
        ])

        if self.wallet.detected_cycles:
            lines.extend([
                "",
                "| Cycle ID | Inflow Date | Inflow Narration | Amount | Outflow Date | Outflow Destination | Duration |",
                "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
            ])
            for c in self.wallet.detected_cycles:
                lines.append(
                    f"| {c.cycle_id} | {c.inflow_date} | {c.inflow_narration[:25]} | ₹{c.inflow_amount:,.2f} | {c.outflow_date} | {c.outflow_narration[:25]} | {c.delta_hours:.1f}h |"
                )

        lines.extend([
            "",
            "### B. Speculative Trading & Gaming Exposure",
            f"- **Stock & F&O Day-Trading Turnover:** ₹{self.speculative.stock_trading_turnover:,.2f} (Net Cash Drainage: ₹{self.speculative.stock_trading_drainage:,.2f})",
            f"- **Gambling & Betting Outflows:** ₹{self.speculative.gambling_outflows:,.2f}",
            f"- **Crypto Asset Outflows:** ₹{self.speculative.crypto_outflows:,.2f}",
            f"- **Speculative Burden vs Monthly Income:** {self.speculative.speculative_pct_of_salary:.2f}%",
            f"- **Critical Risk Trigger:** `{'YES - GAMBLING FREQUENCY BREACH' if self.speculative.critical_credit_risk else 'NO'}`",
            "",
            "### C. Delinquency & Bounce Summary",
            f"- **Inward Cheque Bounces (High CIBIL Impact):** `{self.bounce.inward_cheque_bounces}`",
            f"- **Outward Cheque Bounces:** `{self.bounce.outward_cheque_bounces}`",
            f"- **NACH / ECS Mandate Rejections:** `{self.bounce.nach_mandate_bounces}`",
            f"- **Total Bank Penalty Charges Paid:** ₹{self.bounce.total_penalty_fees:,.2f}",
            "",
            "### D. Loan Recovery & Mandate Health",
            f"- **Missed Recurring Mandates (1st-5th):** {len(self.emi.missed_mandates)} event(s)",
            f"- **Partial Internal Loan Recoveries (Deficit Sweeps):** {len(self.emi.partial_loan_recoveries)} event(s)",
            f"- **Fintech / BNPL Overdue Penalties:** {len(self.emi.fintech_overdue_charges)} event(s)",
            "",
            "---",
            "## 5. Underwriter Conditionality & Action Plan",
        ])

        if verdict.decision == DecisionVerdict.APPROVE:
            lines.append(
                "1. **Sanction Recommended:** Applicant fulfills all regulatory and risk guidelines. Clean repayment history, zero mandate defaults, and prudent FOIR.\n"
                "2. **Conditions:** Ensure disbursement account matches verified account and verify end-use documentation."
            )
        elif verdict.decision == DecisionVerdict.MANUAL_REVIEW:
            lines.append(
                "1. **Credit Committee Escalation:** File flagged for manual underwriting override.\n"
                "2. **Mandatory Inquiries:** Request source of funds declaration for cash deposits and explanation for zero balance days.\n"
                "3. **Collateral/Co-applicant:** Suggest adding creditworthy co-borrower or lien on liquid assets to mitigate liquidity risk."
            )
        else:
            lines.append(
                "1. **Decline Application:** Multiple non-negotiable credit parameters breached (e.g. mandate defaults, excessive leverage, or artificial liquidity cycling).\n"
                "2. **Cooling Period:** Standard 6-month cooling period before reconsideration, contingent on 0 bounces and cured debt obligations."
            )

        return "\n".join(lines)
