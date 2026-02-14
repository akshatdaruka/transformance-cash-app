from pydantic import BaseModel, Field
from datetime import date
from typing import List
from decimal import Decimal

class BankTransaction(BaseModel):
    """Represents a single row from the Bank Statement"""
    date: date
    amount: Decimal
    sender: str
    reference: str
    currency: str

class InvoiceLine(BaseModel):
    """Represents a single line item from the Remittance PDF"""
    internal_ref: str
    invoice_number: str
    date: date
    gross_amount: Decimal
    net_amount: Decimal

class RemittanceAdvice(BaseModel):
    """Represents the parsed content of a PDF"""
    sender_name: str
    total_amount: Decimal
    lines: List[InvoiceLine]
    currency: str

class JournalEntry(BaseModel):
    """Represents the final output row"""
    company_code: str = "1000"
    posting_date: date
    document_date: date
    document_type: str = "SA"
    gl_account: str = "100000"
    amount_credit: Decimal
    currency: str
    item_text: str