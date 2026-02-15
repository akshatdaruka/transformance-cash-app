from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, JSON, Boolean, Text
from sqlalchemy.orm import relationship
from src.database import Base

class Vendor(Base):
    __tablename__ = "vendors"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    
    # THE BRAIN: This column stores the learned rules (Regex, coordinates, etc.)
    # If this is not Null, we skip AI and use these rules.
    extraction_rules = Column(JSON, nullable=True) 

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=True)
    
    # Core Data
    invoice_number = Column(String, index=True)
    date = Column(Date, nullable=True)
    total_amount = Column(Float, default=0.0)
    currency = Column(String, default="EUR")
    
    # Status Tracking
    is_verified = Column(Boolean, default=False)  # False = AI Guess, True = Human Confirmed
    
    # Full AI Dump (So we can re-train later)
    raw_data = Column(JSON, nullable=True)

class BankStatement(Base):
    __tablename__ = "bank_statements"

    id = Column(Integer, primary_key=True, index=True)
    transaction_date = Column(Date)
    amount = Column(Float)
    reference_text = Column(String) # "Payment for Inv 38000383"
    
    # Matching Logic
    matched_invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)