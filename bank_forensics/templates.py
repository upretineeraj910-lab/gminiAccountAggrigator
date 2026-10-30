"""
Multi-Bank Template Engine & Metadata Extraction Module.
Detects issuing Indian bank, parses header metadata, and normalizes variable column layouts.
"""

from __future__ import annotations
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
from bank_forensics.models import StatementMetadata


def parse_indian_date(date_str: str) -> Optional[date]:
    """Parse various Indian banking date formats deterministically."""
    if not date_str:
        return None
    cleaned = date_str.strip()
    # Normalize month names or delimiters
    formats = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%d-%b-%Y",
        "%d-%b-%y",
        "%d %b %Y",
        "%d %b %y",
        "%d-%B-%Y",
        "%d %B %Y",
        "%Y-%m-%d",
        "%Y/%m/%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    # Try regex match for day-month-year
    m = re.search(r"(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})", cleaned)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if year < 100:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            pass
    return None


def clean_amount(val: Any) -> float:
    """Clean and parse Indian currency amounts with commas, signs, and Cr/Dr notations."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s or s in ("-", "--", "NA", "N/A", "Nil", "nil", ""):
        return 0.0

    is_cr = bool(re.search(r"(?i)\bcr\b", s))
    is_dr = bool(re.search(r"(?i)\bdr\b", s))

    # Strip currency symbols, commas, non-numeric except dot and minus
    cleaned = re.sub(r"[₹Rs\.\s,INRcrCRdrDR]", "", s)
    # If string was like 1,500.50, after removing commas and symbols we keep decimal point
    cleaned = re.sub(r"[^\d\.\-]", "", s.replace(",", "").replace("₹", "").replace("Rs.", "").replace("INR", ""))
    
    # Clean multiple dots
    parts = cleaned.split(".")
    if len(parts) > 2:
        cleaned = "".join(parts[:-1]) + "." + parts[-1]

    try:
        amt = float(cleaned)
        return abs(amt)
    except ValueError:
        return 0.0


class BankTemplate:
    """Base specification for bank statement layouts."""
    bank_code: str = "GENERIC"
    bank_name: str = "Generic Indian Bank"
    ifsc_prefix: str = ""
    is_reverse_chronological_default: bool = False

    # Regex patterns for metadata
    account_regex = r"(?:Account\s*No|A\/C\s*No|Account\s*Number|A\/c\s*Number|Acc\s*No)[\s\.:]*([X\d]{9,18})"
    customer_regex = r"(?:Customer\s*Name|Account\s*Name|Name\s*of\s*Account\s*Holder|Name)[\s\.:]*(?:Mr\.|Mrs\.|Ms\.|Shri|Smt)?\s*([A-Za-z\s\.]{2,40}?)(?=\s*(?:\bIFSC\b|\bBranch\b|\bAccount\b|\bA\/c\b|\bMICR\b|\bDate\b|\bPeriod\b|\bTel\b|\bAddress\b|\n|$))"
    ifsc_regex = r"(?:IFSC\s*Code|IFSC|RTGS\/NEFT\s*IFSC)[\s\.:]*([A-Z]{4}0[A-Z0-9]{6})"
    branch_regex = r"(?:Branch\s*Name|Branch)[\s\.:]*([A-Za-z0-9\s,\.\-]{3,60}?)(?=\s*(?:\bIFSC\b|\bMICR\b|\bTel\b|\bPin\b|\bDate\b|\bClosing\b|\bOpening\b|\bPeriod\b|\n|$))"
    period_regex = r"(?:Statement\s*Period|Period|From\s*Date)[\s\.:]*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})\s*(?:to|To|\-)\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})"
    opening_bal_regex = r"(?:Opening\s*Balance|B\/F|Op\s*Bal|Balance\s*B\/F)[\s\.:INR₹]*([0-9,]+\.?\d*)"
    closing_bal_regex = r"(?:Closing\s*Balance|Cl\s*Bal|Balance\s*C\/F)[\s\.:INR₹]*([0-9,]+\.?\d*)"

    # Header column names to internal standard field mapping
    column_mappings: Dict[str, str] = {
        "date": "date",
        "value date": "value_date",
        "narration": "narration",
        "chq ref": "chq_ref",
        "debit": "debit",
        "credit": "credit",
        "balance": "balance",
    }


class PNBTemplate(BankTemplate):
    bank_code = "PNB"
    bank_name = "Punjab National Bank"
    ifsc_prefix = "PUNB"
    is_reverse_chronological_default = True  # PNB ONE statement lists newest first
    account_regex = r"(?:Account\s*Number|A\/c\s*No|Account\s*No)[\s\.:]*([0-9]{13,16})"


class SBITemplate(BankTemplate):
    bank_code = "SBI"
    bank_name = "State Bank of India"
    ifsc_prefix = "SBIN"
    is_reverse_chronological_default = False
    account_regex = r"(?:Account\s*Number|A\/c\s*No)[\s\.:]*([0-9]{10,13})"


class HDFCTemplate(BankTemplate):
    bank_code = "HDFC"
    bank_name = "HDFC Bank"
    ifsc_prefix = "HDFC"
    is_reverse_chronological_default = False
    account_regex = r"(?:Account\s*No\.?|A\/c\s*No\.?)[\s\.:]*([0-9]{14})"


class ICICITemplate(BankTemplate):
    bank_code = "ICICI"
    bank_name = "ICICI Bank"
    ifsc_prefix = "ICIC"
    is_reverse_chronological_default = False
    account_regex = r"(?:Account\s*Number|A\/c\s*No\.?)[\s\.:]*([0-9]{12})"


class AxisTemplate(BankTemplate):
    bank_code = "AXIS"
    bank_name = "Axis Bank"
    ifsc_prefix = "UTIB"
    is_reverse_chronological_default = False
    account_regex = r"(?:Account\s*No\.?|A\/c\s*No\.?)[\s\.:]*([0-9]{15})"


class CanaraTemplate(BankTemplate):
    bank_code = "CANARA"
    bank_name = "Canara Bank"
    ifsc_prefix = "CNRB"
    is_reverse_chronological_default = False
    account_regex = r"(?:Account\s*Number|A\/c\s*No\.?)[\s\.:]*([0-9]{13,14})"


class BankTemplateEngine:
    """Registry and engine to auto-detect bank and extract header metadata."""

    TEMPLATES: List[BankTemplate] = [
        PNBTemplate(),
        SBITemplate(),
        HDFCTemplate(),
        ICICITemplate(),
        AxisTemplate(),
        CanaraTemplate(),
    ]
    GENERIC_TEMPLATE = BankTemplate()

    @classmethod
    def detect_bank(cls, header_text: str) -> BankTemplate:
        """Deterministically detect bank from statement header text or IFSC pattern."""
        text_upper = header_text.upper()

        # Check by IFSC code pattern first
        ifsc_match = re.search(r"\b([A-Z]{4})0[A-Z0-9]{6}\b", text_upper)
        if ifsc_match:
            prefix = ifsc_match.group(1)
            for tmpl in cls.TEMPLATES:
                if tmpl.ifsc_prefix and tmpl.ifsc_prefix == prefix:
                    return tmpl

        # Check by bank brand names in header
        if "PUNJAB NATIONAL BANK" in text_upper or "PNB ONE" in text_upper or "PNB" in text_upper:
            return PNBTemplate()
        if "STATE BANK OF INDIA" in text_upper or "ONLINESBI" in text_upper or "SBI" in text_upper:
            return SBITemplate()
        if "HDFC BANK" in text_upper or "HDFC" in text_upper:
            return HDFCTemplate()
        if "ICICI BANK" in text_upper or "ICICI" in text_upper:
            return ICICITemplate()
        if "AXIS BANK" in text_upper or "UTI BANK" in text_upper:
            return AxisTemplate()
        if "CANARA BANK" in text_upper:
            return CanaraTemplate()

        return cls.GENERIC_TEMPLATE

    @classmethod
    def extract_metadata(cls, text: str) -> StatementMetadata:
        """Extract header metadata from statement text."""
        tmpl = cls.detect_bank(text)
        metadata = StatementMetadata(
            bank_name=tmpl.bank_name,
            bank_code=tmpl.bank_code,
        )

        # Account number
        acc_m = re.search(tmpl.account_regex, text, re.IGNORECASE)
        if acc_m:
            metadata.account_number = acc_m.group(1).strip()
        else:
            # Fallback general account pattern
            gen_acc = re.search(r"\b\d{9,18}\b", text)
            if gen_acc:
                metadata.account_number = gen_acc.group(0)

        # Account type
        acc_type_m = re.search(r"(?:Account\s*Type|A\/c\s*Type)[\s\.:]*([A-Za-z\s]+)", text, re.IGNORECASE)
        if acc_type_m:
            raw_type = acc_type_m.group(1).strip().upper()
            if "SAVING" in raw_type:
                metadata.account_type = "SAVINGS"
            elif "CURRENT" in raw_type:
                metadata.account_type = "CURRENT"
            elif "OVERDRAFT" in raw_type or "OD" in raw_type:
                metadata.account_type = "OVERDRAFT"
            elif "SALARY" in raw_type:
                metadata.account_type = "SALARY"

        # Customer name
        cust_m = re.search(tmpl.customer_regex, text, re.IGNORECASE)
        if cust_m:
            cname = cust_m.group(1).strip().rstrip(".,")
            # Filter out non-names like 'Address', 'Branch', etc.
            if not any(token in cname.upper() for token in ["BRANCH", "IFSC", "STATEMENT", "ACCOUNT", "BANK"]):
                metadata.customer_name = cname

        # IFSC code
        ifsc_m = re.search(tmpl.ifsc_regex, text, re.IGNORECASE)
        if ifsc_m:
            metadata.ifsc_code = ifsc_m.group(1).strip().upper()
        else:
            gen_ifsc = re.search(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", text)
            if gen_ifsc:
                metadata.ifsc_code = gen_ifsc.group(0).upper()

        # Branch
        br_m = re.search(tmpl.branch_regex, text, re.IGNORECASE)
        if br_m:
            bname = br_m.group(1).strip().rstrip(".,\n")
            if not any(k in bname.upper() for k in ["IFSC", "STATEMENT", "PAGE", "ACCOUNT"]):
                metadata.branch = bname

        # Period / Date range
        period_m = re.search(tmpl.period_regex, text, re.IGNORECASE)
        if period_m:
            metadata.start_date = parse_indian_date(period_m.group(1))
            metadata.end_date = parse_indian_date(period_m.group(2))

        # Opening balance
        op_m = re.search(tmpl.opening_bal_regex, text, re.IGNORECASE)
        if op_m:
            metadata.opening_balance = clean_amount(op_m.group(1))

        # Closing balance
        cl_m = re.search(tmpl.closing_bal_regex, text, re.IGNORECASE)
        if cl_m:
            metadata.closing_balance = clean_amount(cl_m.group(1))

        return metadata

    @classmethod
    def map_columns(cls, header_row: List[str]) -> Dict[str, int]:
        """
        Dynamically map table column indices to standard schema:
        ['date', 'value_date', 'narration', 'chq_ref', 'debit', 'credit', 'balance']
        Handles both multi-cell headers and single-cell merged header strings.
        """
        mapping: Dict[str, int] = {}
        cleaned_cells = [str(c or "").strip() for c in header_row]

        # Case: Header was merged into a single cell, e.g. ['Date Narration Chq No Debit Credit Balance', None, ...]
        non_empty = [c for c in cleaned_cells if c]
        if len(non_empty) == 1 and len(cleaned_cells) > 1:
            header_str = non_empty[0].lower()
            # If 6 columns: date, narration, chq_ref, debit, credit, balance
            if len(cleaned_cells) == 6:
                if "chq" in header_str or "ref" in header_str:
                    return {"date": 0, "narration": 1, "chq_ref": 2, "debit": 3, "credit": 4, "balance": 5}
                else:
                    return {"date": 0, "value_date": 1, "narration": 2, "debit": 3, "credit": 4, "balance": 5}
            elif len(cleaned_cells) == 7:
                # date, narration, chq_ref, value_dt, debit, credit, balance (e.g. HDFC)
                return {"date": 0, "narration": 1, "chq_ref": 2, "value_date": 3, "debit": 4, "credit": 5, "balance": 6}
            elif len(cleaned_cells) == 5:
                # date, narration, debit, credit, balance
                return {"date": 0, "narration": 1, "debit": 2, "credit": 3, "balance": 4}

        for idx, col in enumerate(header_row):
            if not col:
                continue
            c = str(col).strip().lower()
            
            # Date detection
            if any(k in c for k in ["txn date", "tran date", "transaction date", "post date"]):
                mapping["date"] = idx
            elif "value date" in c or "val dt" in c or "val date" in c:
                mapping["value_date"] = idx
            elif "date" in c and "date" not in mapping:
                mapping["date"] = idx

            # Narration / Description detection
            elif any(k in c for k in ["narration", "description", "particulars", "details", "remarks"]):
                mapping["narration"] = idx

            # Cheque / Ref number detection
            elif any(k in c for k in ["chq no", "cheque", "ref no", "chq/ref", "utr", "instrument"]):
                mapping["chq_ref"] = idx

            # Debit / Withdrawal detection
            elif any(k in c for k in ["withdrawal", "debit", "dr amt", "dr amount", "dr."]):
                mapping["debit"] = idx

            # Credit / Deposit detection
            elif any(k in c for k in ["deposit", "credit", "cr amt", "cr amount", "cr."]):
                mapping["credit"] = idx

            # Balance detection
            elif any(k in c for k in ["closing balance", "balance", "bal (inr)", "clear bal", "bal."]):
                mapping["balance"] = idx

        return mapping

    @classmethod
    def infer_columns_from_data(cls, sample_row: List[Any]) -> Dict[str, int]:
        """Infers column positions directly from sample data row values when headers are absent."""
        mapping: Dict[str, int] = {}
        num_cols = len(sample_row)

        if num_cols == 7:
            return {"date": 0, "narration": 1, "chq_ref": 2, "value_date": 3, "debit": 4, "credit": 5, "balance": 6}
        elif num_cols == 6:
            return {"date": 0, "narration": 1, "chq_ref": 2, "debit": 3, "credit": 4, "balance": 5}
        elif num_cols == 5:
            return {"date": 0, "narration": 1, "debit": 2, "credit": 3, "balance": 4}

        # Dynamic scan
        for idx, val in enumerate(sample_row):
            s = str(val or "").strip()
            if not s:
                continue
            if parse_indian_date(s) and "date" not in mapping:
                mapping["date"] = idx
            elif len(s) > 15 and not re.search(r"^[\d,\.\s]+$", s) and "narration" not in mapping:
                mapping["narration"] = idx

        # Default last col to balance
        if "balance" not in mapping and num_cols >= 3:
            mapping["balance"] = num_cols - 1
        if "credit" not in mapping and num_cols >= 4:
            mapping["credit"] = num_cols - 2
        if "debit" not in mapping and num_cols >= 5:
            mapping["debit"] = num_cols - 3

        return mapping
