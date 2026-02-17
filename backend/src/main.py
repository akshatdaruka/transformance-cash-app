import sys
import os
from contextlib import asynccontextmanager

# Add the current directory to sys.path so imports work correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
import shutil
import tempfile
from typing import List

# --- Internal Imports ---
from src.database import init_db, engine, get_session
from src.models_db import BankFormatConfig, VendorConfig
from src.routes import config
from src.ingestion import load_bank_statement
from src.parsers.bike_team import BikeTeamParser
from src.parsers.ai_parser import UniversalAIParser
from src.matcher import ReconciliationEngine
from src.models import BankTransaction, RemittanceAdvice

# Load .env file
load_dotenv()

# --- Lifecycle Manager (Startup/Shutdown) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Create Tables
    print("Creating Database Tables...")
    init_db()

    # 2. Seed Default Data (Check if empty first)
    with Session(engine) as session:
        # Seed Bank Config
        if not session.exec(select(BankFormatConfig)).first():
            print("Seeding Default Bank Config...")
            default_bank = BankFormatConfig(
                name="Deutsche Bank CSV",
                date_col="Buchungsdatum",
                amount_col="Betrag",
                sender_col="Auftraggeber/Empfänger",
                reference_col="Referenz",
                currency_col="Währung",
                delimiter=",",
                date_format="%d.%m.%Y"
            )
            session.add(default_bank)
        
        # Seed Vendor Config
        if not session.exec(select(VendorConfig)).first():
            print("Seeding Default Vendor Config...")
            default_vendor = VendorConfig(
                name="Bike Team GmbH",
                identifier_keyword="Bike Team",
                total_label="Zahlbetrag",
                table_start_keyword="Pos.",
                currency="EUR"
            )
            session.add(default_vendor)
        
        session.commit()

    yield

# --- App Definition ---
app = FastAPI(title="Transformance API", lifespan=lifespan)

# Allow React (localhost:5173) to talk to Python (localhost:8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register the Configuration Router
app.include_router(config.router)

# --- In-Memory State (Session) ---
db = {
    "transactions": [],
    "remittance": None
}

# --- Helper Functions ---
def save_upload(upload_file: UploadFile) -> str:
    try:
        suffix = os.path.splitext(upload_file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(upload_file.file, tmp)
            return tmp.name
    except Exception as e:
        raise HTTPException(500, f"Save failed: {e}")

# --- Endpoints ---

@app.post("/api/upload/bank")
async def upload_bank(file: UploadFile = File(...)):
    path = save_upload(file)
    try:
        # DYNAMIC FETCH: Get the default Bank Config from DB
        with Session(engine) as session:
            # In a real app, user would select this from a dropdown
            bank_config = session.exec(select(BankFormatConfig).where(BankFormatConfig.name == "Deutsche Bank CSV")).first()
            
        if not bank_config:
            # Fallback (Safety net)
            print("Warning: DB Config missing, using hardcoded fallback.")
            # You might want to raise an error here in production
        
        print(f"Using Bank Config: {bank_config.name if bank_config else 'Fallback'}")

        # Pass config to ingestion
        txns = load_bank_statement(path, bank_config)
        
        # Store in "Session DB"
        db["transactions"] = txns
        return {"message": "Success", "count": len(txns), "data": [t.model_dump() for t in txns]}
    except Exception as e:
        raise HTTPException(400, str(e))
    finally:
        os.unlink(path)

@app.post("/api/upload/remittance")
async def upload_remittance(file: UploadFile = File(...), use_ai: bool = False):
    path = save_upload(file)
    try:
        if use_ai:
            print("Using AI Parser with Dynamic Config...")
            
            # DYNAMIC FETCH: Get the "Bike Team" config
            # In production, we would run OCR first to find "Bike Team" text, then query DB.
            # For this MVP, we assume it matches the default vendor.
            with Session(engine) as session:
                vendor_conf = session.exec(select(VendorConfig).where(VendorConfig.name == "Bike Team GmbH")).first()
            
            if vendor_conf:
                print(f"Loaded Vendor Rules: Look for Total '{vendor_conf.total_label}'")
            
            parser = UniversalAIParser(vendor_config=vendor_conf)
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
            "lines": [l.model_dump() for l in remittance.lines]
        }
    except Exception as e:
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