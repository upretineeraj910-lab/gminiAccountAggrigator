"""
1-Click Launcher for Bank Forensics Drag & Drop Web Console.
Starts local FastAPI / Uvicorn server and automatically opens browser at http://127.0.0.1:8000
"""

import socket
import sys
import threading
import time
import webbrowser
import uvicorn
from bank_forensics.server import app

def find_available_port(start_port: int = 8000) -> int:
    port = start_port
    while port < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
        port += 1
    return start_port

def open_browser(port: int):
    time.sleep(1.2)
    url = f"http://127.0.0.1:{port}"
    print(f"\n[LAUNCHER] Opening browser at: {url}")
    webbrowser.open(url)

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    selected_port = find_available_port(8000)

    print("=" * 70)
    print("  BANK STATEMENT FORENSIC UNDERWRITING CONSOLE (WEB UI)")
    print("=" * 70)
    print(f"  Local Server URL : http://127.0.0.1:{selected_port}")
    print("  Features Included:")
    print("   * Drag & Drop any Indian Bank Statement PDF (PNB, SBI, HDFC, etc.)")
    print("   * 1-Click Test Scenarios (PNB Fraud Loop, HDFC Prime, SBI Stress)")
    print("   * Color-Coded Transactions Ledger (Salary, Bounce, Gambling, Rotation)")
    print("   * Real-Time FOIR, ABB, Zero-Balance Days & Decision Verdict")
    print("   * Instant Export to JSON and Underwriting Memorandum (.md)")
    print("=" * 70)

    # Launch browser in separate background thread
    threading.Thread(target=open_browser, args=(selected_port,), daemon=True).start()

    # Start FastAPI server
    uvicorn.run(app, host="127.0.0.1", port=selected_port, log_level="info")
