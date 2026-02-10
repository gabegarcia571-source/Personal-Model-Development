from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Transaction:
    date: datetime
    account: str
    description: str
    amount: float
    entity: Optional[str] = None

class TrialBalanceParser:
    COLUMN_MAPPINGS = {
        'account': ['account', 'account name', 'gl account', 'account_name'],
        'description': ['description', 'memo', 'narrative', 'detail'],
        'debit': ['debit', 'dr', 'debits'],
        'credit': ['credit', 'cr', 'credits'],
        'amount': ['amount', 'value'],
        'date': ['date', 'period', 'month', 'posting_date'],
        'entity': ['entity', 'company', 'legal_entity']
    }
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        
    def parse(self) -> List[Transaction]:
        logger.info(f"Parsing file: {self.file_path}")
        
        # Read file
        if self.file_path.endswith('.csv'):
            df = pd.read_csv(self.file_path)
        elif self.file_path.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(self.file_path)
        else:
            raise ValueError(f"Unsupported file format: {self.file_path}")
        
        # Normalize column names
        df.columns = df.columns.str.lower().str.strip()
        
        # Map columns
        column_map = self._map_columns(df.columns)
        df = df.rename(columns=column_map)
        
        # Validate required columns
        required = ['account', 'description']
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        
        # Handle amount calculations
        if 'amount' not in df.columns:
            if 'debit' in df.columns and 'credit' in df.columns:
                df['debit'] = pd.to_numeric(df['debit'], errors='coerce').fillna(0)
                df['credit'] = pd.to_numeric(df['credit'], errors='coerce').fillna(0)
                df['amount'] = df['debit'] - df['credit']
            else:
                raise ValueError("No amount, debit, or credit columns found")
        else:
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        
        # Parse dates
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
        else:
            df['date'] = datetime.now()
        
        # Convert to Transaction objects
        transactions = []
        for _, row in df.iterrows():
            tx = Transaction(
                date=row.get('date', datetime.now()),
                account=str(row['account']),
                description=str(row['description']),
                amount=float(row['amount']),
                entity=str(row['entity']) if 'entity' in df.columns and pd.notna(row.get('entity')) else None
            )
            
            # Flag suspicious amounts
            if abs(tx.amount) > 10_000_000:
                logger.warning(f"Large transaction detected: {tx.amount:,.2f} - {tx.description}")
            
            transactions.append(tx)
        
        logger.info(f"Loaded {len(transactions)} transactions")
        
        # Validate balance (if debits/credits exist)
        if 'debit' in df.columns and 'credit' in df.columns:
            total_debits = df['debit'].sum()
            total_credits = df['credit'].sum()
            if abs(total_debits - total_credits) > 0.01:
                logger.warning(f"Debits ({total_debits:,.2f}) and Credits ({total_credits:,.2f}) don't balance")
        
        return transactions
    
    def _map_columns(self, columns: pd.Index) -> dict:
        column_map = {}
        for standard_name, variations in self.COLUMN_MAPPINGS.items():
            for col in columns:
                if col in variations:
                    column_map[col] = standard_name
                    break
        return column_map
