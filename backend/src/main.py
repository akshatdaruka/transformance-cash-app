import os
import json
import shutil
from typing import List, Optional
from datetime import date

from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
import pandas as pd

# Database Imports
from src.database import engine, get_db, Base
from src import models_db

# Parsers
from src.parsers.ai_parser import UniversalAIParser
from src.parsers.template_parser import TemplateParser
from src.models import RemittanceAdvice

# Initialize Database Tables
Base.metadata.create_all(bind=engine)

app = FastAPI()

# CORS Config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models for API Requests ---
class VerificationRequest(BaseModel):
    invoice_id: int
    correct_invoice_number: str
    correct_date: str
    correct_amount: float
    vendor_name: str

# --- Endpoints ---

@app.get("/")
def read_root():
    return {"status": "API is running"}

@app.get("/api/invoices")
def get_invoices(db: Session = Depends(get_db)):
    """
    Fetch all invoices from the Database to show in the UI Table.
    """
    invoices = db.query(models_db.Invoice).all()
    # Convert DB objects to a list of dicts for the frontend
    results = []
    for inv in invoices:
        results.append({
            "id": inv.id,
            "vendor": inv.vendor_id, # Simplified for now
            "invoice_number": inv.invoice_number,
            "date": inv.date,
            "total_amount": inv.total_amount,
            "is_verified": inv.is_verified
        })
    return results

