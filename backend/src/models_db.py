from typing import Optional
from sqlmodel import SQLModel, Field

class BankFormatConfig(SQLModel, table=True):
    """
    Stores mapping for CSV columns.
    Example: 'Deutsche Bank' -> Date col is 'Buchungstag', Amount col is 'Haben'
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)  # e.g., "Deutsche Bank CSV"
    
    # Columns Names in the CSV
    date_col: str
    amount_col: str
    sender_col: str
    reference_col: str
    currency_col: str
    
    # Formatting (e.g., delimiter ';')
    delimiter: str = ","
    date_format: str = "%d.%m.%Y" # Default German

class VendorConfig(SQLModel, table=True):
    """
    Stores AI Prompt Rules for specific vendors.
    Example: 'Bike Team' -> Look for total labeled 'Zahlbetrag'
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True) # e.g., "Bike Team GmbH"
    identifier_keyword: str # Keyword to find in text to auto-select this profile
    
    # Dynamic Prompt Variables
    total_label: str # e.g., "Zahlbetrag" or "Total Amount"
    table_start_keyword: str # e.g., "Pos." or "Description"
    currency: str = "EUR"