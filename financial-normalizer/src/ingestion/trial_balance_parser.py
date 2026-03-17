from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import pandas as pd
import logging
import warnings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Transaction:
    date: datetime
    account: str
    description: str
    amount: float
    entity: Optional[str] = None


class TrialBalanceImbalanceWarning(UserWarning):
    """Raised when debit/credit totals exceed configured tolerance."""

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
    
    def __init__(self, file_path: str, imbalance_tolerance: float = 0.01):
        self.file_path = file_path
        self.imbalance_tolerance = imbalance_tolerance
        
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

        invalid_amount_rows = df['amount'].isna().sum()
        if invalid_amount_rows:
            logger.warning(f"Dropping {invalid_amount_rows} rows with invalid amount values")
            df = df[df['amount'].notna()].copy()
        
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
            imbalance = total_debits - total_credits
            if abs(imbalance) > self.imbalance_tolerance:
                warning_message = self._build_imbalance_warning(df, total_debits, total_credits, imbalance)
                logger.warning(warning_message)
                warnings.warn(warning_message, TrialBalanceImbalanceWarning)
        
        return transactions

    def _build_imbalance_warning(
        self,
        df: pd.DataFrame,
        total_debits: float,
        total_credits: float,
        imbalance: float,
    ) -> str:
        """Create detailed imbalance warning with top contributing accounts."""
        contribution_df = df.copy()
        contribution_df['line_imbalance'] = contribution_df['debit'].fillna(0) - contribution_df['credit'].fillna(0)
        contribution_df['abs_line_imbalance'] = contribution_df['line_imbalance'].abs()

        top_rows = contribution_df.sort_values('abs_line_imbalance', ascending=False).head(5)
        contributors = []
        for _, row in top_rows.iterrows():
            account = str(row.get('account', 'UNKNOWN'))
            description = str(row.get('description', 'UNKNOWN'))
            line_imbalance = float(row.get('line_imbalance', 0.0))
            contributors.append(f"{account} ({description}): {line_imbalance:,.2f}")

        contributor_text = "; ".join(contributors) if contributors else "No contributing accounts identified"
        return (
            "FORMAL IMBALANCE WARNING | "
            f"Debits={total_debits:,.2f}, Credits={total_credits:,.2f}, "
            f"Imbalance={imbalance:,.2f}, Tolerance={self.imbalance_tolerance:,.2f}. "
            f"Contributing accounts: {contributor_text}. "
            "Recommended action: review source trial balance data and correct unmatched entries before normalization."
        )
    
    def _map_columns(self, columns: pd.Index) -> dict:
        column_map = {}
        for standard_name, variations in self.COLUMN_MAPPINGS.items():
            for col in columns:
                if col in variations:
                    column_map[col] = standard_name
                    break
        return column_map
