"""
Synthetic Indian Bank Statement PDF Generator.
Generates pixel-perfect PDFs with authentic headers, metadata blocks, and transaction grids
for PNB, HDFC, SBI, and tampered statements to test forensic underwriting rules.
"""

from __future__ import annotations
import os
from typing import Any, Dict, List, Optional
import pymupdf


class StatementPDFBuilder:
    """Helper to draw professional bank statement PDFs using PyMuPDF."""

    def __init__(self, filename: str):
        self.filename = filename
        self.doc = pymupdf.open()
        self.page = self.doc.new_page(width=595, height=842)  # A4 standard points
        self.cursor_y = 40

    def draw_header(
        self,
        bank_name: str,
        tagline: str,
        customer_name: str,
        account_no: str,
        account_type: str,
        ifsc: str,
        branch: str,
        period: str,
        opening_bal: float,
        closing_bal: float,
    ) -> None:
        """Draws the statement header and metadata table."""
        p = self.page

        # Bank Banner
        p.draw_rect(pymupdf.Rect(35, self.cursor_y, 560, self.cursor_y + 40), color=(0.1, 0.2, 0.5), fill=(0.1, 0.2, 0.5))
        p.insert_text((45, self.cursor_y + 25), bank_name.upper(), fontsize=14, color=(1, 1, 1), fontname="helv")
        p.insert_text((380, self.cursor_y + 25), tagline, fontsize=9, color=(0.9, 0.9, 0.9), fontname="helv")
        self.cursor_y += 50

        # Metadata Block
        p.draw_rect(pymupdf.Rect(35, self.cursor_y, 560, self.cursor_y + 80), color=(0.7, 0.7, 0.7), width=0.5)

        # Left Column Metadata
        p.insert_text((45, self.cursor_y + 16), f"Customer Name: {customer_name}", fontsize=9, fontname="helv")
        p.insert_text((45, self.cursor_y + 32), f"Account Number: {account_no}", fontsize=9, fontname="helv")
        p.insert_text((45, self.cursor_y + 48), f"Account Type: {account_type}", fontsize=9, fontname="helv")
        p.insert_text((45, self.cursor_y + 64), f"Branch Name: {branch}", fontsize=9, fontname="helv")

        # Right Column Metadata
        p.insert_text((330, self.cursor_y + 16), f"IFSC Code: {ifsc}", fontsize=9, fontname="helv")
        p.insert_text((330, self.cursor_y + 32), f"Statement Period: {period}", fontsize=9, fontname="helv")
        p.insert_text((330, self.cursor_y + 48), f"Opening Balance: INR {opening_bal:,.2f}", fontsize=9, fontname="helv")
        p.insert_text((330, self.cursor_y + 64), f"Closing Balance: INR {closing_bal:,.2f}", fontsize=9, fontname="helv")

        self.cursor_y += 95

    def draw_table(
        self,
        headers: List[str],
        col_widths: List[float],
        rows: List[List[str]],
    ) -> None:
        """Draws grid table with column headers and rows."""
        start_x = 35
        row_height = 20
        total_width = sum(col_widths)

        # Draw Table Header Row
        header_y = self.cursor_y
        self.page.draw_rect(
            pymupdf.Rect(start_x, header_y, start_x + total_width, header_y + row_height),
            color=(0.2, 0.3, 0.6),
            fill=(0.2, 0.3, 0.6),
        )

        curr_x = start_x
        for i, h in enumerate(headers):
            self.page.insert_text(
                (curr_x + 4, header_y + 14),
                h,
                fontsize=8,
                color=(1, 1, 1),
                fontname="helv",
            )
            curr_x += col_widths[i]

        self.cursor_y += row_height

        # Draw Table Rows
        for r_idx, row in enumerate(rows):
            # Check page overflow
            if self.cursor_y > 800:
                self.page = self.doc.new_page(width=595, height=842)
                self.cursor_y = 40

            row_y = self.cursor_y
            # Background alternate shading
            fill_col = (0.96, 0.96, 0.96) if r_idx % 2 == 1 else (1.0, 1.0, 1.0)
            self.page.draw_rect(
                pymupdf.Rect(start_x, row_y, start_x + total_width, row_y + row_height),
                color=(0.8, 0.8, 0.8),
                fill=fill_col,
                width=0.4,
            )

            curr_x = start_x
            for c_idx, cell in enumerate(row):
                # Draw vertical separator line
                self.page.draw_line(
                    pymupdf.Point(curr_x, row_y),
                    pymupdf.Point(curr_x, row_y + row_height),
                    color=(0.8, 0.8, 0.8),
                    width=0.4,
                )
                cell_text = str(cell)[:45]  # avoid clipping
                self.page.insert_text(
                    (curr_x + 3, row_y + 13),
                    cell_text,
                    fontsize=7.5,
                    color=(0.1, 0.1, 0.1),
                    fontname="helv",
                )
                curr_x += col_widths[c_idx]

            # Right border
            self.page.draw_line(
                pymupdf.Point(curr_x, row_y),
                pymupdf.Point(curr_x, row_y + row_height),
                color=(0.8, 0.8, 0.8),
                width=0.4,
            )

            self.cursor_y += row_height

    def save(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.filename)), exist_ok=True)
        self.doc.save(self.filename)
        self.doc.close()


