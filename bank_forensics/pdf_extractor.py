"""
Deterministic PDF Extraction Engine.
Extracts transaction tables and header metadata from messy Indian bank statement PDFs.
Handles multi-line narration stitching and column alignment.
"""

from __future__ import annotations
import os
import re
from typing import Any, Dict, List, Optional, Tuple
import pdfplumber
import pymupdf
from bank_forensics.models import StatementMetadata
from bank_forensics.templates import (
    BankTemplateEngine,
    clean_amount,
    parse_indian_date,
)


class PDFExtractionError(Exception):
    """Custom exception raised when statement PDF parsing fails."""
    pass


class PDFExtractor:
    """
    Dual-engine deterministic PDF extractor (pdfplumber + PyMuPDF)
    specialized for Indian banking formats.
    """

    def __init__(self, pdf_path: str):
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF statement not found at: {pdf_path}")
        self.pdf_path = pdf_path

    def extract(self) -> Tuple[StatementMetadata, List[Dict[str, Any]], str]:
        """
        Main extraction entry point.
        Returns:
            - StatementMetadata: extracted header info
            - List of raw transaction dicts: {date_str, value_date_str, narration, chq_ref, debit, credit, balance}
            - Full extracted text for audit trail
        """
        full_text = self._extract_full_text()
        metadata = BankTemplateEngine.extract_metadata(full_text)

        # First attempt: pdfplumber table extraction
        raw_rows = self._extract_tables_with_pdfplumber()

        # Fallback if no table rows found: PyMuPDF line-by-line parsing
        if not raw_rows:
            raw_rows = self._extract_lines_with_pymupdf()

        if not raw_rows:
            raise PDFExtractionError("Failed to extract transaction rows from bank statement PDF.")

        return metadata, raw_rows, full_text

    def _extract_full_text(self) -> str:
        """Extract text from all pages using PyMuPDF for speed and accuracy."""
        doc = pymupdf.open(self.pdf_path)
        all_text = []
        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                all_text.append(page.get_text())
        finally:
            doc.close()
        return "\n".join(all_text)

    def _extract_tables_with_pdfplumber(self) -> List[Dict[str, Any]]:
        """Extract table rows using pdfplumber with column mapping & multi-line stitching."""
        raw_transactions: List[Dict[str, Any]] = []
        col_mapping: Optional[Dict[str, int]] = None

        with pdfplumber.open(self.pdf_path) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                if not tables:
                    tables = page.extract_tables(
                        table_settings={
                            "vertical_strategy": "text",
                            "horizontal_strategy": "text",
                            "snap_tolerance": 5,
                        }
                    )
                if not tables:
                    continue

                for table in tables:
                    for row in table:
                        if not row or all(cell is None or str(cell).strip() == "" for cell in row):
                            continue

                        # Check if this row is a header row
                        header_candidate = [str(c).strip().lower() for c in row if c is not None]
                        has_date = any("date" in c for c in header_candidate)
                        has_bal = any("bal" in c for c in header_candidate)
                        has_amt = any(any(k in c for k in ["debit", "credit", "withdrawal", "deposit", "amount"]) for c in header_candidate)

                        if has_date and (has_bal or has_amt):
                            # Update or set column mapping
                            col_mapping = BankTemplateEngine.map_columns([str(c or "") for c in row])
                            continue

                        if not col_mapping:
                            # If row starts with a valid date, infer column mapping directly from data structure
                            if row and parse_indian_date(str(row[0] or "").strip()):
                                col_mapping = BankTemplateEngine.infer_columns_from_data(row)
                            else:
                                continue

                        # Extract row using column mapping
                        self._process_table_row(row, col_mapping, raw_transactions)

        return raw_transactions

    def _process_table_row(
        self,
        row: List[Any],
        col_mapping: Dict[str, int],
        raw_transactions: List[Dict[str, Any]],
    ) -> None:
        """Process a single table row, stitching multi-line narrations when needed."""
        def get_val(key: str) -> str:
            idx = col_mapping.get(key)
            if idx is not None and idx < len(row) and row[idx] is not None:
                return str(row[idx]).strip()
            return ""

        date_str = get_val("date")
        value_date_str = get_val("value_date")
        narration = get_val("narration")
        chq_ref = get_val("chq_ref")
        debit_str = get_val("debit")
        credit_str = get_val("credit")
        balance_str = get_val("balance")

        # Check if this is a primary transaction row (must have a valid date or non-zero amount)
        parsed_dt = parse_indian_date(date_str) if date_str else None
        has_amount = bool(debit_str or credit_str or balance_str)

        if parsed_dt and (has_amount or balance_str):
            # This is a new transaction row
            raw_transactions.append({
                "date_str": date_str,
                "value_date_str": value_date_str,
                "narration": narration,
                "chq_ref": chq_ref,
                "debit_str": debit_str,
                "credit_str": credit_str,
                "balance_str": balance_str,
            })
        elif raw_transactions and narration:
            # Multi-line narration continuation: stitch to the previous transaction's narration
            prev_txn = raw_transactions[-1]
            prev_txn["narration"] = (prev_txn["narration"] + " " + narration).strip()
            if chq_ref and not prev_txn["chq_ref"]:
                prev_txn["chq_ref"] = chq_ref

    def _extract_lines_with_pymupdf(self) -> List[Dict[str, Any]]:
        """Fallback line-by-line extractor for unstructured or non-grid PDFs."""
        raw_transactions: List[Dict[str, Any]] = []
        doc = pymupdf.open(self.pdf_path)

        date_pattern = re.compile(r"\b(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})\b")
        # Amount pattern: e.g., 1,500.00 or 50000.00
        amount_pattern = re.compile(r"\b\d{1,3}(?:,\d{2,3})*(?:\.\d{2})\b")

        try:
            for page in doc:
                text = page.get_text("text")
                lines = [line.strip() for line in text.split("\n") if line.strip()]

                for line in lines:
                    dates_found = date_pattern.findall(line)
                    if not dates_found:
                        if raw_transactions and len(line) > 3:
                            # Continuation narration
                            raw_transactions[-1]["narration"] += " " + line
                        continue

                    # Found date, look for amounts
                    amounts_found = amount_pattern.findall(line)
                    if len(amounts_found) >= 2:
                        # At least balance + one of debit/credit
                        date_str = dates_found[0]
                        # Remove matched date and amounts to isolate narration
                        narr_part = line
                        narr_part = date_pattern.sub("", narr_part)
                        for amt in amounts_found:
                            narr_part = narr_part.replace(amt, "")
                        narr_part = re.sub(r"\s+", " ", narr_part).strip()

                        # If 3 amounts: debit, credit, balance OR chq, debit/credit, balance
                        if len(amounts_found) == 3:
                            raw_transactions.append({
                                "date_str": date_str,
                                "value_date_str": "",
                                "narration": narr_part,
                                "chq_ref": "",
                                "debit_str": amounts_found[0],
                                "credit_str": amounts_found[1],
                                "balance_str": amounts_found[2],
                            })
                        elif len(amounts_found) == 2:
                            # Typically one txn amount + balance
                            raw_transactions.append({
                                "date_str": date_str,
                                "value_date_str": "",
                                "narration": narr_part,
                                "chq_ref": "",
                                "debit_str": amounts_found[0],
                                "credit_str": "0.00",
                                "balance_str": amounts_found[1],
                            })
        finally:
            doc.close()

        return raw_transactions
