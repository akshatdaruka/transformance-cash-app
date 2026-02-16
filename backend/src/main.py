import sys
import os
# Add the current directory to sys.path so imports work correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.parsers.ai_parser import UniversalAIParser
from dotenv import load_dotenv

# Load .env file
load_dotenv()

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import shutil
import tempfile
from typing import List

# Import your core logic
from src.ingestion import load_bank_statement
from src.parsers.bike_team import BikeTeamParser
from src.matcher import ReconciliationEngine
from src.models import BankTransaction, RemittanceAdvice

app = FastAPI(title="Transformance API")

# Allow React (localhost:5173) to talk to Python (localhost:8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev only. In prod, specify domain.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage (simulating a database for this session)
# This resets if you restart the server.
db = {
    "transactions": [],
    "remittance": None
}

def save_upload(upload_file: UploadFile) -> str:
    try:
        suffix = os.path.splitext(upload_file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(upload_file.file, tmp)
            return tmp.name
    except Exception as e:
        raise HTTPException(500, f"Save failed: {e}")

@app.post("/api/upload/bank")
async def upload_bank(file: UploadFile = File(...)):
    path = save_upload(file)
    try:
        txns = load_bank_statement(path)
        # Store in "DB"
        db["transactions"] = txns
        return {"message": "Success", "count": len(txns), "data": [t.model_dump() for t in txns]}
    except Exception as e:
        raise HTTPException(400, str(e))
    finally:
        os.unlink(path)

@app.post("/api/upload/remittance")
async def upload_remittance(file: UploadFile = File(...), use_ai: bool = False): # <--- Added param
    path = save_upload(file)
    try:
        if use_ai:
            print("Using AI Parser...")
            parser = UniversalAIParser()
        else:
            print("Using Standard Parser...")
            parser = BikeTeamParser()

        if not parser.can_parse(path):
            raise HTTPException(400, "PDF format not recognized")

        remittance = parser.parse(path)
        db["remittance"] = remittance

        return {
            "message": "Success", 
            "total": remittance.total_amount,
            "lines": [l.model_dump() for l in remittance.lines],
            "is_math_valid": remittance.is_math_valid,
            "calculated_total": remittance.calculated_total
        }
    except Exception as e:
        # Enhanced error logging
        import traceback
        traceback.print_exc()
        raise HTTPException(400, str(e))
    finally:
        if os.path.exists(path):
            os.unlink(path)

@app.post("/api/reconcile")
async def reconcile():
    if not db["transactions"] or not db["remittance"]:
        raise HTTPException(400, "Missing data. Upload both files first.")

    engine = ReconciliationEngine(db["transactions"], [db["remittance"]])
    entries = engine.match_and_generate()

    # Format dates for JSON response
    results = []
    for e in entries:
        row = e.model_dump()
        row['posting_date'] = e.posting_date.strftime('%-m/%-d/%Y')
        row['document_date'] = e.document_date.strftime('%-m/%-d/%Y')
        results.append(row)

    return results