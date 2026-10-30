"""
Forensic Rules & Pattern Detection Engine.
Detects Credit Card / Wallet rotation loops, Speculative/Gambling trading,
Cheque and NACH/ECS bounces with penalty fee mapping, and EMI default/partial recovery patterns.
"""

from __future__ import annotations
import re
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from bank_forensics.models import (
    BounceForensicsAnalysis,
    EMIDefaultAnalysis,
    RotationCycle,
    SpeculativeRiskAnalysis,
    Transaction,
    TransactionCategory,
    VisualHighlightTags,
    WalletRotationAnalysis,
)


class ForensicRulesEngine:
    """
    Executes forensic rules on normalized bank statement transactions.
    """

    # --- Regex Patterns ---
    WALLET_REGEX = re.compile(
        r"(?i)(MOBIKWIK|FREECHARGE|PAYTM.*WALLET|PAYZAPP|AMAZONPAY.*WALLET|PPIW|AIRTEL.*WALLET|PHONEPE.*WALLET)"
    )
    GATEWAY_RENT_REGEX = re.compile(
        r"(?i)(CRED|HOUSING|NOBROKER|MAGICBRICKS|CHQBOOK|REDGIRAFFE|PAWNBROKER|PAYTM.*RENT)"
    )
    CC_BILLPAY_REGEX = re.compile(
        r"(?i)(billpay.*@upi|mbkccbp@|cred@|credpay|ccbillpay|bbps.*card|card.*bill|credit\s*card|cc\s*pay|sbi\s*card|hdfc\s*card|icici\s*card|axis\s*card|rbl\s*card)"
    )

    STOCK_FO_REGEX = re.compile(
        r"(?i)(ZERODHA|GROWW|UPSTOX|ANGELONE|DHAN|MOTILAL|5PAISA|KOTAK.*SECURITIES|ICICIDIRECT|SHAREKHAN|INDIABULLS)"
    )
    GAMBLING_REGEX = re.compile(
        r"(?i)(DREAM11|MY11CIRCLE|MPL|GAMES24X7|WINZO|POKERBAAZI|JUNGLEE|PARIMATCH|1XBET|BETWAY|STAKE|CASINO|RUMMY|LOTTERY)"
    )
    CRYPTO_REGEX = re.compile(
        r"(?i)(WAZIRX|COINDCX|COINSWITCH|BINANCE|ZEBPAY|CRYPTO)"
    )

    INWARD_CHEQUE_BOUNCE_REGEX = re.compile(
        r"(?i)(CHQ.*RET|CHEQUE.*RETURN|INSUFFICIENT.*FUNDS|REFER TO DRAWER|CTS RET|CTS RETURN|CHQ RTN)"
    )
    OUTWARD_CHEQUE_BOUNCE_REGEX = re.compile(
        r"(?i)(OUTWARD.*RET|DEP.*CHQ.*RET)"
    )
    NACH_ECS_BOUNCE_REGEX = re.compile(
        r"(?i)(ACH RTN|ECS RTN|NACH REJ|MANDATE REJECT|ECS RETURN|NACH RET|ACH REJECT|MANDATE FAIL)"
    )
    PENALTY_CHARGES_REGEX = re.compile(
        r"(?i)(RETURN\s*CHRG|RET\s*CHG|PENAL|ECS\s*RET|MANDATE\s*REJ|CHQ\s*RET|BOUNCE\s*CHG|INWARD\s*RET\s*CHG)"
    )

    KNOWN_PENALTY_AMOUNTS = {118.0, 236.0, 295.0, 354.0, 472.0, 500.0, 590.0}

    NBFC_LENDER_REGEX = re.compile(
        r"(?i)(BAJAJ|HDB|IDFC|CHOLAMANDALAM|CHOLA|TATA\s*CAP|MUTHOOT|HERO\s*FIN|L&T\s*FIN|ADITYA\s*BIRLA|ABFL|PIRAMAL|KOTAK\s*MAH|MAHINDRA\s*FIN|SHRIRAM|POONAWALLA|DMI\s*FINANCE|HOME\s*CREDIT|KREDITBEE|NAVIFINS|FULLERTON)"
    )
    INTERNAL_LOAN_REC_REGEX = re.compile(
        r"(?i)(LN REC|DL REC|PART REC|LOAN RECOVERY|RECOVERY FROM A\/C|AUTO RECOVERY|INT REC|INSTALLMENT REC|OD REC|SWEEP REC)"
    )
    FINTECH_BNPL_REGEX = re.compile(
        r"(?i)(AXIO|KISTPAY|SIMPL|LAZYPAY|KREDITBEE|RING|POSTPE|PAYU)"
    )
    CASH_DEP_REGEX = re.compile(
        r"(?i)(CASH DEP|BY CASH|CDM|ATM DEP|CASH RECYCLER|SELF DEP|CASH DEPOSIT)"
    )
    SALARY_REGEX = re.compile(
        r"(?i)(TREASURY|WBEP|PAO|GOVT|DISBURSEMENT|POLICE|DEFENCE|RAILWAY|CENTRAL GOVT|STATE GOVT|SALARY|PAYROLL|CMS\/SAL|NEFT.*SAL|SAL\s*FOR|MONTHLY\s*SAL|WAGES)"
    )
    EMPLOYER_DEDUCTION_REGEX = re.compile(
        r"(?i)(COPT DEDUC|SOCIETY DEDUC|COOP LOAN|SALARY DED|LIC\s*PREM)"
    )

    def __init__(self, transactions: List[Transaction]):
        self.transactions = transactions

    def run_all(self) -> Tuple[
        WalletRotationAnalysis,
        SpeculativeRiskAnalysis,
        BounceForensicsAnalysis,
        EMIDefaultAnalysis,
    ]:
        """Run all forensic inspection modules across transactions."""
        # 1. Base tagging and category resolution
        self._tag_transactions()

        # 2. Individual forensic modules
        wallet_analysis = self.detect_wallet_rotation()
        speculative_analysis = self.detect_speculative_risk()
        bounce_analysis = self.detect_bounces_and_penalties()
        emi_analysis = self.detect_emi_defaults_and_partial_recoveries()

        return wallet_analysis, speculative_analysis, bounce_analysis, emi_analysis

    def _tag_transactions(self) -> None:
        """Assign baseline visual highlight tags and categories."""
        for txn in self.transactions:
            narr = txn.narration.upper()

            # Cash Deposit
            if txn.credit > 0 and self.CASH_DEP_REGEX.search(narr):
                txn.tags.is_cash_deposit = True
                txn.category = TransactionCategory.CASH_DEPOSIT

            # Salary
            if txn.credit > 0 and self.SALARY_REGEX.search(narr):
                txn.tags.is_salary = True
                txn.category = TransactionCategory.SALARY

            # Gambling
            if self.GAMBLING_REGEX.search(narr):
                txn.tags.is_gambling = True
                txn.category = TransactionCategory.GAMBLING_SPECULATION

            # Speculative Stock / Crypto
            if self.STOCK_FO_REGEX.search(narr):
                txn.tags.is_speculative = True
                txn.category = TransactionCategory.SPECULATIVE_TRADING
            elif self.CRYPTO_REGEX.search(narr):
                txn.tags.is_speculative = True
                txn.category = TransactionCategory.CRYPTO_VIRTUAL_ASSET

            # Cheque Bounce
            if self.INWARD_CHEQUE_BOUNCE_REGEX.search(narr):
                txn.tags.is_bounce = True
                txn.category = TransactionCategory.CHEQUE_BOUNCE
                txn.forensic_flags.append("CHEQUE_BOUNCE_INWARD")
            elif self.OUTWARD_CHEQUE_BOUNCE_REGEX.search(narr):
                txn.tags.is_bounce = True
                txn.category = TransactionCategory.CHEQUE_BOUNCE
                txn.forensic_flags.append("CHEQUE_BOUNCE_OUTWARD")

            # Mandate Bounce
            if self.NACH_ECS_BOUNCE_REGEX.search(narr):
                txn.tags.is_bounce = True
                txn.category = TransactionCategory.MANDATE_BOUNCE
                txn.forensic_flags.append("MANDATE_BOUNCE_NACH_ECS")

            # Penalty Charges
            if txn.debit > 0 and (
                self.PENALTY_CHARGES_REGEX.search(narr)
                or (txn.debit in self.KNOWN_PENALTY_AMOUNTS and any(k in narr for k in ["CHG", "CHRG", "FEE", "RET"]))
            ):
                txn.tags.is_penalty = True
                txn.category = TransactionCategory.BANK_PENALTY_CHARGE

            # EMI / Loan / Mandate Outflows
            if txn.debit > 0 and (
                self.NBFC_LENDER_REGEX.search(narr)
                or self.EMPLOYER_DEDUCTION_REGEX.search(narr)
                or re.search(r"(?i)\b(ACH|NACH|ECS|LOAN|EMI)\b", narr)
            ):
                if not txn.tags.is_bounce and not txn.tags.is_penalty:
                    txn.tags.is_emi = True
                    txn.category = TransactionCategory.EMI_OUTFLOW

            # Partial loan recovery
            if txn.debit > 0 and self.INTERNAL_LOAN_REC_REGEX.search(narr):
                txn.tags.is_partial_recovery = True
                txn.category = TransactionCategory.INTERNAL_LOAN_RECOVERY

    # =========================================================================
    # MODULE 1: Credit Card & Wallet Cash-Out / Rotation Detection
    # =========================================================================
    def detect_wallet_rotation(self) -> WalletRotationAnalysis:
        """
        Catches users rotating credit card limits into bank accounts via wallets
        or payment gateways to generate artificial liquidity.
        Traces circular loops within 24 to 72 hours:
        1. Wallet / Gateway Cash-In -> Credit Card Bill Payment Outflow
        2. High-frequency bidirectional transactions between bank and wallet (Add Money -> Cash Out)
        """
        cycles: List[RotationCycle] = []
        monthly_vol: Dict[str, float] = defaultdict(float)
        matched_txns: Set[str] = set()

        # Identify Inflow candidates: Wallets (PPIW, Mobikwik, Paytm) or Gateways (Cred, Housing, NoBroker)
        inflow_candidates: List[Transaction] = []
        for txn in self.transactions:
            if txn.credit > 0:
                is_wallet = bool(self.WALLET_REGEX.search(txn.narration))
                is_gateway = bool(self.GATEWAY_RENT_REGEX.search(txn.narration))
                if is_wallet or is_gateway:
                    inflow_candidates.append(txn)

        # Identify Outflow candidates: CC bill payments or transfers into/back to wallet
        outflow_candidates: List[Transaction] = []
        for txn in self.transactions:
            if txn.debit > 0:
                is_cc_billpay = bool(self.CC_BILLPAY_REGEX.search(txn.narration))
                is_wallet_out = bool(self.WALLET_REGEX.search(txn.narration))
                is_gateway_out = bool(self.GATEWAY_RENT_REGEX.search(txn.narration))
                if is_cc_billpay or is_wallet_out or is_gateway_out:
                    outflow_candidates.append(txn)

        # Pattern 1: Wallet/Gateway Inflow -> CC Bill Payment Outflow within 24-72h
        for inf in inflow_candidates:
            for out in outflow_candidates:
                if out.txn_id in matched_txns or inf.txn_id in matched_txns:
                    continue
                if out.date < inf.date:
                    continue

                delta_days = (out.date - inf.date).days
                delta_hours = max(delta_days * 24.0, 1.0)
                if delta_hours > 72.0:
                    continue

                diff_ratio = abs(inf.credit - out.debit) / max(inf.credit, 1.0)
                is_amount_match = diff_ratio <= 0.15
                is_cc_pay = bool(self.CC_BILLPAY_REGEX.search(out.narration))

                if is_amount_match and is_cc_pay:
                    cycle_vol = min(inf.credit, out.debit)
                    cycle = RotationCycle(
                        cycle_id=f"ROT_{len(cycles)+1:03d}",
                        inflow_txn_id=inf.txn_id,
                        inflow_date=inf.date,
                        inflow_amount=inf.credit,
                        inflow_narration=inf.narration,
                        outflow_txn_id=out.txn_id,
                        outflow_date=out.date,
                        outflow_amount=out.debit,
                        outflow_narration=out.narration,
                        delta_hours=delta_hours,
                        cycle_type="WALLET_TO_CC_BILLPAY",
                        rotated_volume=cycle_vol,
                    )
                    cycles.append(cycle)
                    matched_txns.add(out.txn_id)
                    matched_txns.add(inf.txn_id)

                    inf.tags.is_wallet_rotation = True
                    out.tags.is_wallet_rotation = True
                    if "CREDIT_CARD_ROTATION_SUSPECT" not in inf.forensic_flags:
                        inf.forensic_flags.append("CREDIT_CARD_ROTATION_SUSPECT")
                    if "CREDIT_CARD_ROTATION_SUSPECT" not in out.forensic_flags:
                        out.forensic_flags.append("CREDIT_CARD_ROTATION_SUSPECT")

                    m_key = inf.date.strftime("%Y-%m")
                    monthly_vol[m_key] += cycle_vol
                    break

        # Pattern 2: Bidirectional Bank <-> Wallet transactions within 24-72h (e.g. Add Money -> Cash Out)
        for out in outflow_candidates:
            if not self.WALLET_REGEX.search(out.narration) and not self.GATEWAY_RENT_REGEX.search(out.narration):
                continue
            for inf in inflow_candidates:
                if out.txn_id in matched_txns or inf.txn_id in matched_txns:
                    continue
                # Check delta either direction within 72 hours
                delta_days = abs((inf.date - out.date).days)
                delta_hours = max(delta_days * 24.0, 1.0)
                if delta_hours > 72.0:
                    continue

                diff_ratio = abs(inf.credit - out.debit) / max(inf.credit, 1.0)
                if diff_ratio <= 0.15:
                    cycle_vol = min(inf.credit, out.debit)
                    cycle = RotationCycle(
                        cycle_id=f"ROT_{len(cycles)+1:03d}",
                        inflow_txn_id=inf.txn_id,
                        inflow_date=inf.date,
                        inflow_amount=inf.credit,
                        inflow_narration=inf.narration,
                        outflow_txn_id=out.txn_id,
                        outflow_date=out.date,
                        outflow_amount=out.debit,
                        outflow_narration=out.narration,
                        delta_hours=delta_hours,
                        cycle_type="BIDIRECTIONAL_WALLET_LOOP",
                        rotated_volume=cycle_vol,
                    )
                    cycles.append(cycle)
                    matched_txns.add(out.txn_id)
                    matched_txns.add(inf.txn_id)

                    inf.tags.is_wallet_rotation = True
                    out.tags.is_wallet_rotation = True
                    if "CREDIT_CARD_ROTATION_SUSPECT" not in inf.forensic_flags:
                        inf.forensic_flags.append("CREDIT_CARD_ROTATION_SUSPECT")
                    if "CREDIT_CARD_ROTATION_SUSPECT" not in out.forensic_flags:
                        out.forensic_flags.append("CREDIT_CARD_ROTATION_SUSPECT")

                    m_key = inf.date.strftime("%Y-%m")
                    monthly_vol[m_key] += cycle_vol
                    break

        total_vol = sum(c.rotated_volume for c in cycles)
        flag_raised = len(cycles) > 0

        detail_msg = (
            f"Detected {len(cycles)} circular rotation cycles totaling ₹{total_vol:,.2f} "
            f"across {len(monthly_vol)} statement months."
            if flag_raised
            else "No circular credit card / wallet rotation patterns identified."
        )

        return WalletRotationAnalysis(
            flag_raised=flag_raised,
            total_rotated_volume=total_vol,
            monthly_rotated_volume=dict(monthly_vol),
            detected_cycles=cycles,
            details=detail_msg,
        )

    def _extract_vpa(self, text: str) -> Optional[str]:
        """Extract UPI VPA or handle from narration if present."""
        m = re.search(r"([a-zA-Z0-9\.\-_]+@[a-zA-Z0-9]+)", text)
        return m.group(1).lower() if m else None

    # =========================================================================
    # MODULE 2: Speculative Inflows/Outflows (Trading, Crypto & Gambling)
    # =========================================================================
    def detect_speculative_risk(self) -> SpeculativeRiskAnalysis:
        """
        Detects stock day-trading / F&O churning, gambling, and crypto exposure.
        Flags CRITICAL_CREDIT_RISK if gambling frequency > 2 times in any month.
        """
        stock_in = 0.0
        stock_out = 0.0
        gambling_out = 0.0
        crypto_out = 0.0
        gambling_monthly_counts: Dict[str, int] = defaultdict(int)
        details: List[str] = []

        for txn in self.transactions:
            narr = txn.narration
            m_key = txn.date.strftime("%Y-%m")

            # Stock & F&O Trading
            if self.STOCK_FO_REGEX.search(narr):
                if txn.debit > 0:
                    stock_out += txn.debit
                if txn.credit > 0:
                    stock_in += txn.credit
                txn.tags.is_speculative = True
                txn.forensic_flags.append("SPECULATIVE_STOCK_FO")

            # Gambling / Casino
            if self.GAMBLING_REGEX.search(narr):
                if txn.debit > 0:
                    gambling_out += txn.debit
                    gambling_monthly_counts[m_key] += 1
                txn.tags.is_gambling = True
                txn.forensic_flags.append("GAMBLING_SPECULATION")

            # Crypto
            if self.CRYPTO_REGEX.search(narr):
                if txn.debit > 0:
                    crypto_out += txn.debit
                txn.tags.is_speculative = True
                txn.forensic_flags.append("CRYPTO_VIRTUAL_ASSET")

        stock_turnover = stock_in + stock_out
        stock_drainage = max(stock_out - stock_in, 0.0)
        total_speculative = stock_out + gambling_out + crypto_out

        # High-frequency gambling check: > 2 times per month
        critical_risk = any(cnt > 2 for cnt in gambling_monthly_counts.values())

        if critical_risk:
            details.append("CRITICAL_CREDIT_RISK: High-frequency gambling activity (>2 txns/month) detected.")
        if gambling_out > 0:
            details.append(f"Gambling & Betting Outflows: ₹{gambling_out:,.2f} across {sum(gambling_monthly_counts.values())} events.")
        if stock_turnover > 0:
            details.append(f"Stock & F&O Turnover: ₹{stock_turnover:,.2f} (Net Drainage: ₹{stock_drainage:,.2f}).")
        if crypto_out > 0:
            details.append(f"Crypto Asset Outflows: ₹{crypto_out:,.2f}.")

        return SpeculativeRiskAnalysis(
            stock_trading_inflows=stock_in,
            stock_trading_outflows=stock_out,
            stock_trading_turnover=stock_turnover,
            stock_trading_drainage=stock_drainage,
            gambling_outflows=gambling_out,
            gambling_frequency_monthly=dict(gambling_monthly_counts),
            crypto_outflows=crypto_out,
            total_speculative_outflow=total_speculative,
            critical_credit_risk=critical_risk,
            details=details,
        )

    # =========================================================================
    # MODULE 3: Cheque & NACH / ECS Bounce Forensics
    # =========================================================================
    def detect_bounces_and_penalties(self) -> BounceForensicsAnalysis:
        """
        Distinguishes between inward and outward bounces and maps penalty charges.
        """
        inward_chq = 0
        outward_chq = 0
        nach_bounces = 0
        total_penalties = 0.0
        penalty_breakdown: Dict[str, float] = defaultdict(float)
        bounce_events: List[Dict[str, Any]] = []

        for txn in self.transactions:
            narr = txn.narration.upper()

            # Check if this row is a bank penalty charge debit
            is_penalty = False
            if txn.debit > 0:
                if self.PENALTY_CHARGES_REGEX.search(narr):
                    is_penalty = True
                elif txn.debit in self.KNOWN_PENALTY_AMOUNTS and any(
                    k in narr for k in ["CHG", "CHRG", "RET", "BOUNCE", "PENAL", "FEE"]
                ):
                    is_penalty = True

            if is_penalty:
                total_penalties += txn.debit
                penalty_breakdown[f"INR_{int(txn.debit)}"] += txn.debit
                txn.tags.is_penalty = True
                txn.forensic_flags.append(f"PENALTY_FEE_{txn.debit}")

            # Inward cheque bounce (Customer issued cheque bounced - High CIBIL impact)
            if self.INWARD_CHEQUE_BOUNCE_REGEX.search(narr) and not is_penalty:
                inward_chq += 1
                bounce_events.append({
                    "txn_id": txn.txn_id,
                    "date": str(txn.date),
                    "type": "CHEQUE_BOUNCE_INWARD",
                    "narration": txn.narration,
                    "amount": txn.debit or txn.credit,
                })
                txn.tags.is_bounce = True
                if "CHEQUE_BOUNCE_INWARD" not in txn.forensic_flags:
                    txn.forensic_flags.append("CHEQUE_BOUNCE_INWARD")

            # Outward cheque bounce (Cheque deposited by customer bounced)
            elif self.OUTWARD_CHEQUE_BOUNCE_REGEX.search(narr) and not is_penalty:
                outward_chq += 1
                bounce_events.append({
                    "txn_id": txn.txn_id,
                    "date": str(txn.date),
                    "type": "CHEQUE_BOUNCE_OUTWARD",
                    "narration": txn.narration,
                    "amount": txn.debit or txn.credit,
                })
                txn.tags.is_bounce = True
                if "CHEQUE_BOUNCE_OUTWARD" not in txn.forensic_flags:
                    txn.forensic_flags.append("CHEQUE_BOUNCE_OUTWARD")

            # NACH / ECS Mandate Reject
            elif self.NACH_ECS_BOUNCE_REGEX.search(narr) and not is_penalty:
                nach_bounces += 1
                bounce_events.append({
                    "txn_id": txn.txn_id,
                    "date": str(txn.date),
                    "type": "NACH_ECS_MANDATE_BOUNCE",
                    "narration": txn.narration,
                    "amount": txn.debit,
                })
                txn.tags.is_bounce = True
                if "MANDATE_BOUNCE_NACH_ECS" not in txn.forensic_flags:
                    txn.forensic_flags.append("MANDATE_BOUNCE_NACH_ECS")

        return BounceForensicsAnalysis(
            inward_cheque_bounces=inward_chq,
            outward_cheque_bounces=outward_chq,
            nach_mandate_bounces=nach_bounces,
            total_penalty_fees=total_penalties,
            penalty_breakdown=dict(penalty_breakdown),
            bounce_events=bounce_events,
        )

    # =========================================================================
    # MODULE 4: EMI Default & Partial Payment Detection
    # =========================================================================
    def detect_emi_defaults_and_partial_recoveries(self) -> EMIDefaultAnalysis:
        """
        Catches:
        1. Recurring NBFC scheduled between 1st-5th that failed or missed.
        2. Partial internal loan recoveries (e.g. ₹160.63, ₹447.06 when standard instalment is ~₹19,000+).
        3. Fintech and BNPL overdue charges (AXIO, KISTPAY, SIMPL, LAZYPAY).
        """
        missed_mandates: List[Dict[str, Any]] = []
        partial_recoveries: List[Dict[str, Any]] = []
        fintech_overdue: List[Dict[str, Any]] = []
        total_penal = 0.0

        # Scan for partial internal loan recovery lines
        for txn in self.transactions:
            if txn.debit <= 0:
                continue

            narr = txn.narration.upper()

            # 1. Partial internal recovery check: broken fractional amount or keyword match
            if self.INTERNAL_LOAN_REC_REGEX.search(narr):
                # Broken paise amount (e.g. .63, .06) or small amount indicates insufficient funds sweep
                is_fractional = (txn.debit % 1.0) != 0.0
                if is_fractional or txn.debit < 1000.0:
                    partial_recoveries.append({
                        "txn_id": txn.txn_id,
                        "date": str(txn.date),
                        "amount": txn.debit,
                        "narration": txn.narration,
                        "flag": "BROKEN_PARTIAL_LOAN_RECOVERY",
                    })
                    txn.tags.is_partial_recovery = True
                    txn.forensic_flags.append("PARTIAL_LOAN_RECOVERY_DEFICIT")

            # 2. Fintech / BNPL overdue charges
            if self.FINTECH_BNPL_REGEX.search(narr):
                is_penal = any(k in narr for k in ["OVERDUE", "PENAL", "LATE", "DEFAULT", "FEE", "BOUNCE"])
                if is_penal or txn.debit < 500.0:
                    fintech_overdue.append({
                        "txn_id": txn.txn_id,
                        "date": str(txn.date),
                        "amount": txn.debit,
                        "narration": txn.narration,
                        "lender": "FINTECH_BNPL",
                    })
                    total_penal += txn.debit
                    txn.tags.is_penalty = True
                    txn.forensic_flags.append("FINTECH_BNPL_OVERDUE_CHARGE")

        # 3. Detect missed recurring NBFC mandates scheduled between 1st-5th
        # Find recurring NBFC lenders across months
        lender_months: Dict[str, Set[str]] = defaultdict(set)
        for txn in self.transactions:
            if txn.debit > 0 and self.NBFC_LENDER_REGEX.search(txn.narration):
                m_match = self.NBFC_LENDER_REGEX.search(txn.narration)
                if m_match:
                    lender = m_match.group(1).upper()
                    m_key = txn.date.strftime("%Y-%m")
                    lender_months[lender].add(m_key)

        # Cross-reference with bounce charges between 1st-5th
        for txn in self.transactions:
            if txn.date.day <= 5 and txn.tags.is_bounce:
                for lender in lender_months:
                    if lender in txn.narration.upper():
                        missed_mandates.append({
                            "txn_id": txn.txn_id,
                            "date": str(txn.date),
                            "lender": lender,
                            "narration": txn.narration,
                            "reason": "NBFC mandate scheduled between 1st-5th returned unpaid.",
                        })
                        txn.forensic_flags.append("MISSED_MANDATE_DEFAULT")

        return EMIDefaultAnalysis(
            missed_mandates=missed_mandates,
            partial_loan_recoveries=partial_recoveries,
            fintech_overdue_charges=fintech_overdue,
            total_penal_charges=total_penal,
        )
