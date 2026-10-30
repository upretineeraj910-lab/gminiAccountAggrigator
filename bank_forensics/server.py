"""
FastAPI Web Server for Drag & Drop Bank Statement Forensics & Underwriting Console.
Provides REST APIs for PDF analysis, sample execution, and serves the reactive frontend UI.
"""

from __future__ import annotations
import os
import shutil
import tempfile
from typing import Any, Dict
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from bank_forensics.engine import BankForensicsEngine, CustomJSONEncoder
from bank_forensics.sample_generator import generate_all_samples

app = FastAPI(
    title="Bank Statement Forensics & Underwriting Engine API",
    description="Deterministic forensic underwriting API for Indian bank statements.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ENGINE = BankForensicsEngine()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE_DIR, "web")
SAMPLES_DIR = os.path.join(BASE_DIR, "samples")

# Ensure samples exist
if not os.path.exists(os.path.join(SAMPLES_DIR, "pnb_statement_reverse_chronology.pdf")):
    generate_all_samples(SAMPLES_DIR)


@app.get("/")
async def serve_index():
    """Serves the reactive drag-and-drop web frontend."""
    index_path = os.path.join(WEB_DIR, "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="Frontend index.html not found.")
    return FileResponse(index_path, media_type="text/html")


@app.post("/api/analyze")
async def analyze_statement(file: UploadFile = File(...)):
    """
    Accepts uploaded bank statement PDF via Drag & Drop,
    extracts metadata, resolves reverse chronology, validates ledger balance equation,
    evaluates forensic risk rules, and returns full underwriting JSON.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files (.pdf) are supported.")

    # Save to secure temporary file
    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, file.filename)

    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Run forensic underwriting engine
        report = ENGINE.analyze_pdf(temp_file_path)
        payload = report.model_dump(mode="json")
        return JSONResponse(content=payload)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forensic Analysis Error: {str(e)}")
    finally:
        # Cleanup temporary files
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.get("/api/sample/{sample_name}")
async def analyze_sample(sample_name: str):
    """
    1-Click test endpoint for preset bank statement scenarios:
    - 'pnb': Reverse chronology + Credit Card rotation + Bounce -> REJECT
    - 'hdfc': Prime salaried clean ledger -> APPROVE
    - 'sbi': High cash deposit & zero balance days -> MANUAL_REVIEW
    - 'tampered': Mathematical ledger breach -> REJECT
    """
    sample_files = {
        "pnb": "pnb_statement_reverse_chronology.pdf",
        "hdfc": "hdfc_statement_prime_salaried.pdf",
        "sbi": "sbi_statement_cash_stress.pdf",
        "tampered": "tampered_ledger_breach.pdf",
    }

    if sample_name not in sample_files:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown sample scenario '{sample_name}'. Available: {list(sample_files.keys())}",
        )

    pdf_path = os.path.join(SAMPLES_DIR, sample_files[sample_name])
    if not os.path.exists(pdf_path):
        generate_all_samples(SAMPLES_DIR)

    try:
        report = ENGINE.analyze_pdf(pdf_path)
        payload = report.model_dump(mode="json")
        return JSONResponse(content=payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sample Evaluation Failed: {str(e)}")


def start_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Launches the Uvicorn web server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
