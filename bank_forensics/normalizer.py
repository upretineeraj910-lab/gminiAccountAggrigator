"""
Transaction Normalizer & Ledger Math Verification Module.
Resolves reverse chronological statements (e.g. PNB ONE), validates mathematical ledger integrity,
and maps transactions into standardized, visually tagged structures.
"""

from __future__ import annotations
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
from bank_forensics.models import (
    LedgerVerificationResult,
    StatementMetadata,
    Transaction,
    TransactionCategory,
    VisualHighlightTags,
)
from bank_forensics.templates import clean_amount, parse_indian_date


class TransactionNormalizer:
    """
    Normalizes raw extracted transaction rows into chronologically sorted,
    mathematically verified, and typed Transaction objects.
    """

    TOLERANCE: float = 0.05  # INR tolerance for float rounding

    def __init__(self, metadata: StatementMetadata):
        self.metadata = metadata

    def normalize(
        self, raw_rows: List[Dict[str, Any]]
    ) -> Tuple[List[Transaction], LedgerVerificationResult]:
        """
        Main pipeline:
        1. Parse raw text rows to initial Transaction objects
        2. Detect and correct reverse chronological ordering
        3. Verify mathematical ledger integrity: Balance_i = Balance_{i-1} + Credit_i - Debit_i
        4. Return normalized transactions and verification report
        """
        initial_txns: List[Transaction] = []
        for idx, row in enumerate(raw_rows):
            d_str = row.get("date_str", "")
            parsed_date = parse_indian_date(d_str)
            if not parsed_date:
                continue

            v_str = row.get("value_date_str", "")
            value_date = parse_indian_date(v_str) if v_str else parsed_date

            narration = str(row.get("narration", "")).strip()
            chq_ref = str(row.get("chq_ref", "")).strip() or None
            debit = clean_amount(row.get("debit_str"))
            credit = clean_amount(row.get("credit_str"))
            balance = clean_amount(row.get("balance_str"))

            initial_txns.append(
                Transaction(
                    txn_id=f"TXN_{idx+1:04d}",
                    date=parsed_date,
                    value_date=value_date,
                    narration=narration,
                    chq_ref=chq_ref,
                    debit=debit,
                    credit=credit,
                    balance=balance,
                    raw_row=row,
                )
            )

        if not initial_txns:
            return [], LedgerVerificationResult(
                is_verified=False,
                total_transactions=0,
                was_reverse_chronological=False,
                opening_balance=0.0,
                closing_balance=0.0,
                calculated_closing_balance=0.0,
                discrepancy_count=0,
                reconciliation_message="No valid transactions parsed from statement.",
            )

        # Detect reverse chronology
        chronological_txns, was_reversed = self._resolve_chronology(initial_txns)

        # Verify mathematical balance ledger
        verified_txns, verification_result = self._verify_ledger(
            chronological_txns, was_reversed
        )

        return verified_txns, verification_result

    def _resolve_chronology(
        self, txns: List[Transaction]
    ) -> Tuple[List[Transaction], bool]:
        """
        Detects if transactions are ordered newest-to-oldest (PNB ONE / e-statements)
        and re-orders them to ascending order: Date ASC, Index ASC.
        """
        if len(txns) <= 1:
            return txns, False

        # 1. Date direction check
        date_descending_count = 0
        date_ascending_count = 0
        for i in range(len(txns) - 1):
            if txns[i].date > txns[i + 1].date:
                date_descending_count += 1
            elif txns[i].date < txns[i + 1].date:
                date_ascending_count += 1

        is_reverse_by_date = date_descending_count > date_ascending_count

        # 2. Mathematical ledger continuity test in forward vs reverse
        forward_discrepancies = self._count_ledger_discrepancies(txns)
        reversed_list = list(reversed(txns))
        reversed_discrepancies = self._count_ledger_discrepancies(reversed_list)

        # Decide whether to reverse
        should_reverse = False
        if reversed_discrepancies < forward_discrepancies:
            should_reverse = True
        elif is_reverse_by_date and (reversed_discrepancies <= forward_discrepancies):
            should_reverse = True
        elif self.metadata.bank_code == "PNB" and is_reverse_by_date:
            should_reverse = True

        if should_reverse:
            # Re-index transaction IDs in proper ascending order
            for i, txn in enumerate(reversed_list):
                txn.txn_id = f"TXN_{i+1:04d}"
            return reversed_list, True

        return txns, False

    def _count_ledger_discrepancies(self, txns: List[Transaction]) -> int:
        """Count how many rows violate Balance_i = Balance_{i-1} + Credit_i - Debit_i."""
        if len(txns) <= 1:
            return 0
        disc_count = 0
        for i in range(1, len(txns)):
            prev = txns[i - 1]
            curr = txns[i]
            expected = prev.balance + curr.credit - curr.debit
            if abs(curr.balance - expected) > self.TOLERANCE:
                disc_count += 1
        return disc_count

    def _verify_ledger(
        self, txns: List[Transaction], was_reversed: bool
    ) -> Tuple[List[Transaction], LedgerVerificationResult]:
        """
        Executes deterministic mathematical ledger verification:
        Expected_Balance_i = Balance_{i-1} + Credit_i - Debit_i.
        """
        if not txns:
            return txns, LedgerVerificationResult(
                is_verified=False,
                total_transactions=0,
                was_reverse_chronological=was_reversed,
                opening_balance=0.0,
                closing_balance=0.0,
                calculated_closing_balance=0.0,
                reconciliation_message="Empty ledger.",
            )

        # Determine opening balance before txn 0
        first_txn = txns[0]
        inferred_opening_balance = first_txn.balance - first_txn.credit + first_txn.debit
        reported_opening = (
            self.metadata.opening_balance
            if self.metadata.opening_balance is not None
            else inferred_opening_balance
        )

        running_balance = reported_opening
        discrepancies: List[Dict[str, Any]] = []

        for i, txn in enumerate(txns):
            expected_balance = round(running_balance + txn.credit - txn.debit, 2)
            reported_balance = round(txn.balance, 2)
            diff = round(reported_balance - expected_balance, 2)

            if abs(diff) > self.TOLERANCE:
                discrepancies.append({
                    "row_index": i + 1,
                    "txn_id": txn.txn_id,
                    "date": str(txn.date),
                    "narration": txn.narration[:60],
                    "prev_balance": running_balance,
                    "credit": txn.credit,
                    "debit": txn.debit,
                    "expected_balance": expected_balance,
                    "reported_balance": reported_balance,
                    "discrepancy": diff,
                })
                txn.forensic_flags.append(f"LEDGER_DISCREPANCY_DIFF_{diff}")

            # Advance running balance
            running_balance = reported_balance

        closing_balance = txns[-1].balance
        calculated_closing = (
            round(reported_opening + sum(t.credit for t in txns) - sum(t.debit for t in txns), 2)
        )

        is_verified = len(discrepancies) == 0
        tampering = len(discrepancies) > 0 and any(abs(d["discrepancy"]) > 1.0 for d in discrepancies)

        rec_msg = (
            "100% Mathematical Ledger Match. No balance discrepancies detected."
            if is_verified
            else f"Ledger reconciliation flagged {len(discrepancies)} discrepancies. Balance equation breached."
        )

        result = LedgerVerificationResult(
            is_verified=is_verified,
            total_transactions=len(txns),
            was_reverse_chronological=was_reversed,
            opening_balance=reported_opening,
            closing_balance=closing_balance,
            calculated_closing_balance=calculated_closing,
            discrepancy_count=len(discrepancies),
            discrepancies=discrepancies,
            tampering_suspected=tampering,
            reconciliation_message=rec_msg,
        )

        return txns, result
