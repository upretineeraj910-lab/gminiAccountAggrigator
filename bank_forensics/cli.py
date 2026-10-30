"""
Command Line Interface (CLI) for Forensic Bank Statement Analyzer & Underwriting Engine.
Enables command-line processing of Indian bank statements, terminal auditing, and export.
"""

from __future__ import annotations
import argparse
import os
import sys
from bank_forensics.engine import BankForensicsEngine
from bank_forensics.models import DecisionVerdict


def main() -> int:
    # Ensure stdout/stderr handles UTF-8 on Windows consoles
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    parser = argparse.ArgumentParser(
        description="Deterministic Forensic Bank Statement Analyzer & Credit Underwriting Engine."
    )
    parser.add_argument("pdf_path", help="Path to Indian bank statement PDF (e.g. PNB, SBI, HDFC).")
    parser.add_argument("-j", "--json", help="Path to export structured JSON payload.")
    parser.add_argument("-m", "--memo", help="Path to export executive Underwriting Memorandum in Markdown.")
    parser.add_argument("-H", "--html", help="Path to export interactive visual HTML dashboard.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose transaction audit log.")

    args = parser.parse_args()

    if not os.path.exists(args.pdf_path):
        print(f"[ERROR] Statement file not found: {args.pdf_path}", file=sys.stderr)
        return 1

    engine = BankForensicsEngine()
    print(f"\n[ENGINE] Ingesting and analyzing: {args.pdf_path}...")
    try:
        report = engine.analyze_pdf(args.pdf_path)
    except Exception as e:
        print(f"[ERROR] Execution failed: {e}", file=sys.stderr)
        return 1

    base_name = os.path.splitext(os.path.basename(args.pdf_path))[0]
    json_path = args.json or f"{base_name}_analysis.json"
    memo_path = args.memo or f"{base_name}_memo.md"
    html_path = args.html or f"{base_name}_dashboard.html"

    engine.export_results(report, json_path, memo_path, html_path)

    # Terminal Executive Summary
    print("=" * 78)
    print(f" FORENSIC CREDIT UNDERWRITING REPORT: {report.metadata.customer_name.upper()} ")
    print("=" * 78)
    print(f"Issuing Bank        : {report.metadata.bank_name} ({report.metadata.bank_code})")
    print(f"Account Number      : {report.metadata.account_number} ({report.metadata.account_type})")
    print(f"IFSC Code           : {report.metadata.ifsc_code} | Branch: {report.metadata.branch}")
    print(f"Statement Span      : {report.metadata.start_date} to {report.metadata.end_date}")
    print(f"Opening -> Closing  : INR {report.ledger_audit.opening_balance:,.2f} -> INR {report.ledger_audit.closing_balance:,.2f}")
    print(f"Ledger Verification : {'PASSED (100% Match)' if report.ledger_audit.is_verified else 'FAILED (Discrepancies)'}")
    print(f"Chronology Reversed : {'YES (Auto-realigned from newest-first)' if report.ledger_audit.was_reverse_chronological else 'NO'}")
    print("-" * 78)

    print("KEY FINANCIAL METRICS & RATIOS:")
    m = report.financial_metrics
    print(f" - Average Monthly Salary  : INR {m.average_net_monthly_salary:,.2f} (Consistency: {m.salary_consistency_score:.2f})")
    print(f" - True Monthly EMIs       : INR {m.total_monthly_obligations:,.2f}")
    print(f" - Calculated FOIR         : {m.foir_percentage:.2f}% (Policy Threshold: <= 50.0%)")
    print(f" - Average Bank Bal (ABB)  : INR {m.average_bank_balance:,.2f}")
    print(f" - Zero Balance Days       : {m.zero_balance_days_count} days")
    print(f" - Cash Deposit Ratio      : {m.cash_inflow_ratio*100:.1f}% (Policy Threshold: <= 40.0%)")
    print("-" * 78)

    print("FORENSIC RISK FINDINGS:")
    w = report.forensics["wallet_rotation"]
    s = report.forensics["speculative_risk"]
    b = report.forensics["bounce_forensics"]
    e = report.forensics["emi_default_analysis"]

    print(f" - Wallet Rotation Loops   : {'SUSPECT FLAG RAISED' if w['flag_raised'] else 'Clean'} (Rotated Vol: INR {w['total_rotated_volume']:,.2f})")
    print(f" - Speculative Outflows    : INR {s['total_speculative_outflow']:,.2f} (Gambling: INR {s['gambling_outflows']:,.2f}, Stocks: INR {s['stock_trading_outflows']:,.2f})")
    print(f" - Delinquency / Bounces   : Inward Chq: {b['inward_cheque_bounces']} | Mandate Bounces: {b['nach_mandate_bounces']} | Penalties: INR {b['total_penalty_fees']:,.2f}")
    print(f" - Deficit Loan Recoveries : {len(e['partial_loan_recoveries'])} event(s) | Missed Mandates: {len(e['missed_mandates'])}")
    print("-" * 78)

    v = report.verdict
    print(f"FINAL CREDIT VERDICT: >>> {v.decision.value} <<< [Grade: {v.risk_grade.value} | Score: {v.credit_score}/900]")
    if v.hard_rejection_reasons:
        print("\nHard Rejections Triggered:")
        for r in v.hard_rejection_reasons:
            print(f"  [X] {r}")
    if v.manual_review_triggers:
        print("\nManual Review Triggers:")
        for r in v.manual_review_triggers:
            print(f"  [!] {r}")
    if v.positive_factors:
        print("\nPositive Mitigants:")
        for p in v.positive_factors:
            print(f"  [+] {p}")

    print("=" * 78)
    print(f"[EXPORT] JSON payload written to        : {json_path}")
    print(f"[EXPORT] Underwriting Memorandum saved to: {memo_path}")
    print(f"[EXPORT] Visual HTML Dashboard saved to  : {html_path}")
    print("=" * 78 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