@app.post("/api/upload/remittance")
async def upload_remittance(
    file: UploadFile = File(...),
    use_ai: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    SMART ROUTER: Checks DB for rules -> Uses AI or Template -> Saves Draft.
    """
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Step 1: Detect Vendor (Simulated for Demo)
        detected_vendor_name = "Bike Team GmbH" 
        
        vendor = db.query(models_db.Vendor).filter(models_db.Vendor.name == detected_vendor_name).first()

        method = "ai"
        remittance = None
        
        # Step 2: The Decision Logic
        if vendor and vendor.extraction_rules:
            print(f"🧠 MEMORY: Found rules for {vendor.name}. Skipping AI.")
            parser = TemplateParser(rules=vendor.extraction_rules)
            remittance = parser.parse(temp_path)
            method = "template"
        else:
            print(f"🤖 UNKNOWN: No rules for {detected_vendor_name}. Using AI.")
            parser = UniversalAIParser()
            remittance = parser.parse(temp_path)
            method = "ai"

        # Step 3: Save 'Draft' to Database
        if not vendor:
            vendor = models_db.Vendor(name=remittance.sender_name or detected_vendor_name)
            db.add(vendor)
            db.commit()
            db.refresh(vendor)

        db_invoice = models_db.Invoice(
            vendor_id=vendor.id,
            invoice_number=remittance.lines[0].invoice_number if remittance.lines else "UNKNOWN",
            date=remittance.lines[0].date if remittance.lines else None,
            total_amount=float(remittance.total_amount) if remittance.total_amount else 0.0,
            currency=remittance.currency,
            is_verified=False,
            raw_data=json.loads(remittance.json())
        )
        
        db.add(db_invoice)
        db.commit()
        db.refresh(db_invoice)
        
        print(f"✅ Invoice Saved with ID: {db_invoice.id} (Method: {method})")

        return {
            "status": "success",
            "method": method, 
            "db_id": db_invoice.id,
            "data": remittance
        }

    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.post("/api/invoices/verify")
async def verify_and_learn(
    data: VerificationRequest,
    db: Session = Depends(get_db)
):
    """
    THE LEARNING LOOP: Updates Invoice & Saves Rules.
    """
    invoice = db.query(models_db.Invoice).filter(models_db.Invoice.id == data.invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    invoice.invoice_number = data.correct_invoice_number
    invoice.total_amount = data.correct_amount
    invoice.is_verified = True
    db.commit()
    
    original_ai_number = invoice.raw_data.get('lines', [{}])[0].get('invoice_number', '')
    
    if original_ai_number != data.correct_invoice_number:
        print("🧠 LEARNING: AI got the Invoice Number wrong. Saving correction rule.")
        vendor = db.query(models_db.Vendor).filter(models_db.Vendor.id == invoice.vendor_id).first()
        
        new_rules = vendor.extraction_rules or {}
        new_rules["use_template"] = True
        new_rules["invoice_format"] = "DD.MM.YYYY" # Mock rule for demo
        
        vendor.extraction_rules = new_rules
        db.commit()
        return {"message": "Verified & Rule Learned!", "learned": True}

    return {"message": "Verified (No new rules needed)", "learned": False}

@app.get("/api/reconcile")
def reconcile_transactions(db: Session = Depends(get_db)):
    """
    The Matching Engine:
    Finds Bank Transactions that match Invoice Amounts within a date range.
    """
    # 1. Fetch Unmatched Items
    # In a real app, filtering would be stricter (is_verified=True)
    invoices = db.query(models_db.Invoice).filter(models_db.Invoice.is_verified == True).all()
    statements = db.query(models_db.BankStatement).filter(models_db.BankStatement.matched_invoice_id == None).all()
    
    matches = []
    
    # 2. Simple Exact Match Algorithm (Demo Logic)
    # We look for exact Amount match +/- 1.00 EUR tolerance
    
    for stmt in statements:
        best_match = None
        
        for inv in invoices:
            # Check 1: Amount Match (with tolerance)
            delta = abs(stmt.amount - inv.total_amount)
            if delta < 1.00:
                # Check 2: Date Logic (Payment usually after Invoice)
                # (Skipping strictly for demo simplicity)
                best_match = inv
                break # Found a match!
        
        if best_match:
            # 3. Save the Match to DB
            stmt.matched_invoice_id = best_match.id
            db.commit()
            
            matches.append({
                "statement_id": stmt.id,
                "invoice_id": best_match.id,
                "amount": stmt.amount,
                "invoice_number": best_match.invoice_number,
                "status": "matched"
            })
            
    return {
        "status": "success",
        "matches_found": len(matches),
        "details": matches
    }

@app.post("/api/upload/bank")
async def upload_bank_statement(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        # 1. Load Data
        if file.filename.endswith('.csv'):
            # Use sep=None to auto-detect ; vs ,
            df = pd.read_csv(temp_path, sep=None, engine='python')
        else:
            df = pd.read_excel(temp_path)

        # 2. Smart Column Mapping (The Fix)
        # We look for keywords instead of hardcoding index 0 or 1
        amount_col = None
        date_col = None
        ref_col = None

        # Normalize headers to lowercase to find matches
        df.columns = df.columns.str.lower().str.strip()

        for col in df.columns:
            if any(x in col for x in ['betrag', 'amount', 'value', 'umsatz']):
                amount_col = col
            elif any(x in col for x in ['datum', 'date', 'valuta']):
                date_col = col
            elif any(x in col for x in ['verwendungszweck', 'ref', 'desc', 'details']):
                ref_col = col

        # Fallback if detection fails (Index 0=Date, Index 1=Ref, Index 2=Amount)
        if not amount_col: amount_col = df.columns[2] if len(df.columns) > 2 else df.columns[-1]
        if not date_col: date_col = df.columns[0]
        if not ref_col: ref_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]

        saved_count = 0
        for _, row in df.iterrows():
            try:
                # Clean the Amount (Handle "1.000,00" German format)
                raw_amount = str(row[amount_col])
                if ',' in raw_amount and '.' in raw_amount:
                     # Remove thousands separator (.) and replace decimal (,) with (.)
                    raw_amount = raw_amount.replace('.', '').replace(',', '.')
                elif ',' in raw_amount:
                    raw_amount = raw_amount.replace(',', '.')
                
                final_amount = float(raw_amount)

                # Clean the Date
                raw_date = str(row[date_col])
                try:
                    txn_date = pd.to_datetime(raw_date, dayfirst=True).date()
                except:
                    txn_date = date.today()

                stmt = models_db.BankStatement(
                    transaction_date=txn_date,
                    amount=final_amount,
                    reference_text=str(row[ref_col])
                )
                db.add(stmt)
                saved_count += 1
            except Exception as row_e:
                print(f"Skipping bad row: {row_e}")
                continue
            
        db.commit()
        return {"message": f"Successfully uploaded {saved_count} transactions"}
        
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)