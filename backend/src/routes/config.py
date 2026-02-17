from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from typing import List

# Import your DB connection and Models
from src.database import get_session
from src.models_db import BankFormatConfig, VendorConfig

router = APIRouter(prefix="/api/config", tags=["Configuration"])

# --- BANK FORMAT ROUTES ---

@router.post("/bank-layout", response_model=BankFormatConfig)
def create_bank_layout(config: BankFormatConfig, session: Session = Depends(get_session)):
    """Save a new Bank CSV mapping configuration."""
    try:
        session.add(config)
        session.commit()
        session.refresh(config)
        return config
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/bank-layout", response_model=List[BankFormatConfig])
def get_bank_layouts(session: Session = Depends(get_session)):
    """List all saved bank layouts."""
    return session.exec(select(BankFormatConfig)).all()

# --- VENDOR RULES ROUTES ---

@router.post("/vendor-rules", response_model=VendorConfig)
def create_vendor_rules(config: VendorConfig, session: Session = Depends(get_session)):
    """Save a new Vendor AI Prompt configuration."""
    try:
        session.add(config)
        session.commit()
        session.refresh(config)
        return config
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/vendor-rules", response_model=List[VendorConfig])
def get_vendor_rules(session: Session = Depends(get_session)):
    """List all saved vendor rules."""
    return session.exec(select(VendorConfig)).all()

@router.get("/vendor-rules/{name}", response_model=VendorConfig)
def get_vendor_rule_by_name(name: str, session: Session = Depends(get_session)):
    """Fetch specific rules for a vendor (used by the AI Engine)."""
    rule = session.exec(select(VendorConfig).where(VendorConfig.name == name)).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Vendor config not found")
    return rule