"""
Master Orchestrator Engine for Bank Forensics & Credit Underwriting.
Coordinates PDF extraction, normalization, forensic rule application, and credit underwriting.
"""

from __future__ import annotations
import json
import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union
from bank_forensics.forensic_rules import ForensicRulesEngine
from bank_forensics.models import (
    StatementMetadata,
    Transaction,
    UnderwritingReport,
)
from bank_forensics.normalizer import TransactionNormalizer
from bank_forensics.pdf_extractor import PDFExtractor
from bank_forensics.templates import BankTemplateEngine
from bank_forensics.underwriter import CreditUnderwriter


class CustomJSONEncoder(json.JSONEncoder):
    """Encodes dates, datetimes, and Pydantic-compatible objects to JSON."""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return super().default(obj)


class BankForensicsEngine:
    """
    Production-grade deterministic forensic bank statement analyzer & credit underwriting engine.
    """

    def __init__(self):
        pass

    def analyze_pdf(self, pdf_path: str) -> UnderwritingReport:
        """
        End-to-end processing of a bank statement PDF.
        Returns fully typed UnderwritingReport.
        """
        extractor = PDFExtractor(pdf_path)
        metadata, raw_rows, _ = extractor.extract()
        return self.analyze_raw_data(metadata, raw_rows)

    def analyze_raw_data(
        self, metadata: StatementMetadata, raw_rows: List[Dict[str, Any]]
    ) -> UnderwritingReport:
        """
        Processes parsed statement rows through normalization, forensics, and underwriting.
        """
        # 1. Normalization & Ledger Math Verification
        normalizer = TransactionNormalizer(metadata)
        txns, ledger_audit = normalizer.normalize(raw_rows)

        # 2. Forensic Rules
        forensic_engine = ForensicRulesEngine(txns)
        wallet_res, spec_res, bounce_res, emi_res = forensic_engine.run_all()

        # 3. Underwriting Matrix & Memorandum
        underwriter = CreditUnderwriter(
            metadata=metadata,
            transactions=txns,
            ledger_audit=ledger_audit,
            wallet_analysis=wallet_res,
            speculative_analysis=spec_res,
            bounce_analysis=bounce_res,
            emi_analysis=emi_res,
        )
        metrics, verdict, memo = underwriter.evaluate()

        forensics_dict = {
            "wallet_rotation": wallet_res.model_dump(),
            "speculative_risk": spec_res.model_dump(),
            "bounce_forensics": bounce_res.model_dump(),
            "emi_default_analysis": emi_res.model_dump(),
        }

        return UnderwritingReport(
            metadata=metadata,
            ledger_audit=ledger_audit,
            forensics=forensics_dict,
            financial_metrics=metrics,
            verdict=verdict,
            transactions=txns,
            memorandum_markdown=memo,
        )

    def generate_json_output(self, report: UnderwritingReport, indent: int = 2) -> str:
        """Serializes UnderwritingReport to formatted JSON string."""
        data = report.model_dump()
        return json.dumps(data, cls=CustomJSONEncoder, indent=indent)

    def export_results(
        self,
        report: UnderwritingReport,
        json_output_path: str,
        memo_output_path: Optional[str] = None,
        html_output_path: Optional[str] = None,
    ) -> None:
        """Exports JSON payload, Markdown Memorandum, and interactive HTML viewer to disk."""
        os.makedirs(os.path.dirname(os.path.abspath(json_output_path)), exist_ok=True)
        json_str = self.generate_json_output(report)
        with open(json_output_path, "w", encoding="utf-8") as f:
            f.write(json_str)

        if memo_output_path:
            os.makedirs(os.path.dirname(os.path.abspath(memo_output_path)), exist_ok=True)
            with open(memo_output_path, "w", encoding="utf-8") as f:
                f.write(report.memorandum_markdown)

        if html_output_path:
            os.makedirs(os.path.dirname(os.path.abspath(html_output_path)), exist_ok=True)
            html_content = self.generate_html_dashboard(report)
            with open(html_output_path, "w", encoding="utf-8") as f:
                f.write(html_content)

    def generate_html_dashboard(self, report: UnderwritingReport) -> str:
        """Renders an interactive, standalone HTML forensic dashboard with colored transaction tags."""
        v = report.verdict
        m = report.financial_metrics
        meta = report.metadata
        audit = report.ledger_audit

        badge_color = {
            "APPROVE": "#10B981",
            "MANUAL_REVIEW": "#F59E0B",
            "REJECT": "#EF4444",
        }.get(v.decision.value, "#6B7280")

        rows_html = []
        for t in report.transactions:
            tag_badges = []
            if t.tags.is_salary:
                tag_badges.append('<span style="background:#D1FAE5;color:#065F46;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;">SALARY</span>')
            if t.tags.is_bounce:
                tag_badges.append('<span style="background:#FEE2E2;color:#991B1B;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;">BOUNCE</span>')
            if t.tags.is_gambling:
                tag_badges.append('<span style="background:#FFEDD5;color:#9A3412;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;">GAMBLING</span>')
            if t.tags.is_wallet_rotation:
                tag_badges.append('<span style="background:#EDE9FE;color:#5B21B6;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;">CC ROTATION</span>')
            if t.tags.is_emi:
                tag_badges.append('<span style="background:#DBEAFE;color:#1E40AF;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;">EMI / MANDATE</span>')
            if t.tags.is_speculative:
                tag_badges.append('<span style="background:#FEF3C7;color:#92400E;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;">SPECULATIVE</span>')
            if t.tags.is_partial_recovery:
                tag_badges.append('<span style="background:#FEF9C3;color:#854D0E;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;">PARTIAL REC</span>')
            if t.tags.is_penalty:
                tag_badges.append('<span style="background:#FCE7F3;color:#9D174D;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;">PENALTY</span>')
            if t.tags.is_cash_deposit:
                tag_badges.append('<span style="background:#CCFBF1;color:#115E59;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;">CASH DEP</span>')

            tags_str = " ".join(tag_badges) or '<span style="color:#9CA3AF;font-size:11px;">GENERAL</span>'
            row_bg = "#FEF2F2" if (t.tags.is_bounce or t.tags.is_wallet_rotation) else ("#F0FDF4" if t.tags.is_salary else "#FFFFFF")

            rows_html.append(f"""
            <tr style="background:{row_bg};border-bottom:1px solid #E5E7EB;">
                <td style="padding:10px 12px;font-family:monospace;font-size:12px;">{t.txn_id}</td>
                <td style="padding:10px 12px;white-space:nowrap;font-size:12px;">{t.date}</td>
                <td style="padding:10px 12px;font-size:12px;">{t.narration}</td>
                <td style="padding:10px 12px;text-align:right;color:#DC2626;font-family:monospace;font-size:12px;">{'₹' + f'{t.debit:,.2f}' if t.debit > 0 else '-'}</td>
                <td style="padding:10px 12px;text-align:right;color:#059669;font-family:monospace;font-size:12px;">{'₹' + f'{t.credit:,.2f}' if t.credit > 0 else '-'}</td>
                <td style="padding:10px 12px;text-align:right;font-family:monospace;font-weight:600;font-size:12px;">₹{t.balance:,.2f}</td>
                <td style="padding:10px 12px;">{tags_str}</td>
            </tr>
            """)

        table_rows_str = "\n".join(rows_html)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Forensic Underwriting Dashboard - {meta.customer_name}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background:#F9FAFB; color:#1F2937; margin:0; padding:24px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .card {{ background:white; border-radius:10px; border:1px solid #E5E7EB; box-shadow:0 1px 3px rgba(0,0,0,0.05); padding:24px; margin-bottom:20px; }}
        .header-title {{ display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #E5E7EB; padding-bottom:16px; margin-bottom:16px; }}
        .badge {{ background:{badge_color}; color:white; padding:6px 16px; border-radius:20px; font-weight:700; font-size:14px; letter-spacing:0.5px; }}
        .grid-4 {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:16px; margin-bottom:16px; }}
        .stat-box {{ background:#F3F4F6; border-radius:8px; padding:14px; }}
        .stat-label {{ font-size:12px; color:#6B7280; text-transform:uppercase; font-weight:600; margin-bottom:4px; }}
        .stat-val {{ font-size:20px; font-weight:700; color:#111827; }}
        table {{ width:100%; border-collapse:collapse; margin-top:12px; }}
        th {{ background:#F9FAFB; padding:10px 12px; text-align:left; font-size:11px; text-transform:uppercase; color:#6B7280; border-bottom:2px solid #E5E7EB; }}
    </style>
</head>
<body>
<div class="container">
    <div class="card">
        <div class="header-title">
            <div>
                <h1 style="margin:0;font-size:22px;color:#111827;">FORENSIC UNDERWRITING DOSSIER</h1>
                <p style="margin:4px 0 0;font-size:13px;color:#6B7280;">Borrower: <b>{meta.customer_name}</b> | Account: <code>{meta.account_number}</code> ({meta.bank_name})</p>
            </div>
            <div>
                <span class="badge">{v.decision.value}</span>
            </div>
        </div>

        <div class="grid-4">
            <div class="stat-box">
                <div class="stat-label">Risk Grade & Score</div>
                <div class="stat-val">{v.risk_grade.value} <span style="font-size:14px;color:#6B7280;">({v.credit_score}/900)</span></div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Calculated FOIR</div>
                <div class="stat-val">{m.foir_percentage:.1f}%</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Net Monthly Salary</div>
                <div class="stat-val">₹{m.average_net_monthly_salary:,.2f}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Ledger Audit</div>
                <div class="stat-val" style="color:{'#10B981' if audit.is_verified else '#EF4444'}; font-size:16px;">{'100% MATCH' if audit.is_verified else 'DISCREPANCY'}</div>
            </div>
        </div>

        <div style="margin-top:16px;background:#FEF2F2;border-left:4px solid #EF4444;padding:12px 16px;border-radius:4px;display:{'block' if v.hard_rejection_reasons else 'none'};">
            <b style="color:#991B1B;font-size:13px;">Hard Rejection Policies Triggered:</b>
            <ul style="margin:6px 0 0;padding-left:20px;color:#7F1D1D;font-size:13px;">
                {''.join(f'<li>{r}</li>' for r in v.hard_rejection_reasons)}
            </ul>
        </div>
    </div>

    <div class="card">
        <h2 style="margin:0 0 12px;font-size:16px;color:#111827;">Normalized Ledger Transactions & Visual Highlight Tags</h2>
        <table>
            <thead>
                <tr>
                    <th>Txn ID</th>
                    <th>Date</th>
                    <th>Narration</th>
                    <th style="text-align:right;">Debit</th>
                    <th style="text-align:right;">Credit</th>
                    <th style="text-align:right;">Balance</th>
                    <th>Visual Forensic Tags</th>
                </tr>
            </thead>
            <tbody>
                {table_rows_str}
            </tbody>
        </table>
    </div>
</div>
</body>
</html>"""
        return html
