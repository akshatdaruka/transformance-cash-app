import pandas as pd
from src.models import BankTransaction
from src.models_db import BankFormatConfig # <--- Import the DB Model
from decimal import Decimal

def load_bank_statement(file_path: str, config: BankFormatConfig) -> list[BankTransaction]:
    """
    Parses a bank CSV using the dynamic column mapping provided in 'config'.
    """
    # 1. Load Data with the specific delimiter from DB
    if file_path.endswith('.csv'):
        try:
            df = pd.read_csv(file_path, sep=config.delimiter)
        except:
            # Fallback if delimiter is wrong
            df = pd.read_csv(file_path, sep="," if config.delimiter == ";" else ";")
    else:
        df = pd.read_excel(file_path)
    
    transactions = []
    
    # 2. Iterate dynamically
    for _, row in df.iterrows():
        try:
            # DYNAMIC: Use config.date_col instead of hardcoded string
            raw_date = row[config.date_col]
            
            # Handle Date Format (Basic logic)
            # In a full app, you'd use config.date_format with datetime.strptime
            dt = pd.to_datetime(raw_date, dayfirst=True).date()
            
            # DYNAMIC: Use config.amount_col
            raw_amt = str(row[config.amount_col])
            
            # Clean amount string (German/US logic)
            if ',' in raw_amt and '.' in raw_amt:
                amt = Decimal(raw_amt.replace(',', '')) 
            else:
                amt = Decimal(raw_amt.replace(',', '.'))

            # DYNAMIC: Map other fields
            txn = BankTransaction(
                date=dt,
                amount=amt,
                sender=str(row.get(config.sender_col, "Unknown")),
                reference=str(row.get(config.reference_col, "N/A")),
                currency=str(row.get(config.currency_col, "EUR"))
            )
            transactions.append(txn)
        except Exception as e:
            # print(f"Skipping row: {e}")
            continue
            
    return transactions