def generate_pnb_reverse_statement(output_path: str) -> None:
    """
    Generates realistic PNB ONE e-Statement with REVERSE chronological order,
    containing:
    - Wallet PPIW rotation loop into Credit Card bill payment within 48h
    - Inward NACH mandate bounce with ₹295 penalty charge
    - Broken internal loan recovery (₹160.63)
    - High-frequency gambling (>2 times/month)
    - Speculative stock F&O trading
    """
    builder = StatementPDFBuilder(output_path)
    builder.draw_header(
        bank_name="PUNJAB NATIONAL BANK",
        tagline="PNB ONE E-STATEMENT",
        customer_name="VIKRAM SHARMA",
        account_no="0145000100234567",
        account_type="SAVINGS",
        ifsc="PUNB0014500",
        branch="CONNAUGHT PLACE NEW DELHI",
        period="01/10/2026 To 25/10/2026",
        opening_bal=35000.00,
        closing_bal=43194.37,
    )

    headers = ["Date", "Narration", "Chq No", "Debit", "Credit", "Balance"]
    col_widths = [60, 210, 45, 70, 70, 70]

    # Chronological sequence
    txns = [
        ["01/10/2026", "TREASURY WBEP GOVT SALARY OCT 2026", "", "0.00", "85,000.00", "120,000.00"],
        ["02/10/2026", "UPI/DR/MOBIKWIK/PPIW ADD MONEY/WALLET", "", "50,000.00", "0.00", "70,000.00"],
        ["03/10/2026", "UPI/CR/MOBIKWIK PPIW WALLET CASH OUT", "", "0.00", "50,000.00", "120,000.00"],
        ["04/10/2026", "UPI/DR/billpay.axb@upi/CCBILLPAY AXIS CARD", "", "49,500.00", "0.00", "70,500.00"],
        ["05/10/2026", "ACH RTN/BAJAJ FINANCE/MANDATE REJECT/UNPAID", "", "0.00", "0.00", "70,500.00"],
        ["05/10/2026", "ECS RETURN CHRG/GST INCL/PENALTY", "", "295.00", "0.00", "70,205.00"],
        ["07/10/2026", "LN REC DL REC SWEEP PARTIAL RECOVERY", "", "160.63", "0.00", "70,044.37"],
        ["10/10/2026", "UPI/DR/DREAM11/CONTEST ENTRY/GAMING", "", "2,500.00", "0.00", "67,544.37"],
        ["14/10/2026", "UPI/DR/DREAM11/CONTEST ENTRY/GAMING", "", "3,000.00", "0.00", "64,544.37"],
        ["18/10/2026", "UPI/DR/DREAM11/CONTEST ENTRY/GAMING", "", "4,000.00", "0.00", "60,544.37"],
        ["20/10/2026", "UPI/DR/ZERODHA BROKING LTD/MARGIN FUNDING", "", "15,000.00", "0.00", "45,544.37"],
        ["25/10/2026", "POS GROCERY STORE SWIPE NEW DELHI", "", "2,350.00", "0.00", "43,194.37"],
    ]

    # Invert rows to reverse chronological order as PNB ONE issues them
    reverse_rows = list(reversed(txns))
    builder.draw_table(headers, col_widths, reverse_rows)
    builder.save()


