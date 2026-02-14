from typing import List, Optional
from src.models import BankTransaction, RemittanceAdvice, JournalEntry

class ReconciliationEngine:
    def __init__(self, transactions: List[BankTransaction], remittances: List[RemittanceAdvice]):
        self.transactions = transactions
        self.remittances = remittances

    def match_and_generate(self) -> List[JournalEntry]:
        journal_entries = []

        for remittance in self.remittances:
            match: Optional[BankTransaction] = None
            
            for txn in self.transactions:
                # Absolute value match to handle credit/debit signs
                if abs(txn.amount) == abs(remittance.total_amount):
                    match = txn
                    break
            
            if match:
                for line in remittance.lines:
                    # Construct Item Text: InternalRef/InvoiceRef
                    item_text_val = f"{line.internal_ref}/{line.invoice_number}"
                    
                    je = JournalEntry(
                        company_code="1000",
                        posting_date=match.date,   # Use Bank Date
                        document_date=match.date,  # Use Bank Date
                        document_type="SA",
                        gl_account="100000",
                        amount_credit=line.net_amount,
                        currency=match.currency,
                        item_text=item_text_val
                    )
                    journal_entries.append(je)
            
        return journal_entries