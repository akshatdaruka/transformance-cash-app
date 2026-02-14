import pandas as pd
from src.models import BankTransaction
from decimal import Decimal

def load_bank_statement(file_path: str) -> list[BankTransaction]:
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path)
    
    transactions = []
    for _, row in df.iterrows():
        try:
            # Handle M/D/YYYY format (2/3/2014)
            dt = pd.to_datetime(row['Buchungsdatum'], dayfirst=False).date()
            
            raw_amt = str(row['Betrag'])
            # Clean amount string
            if ',' in raw_amt and '.' in raw_amt:
                amt = Decimal(raw_amt.replace(',', '')) 
            else:
                amt = Decimal(raw_amt)

            txn = BankTransaction(
                date=dt,
                amount=amt,
                sender=str(row['Auftraggeber/Empfänger']),
                reference=str(row['Referenz']),
                currency=str(row['Währung'])
            )
            transactions.append(txn)
        except Exception as e:
            continue
            
    return transactions