def generate_hdfc_prime_statement(output_path: str) -> None:
    """
    Generates clean HDFC Bank statement for a prime salaried applicant.
    - Regular corporate salary (Infosys)
    - Prudent home loan obligation (FOIR ~26%)
    - Zero bounces, zero gambling, zero rotation
    - Result: APPROVE (A1_PRIME)
    """
    builder = StatementPDFBuilder(output_path)
    builder.draw_header(
        bank_name="HDFC BANK",
        tagline="ACCOUNT STATEMENT",
        customer_name="ANANYA IYER",
        account_no="50100248912345",
        account_type="SAVINGS",
        ifsc="HDFC0000123",
        branch="BANDRA KURLA COMPLEX MUMBAI",
        period="01/09/2026 To 31/10/2026",
        opening_bal=60000.00,
        closing_bal=250001.00,
    )

    headers = ["Date", "Narration", "Chq/Ref No", "Value Dt", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"]
    col_widths = [50, 190, 50, 50, 60, 60, 65]

    rows = [
        ["01/09/2026", "CMS/SAL/INFOSYS LTD/SEP 2026/SALARY", "SAL9082", "01/09/2026", "0.00", "145,000.00", "205,000.00"],
        ["05/09/2026", "ACH/HDFC HOME LOAN EMI/HL90812", "ACH4412", "05/09/2026", "38,000.00", "0.00", "167,000.00"],
        ["10/09/2026", "ELECTRICITY BILL TATA POWER MUMBAI", "UPI1298", "10/09/2026", "4,500.00", "0.00", "162,500.00"],
        ["15/09/2026", "SUPERMARKET SPEND POS RELIANCE FRESH", "POS7781", "15/09/2026", "12,000.00", "0.00", "150,500.00"],
        ["01/10/2026", "CMS/SAL/INFOSYS LTD/OCT 2026/SALARY", "SAL9182", "01/10/2026", "0.00", "145,000.00", "295,500.00"],
        ["05/10/2026", "ACH/HDFC HOME LOAN EMI/HL90812", "ACH4512", "05/10/2026", "38,000.00", "0.00", "257,500.00"],
        ["12/10/2026", "BROADBAND AIRTEL FIBER BILL", "UPI3991", "12/10/2026", "1,499.00", "0.00", "256,001.00"],
        ["25/10/2026", "DINING OUT POS TAJ LANDS END", "POS8891", "25/10/2026", "6,000.00", "0.00", "250,001.00"],
    ]

    builder.draw_table(headers, col_widths, rows)
    builder.save()


def generate_sbi_cash_stress_statement(output_path: str) -> None:
    """
    Generates SBI statement triggering MANUAL_REVIEW:
    - Cash deposits exceed 40% of inflows
    - Zero balance days > 5 days in month
    """
    builder = StatementPDFBuilder(output_path)
    builder.draw_header(
        bank_name="STATE BANK OF INDIA",
        tagline="ONLINE SBI E-STATEMENT",
        customer_name="RAJESH PATEL",
        account_no="30981234567",
        account_type="SAVINGS",
        ifsc="SBIN0004567",
        branch="AHMEDABAD MAIN BRANCH",
        period="01/10/2026 To 31/10/2026",
        opening_bal=5000.00,
        closing_bal=7050.00,
    )

    headers = ["Txn Date", "Narration", "Ref No", "Debit", "Credit", "Balance"]
    col_widths = [60, 220, 50, 65, 65, 65]

    rows = [
        ["01/10/2026", "NEFT/SAL/SMALL ENTERPRISES SALARY", "NEFT9081", "0.00", "40,000.00", "45,000.00"],
        ["02/10/2026", "CASH DEP CDM BR 04567 AHMEDABAD", "CDM1102", "0.00", "70,000.00", "115,000.00"],
        ["05/10/2026", "ACH/IDFC FIRST BANK EMI", "ACH8871", "22,000.00", "0.00", "93,000.00"],
        ["08/10/2026", "ATM CASH WITHDRAWAL AHMEDABAD", "ATM4412", "92,950.00", "0.00", "50.00"],
        ["14/10/2026", "UPI/CR/FRIEND TRANSFER PAYEE", "UPI5501", "0.00", "10,000.00", "10,050.00"],
        ["28/10/2026", "STORE PAYMENT HARDWARE MART", "UPI6612", "3,000.00", "0.00", "7,050.00"],
    ]

    builder.draw_table(headers, col_widths, rows)
    builder.save()


def generate_tampered_statement(output_path: str) -> None:
    """
    Generates statement with an edited balance breaching mathematical continuity:
    Expected Balance = Balance_{i-1} + Credit - Debit
    """
    builder = StatementPDFBuilder(output_path)
    builder.draw_header(
        bank_name="STATE BANK OF INDIA",
        tagline="ONLINE SBI STATEMENT",
        customer_name="FORGED APPLICANT",
        account_no="30981999999",
        account_type="SAVINGS",
        ifsc="SBIN0004567",
        branch="DELHI CANTT",
        period="01/10/2026 To 15/10/2026",
        opening_bal=10000.00,
        closing_bal=150000.00,
    )

    headers = ["Txn Date", "Narration", "Ref No", "Debit", "Credit", "Balance"]
    col_widths = [60, 220, 50, 65, 65, 65]

    rows = [
        ["01/10/2026", "OPENING BALANCE B/F", "", "0.00", "0.00", "10,000.00"],
        ["05/10/2026", "UPI/CR/TRANSFER FROM RELATIVE", "UPI1234", "0.00", "5,000.00", "15,000.00"],
        # Tampered row below: previous bal 15,000, debit 2,000 => should be 13,000, but forged to 1,50,000!
        ["10/10/2026", "POS SHOPPING MALL SPEND", "POS9912", "2,000.00", "0.00", "150,000.00"],
    ]

    builder.draw_table(headers, col_widths, rows)
    builder.save()


def generate_all_samples(samples_dir: str = "samples") -> Dict[str, str]:
    """Generates all synthetic bank statement PDFs."""
    os.makedirs(samples_dir, exist_ok=True)
    paths = {
        "pnb_reverse": os.path.join(samples_dir, "pnb_statement_reverse_chronology.pdf"),
        "hdfc_prime": os.path.join(samples_dir, "hdfc_statement_prime_salaried.pdf"),
        "sbi_cash_stress": os.path.join(samples_dir, "sbi_statement_cash_stress.pdf"),
        "tampered": os.path.join(samples_dir, "tampered_ledger_breach.pdf"),
    }

    generate_pnb_reverse_statement(paths["pnb_reverse"])
    generate_hdfc_prime_statement(paths["hdfc_prime"])
    generate_sbi_cash_stress_statement(paths["sbi_cash_stress"])
    generate_tampered_statement(paths["tampered"])

    return paths


if __name__ == "__main__":
    generated = generate_all_samples()
    print("Generated statement PDFs:")
    for k, p in generated.items():
        print(f"  {k}: {p}")
