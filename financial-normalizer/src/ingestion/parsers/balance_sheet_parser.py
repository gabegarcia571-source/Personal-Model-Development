"""
Balance Sheet Parser

INPUT FORMAT:
Expected CSV with columns like:
- Account: Asset accounts (Cash, AR, Inventory, PPE) or Liability/Equity accounts
- Balance: Numeric amount
- Category: Asset, Liability, or Equity (optional but helpful)
- Entity (optional, defaults to 'Unknown')
- Date (optional, defaults to today)

EXTRACTS:
Maps balance sheet accounts to GL entries with their balances.
Each account becomes a separate GL entry classified as asset, liability, or equity.

OUTPUT SCHEMA (required for ClassificationEngine.classify_dataframe()):
- Account_Code: Auto-generated from account name (e.g., "BS_CASH", "BS_AR")
- Account_Name: Account name from balance sheet
- Amount: Balance amount
- Entity: Entity name
- Period: Derived from date (YYYY-MM-DD)
- Date: Balance sheet date

DOWNSTREAM:
Output DataFrame feeds directly into ClassificationEngine.classify_dataframe()
No modifications should be made to classifier.py
"""

import pandas as pd
from datetime import datetime
from typing import Optional


def parse_balance_sheet(file_path: str,
                       entity: str = "Unknown",
                       date: str = None) -> pd.DataFrame:
    """
    Parse a balance sheet CSV into the internal schema.

    Args:
        file_path: Path to CSV containing balance sheet accounts
        entity: Entity name (optional, defaults to 'Unknown')
        date: Balance sheet date (optional, defaults to today)

    Returns:
        DataFrame with columns: Account_Code, Account_Name, Amount, Entity, Period, Date
    """
    
    # Load CSV
    df = pd.read_csv(file_path)
    
    # Set defaults
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    period = date.split('-')[0] if '-' in date else str(datetime.now().year)
    
    # Normalize column names
    df.columns = df.columns.str.strip().str.lower()
    
    # Find the account and balance columns
    account_col = None
    balance_col = None
    
    for col in df.columns:
        if 'account' in col or 'name' in col or 'description' in col:
            account_col = col
        if 'balance' in col or 'amount' in col or 'value' in col:
            balance_col = col
    
    if account_col is None:
        raise ValueError("Could not find account column")
    if balance_col is None:
        raise ValueError("Could not find balance column")
    
    # Build result
    result = []
    for _, row in df.iterrows():
        account_name = str(row[account_col]).strip()
        amount = pd.to_numeric(row[balance_col], errors='coerce')
        
        if pd.isna(amount):
            continue
        
        # Generate account code from account name
        code_prefix = account_name.upper()[:10].replace(" ", "_")
        account_code = f"BS_{code_prefix}"
        
        result.append({
            'Account_Code': account_code,
            'Account_Name': account_name,
            'Amount': amount,
            'Entity': entity,
            'Period': period,
            'Date': date,
        })
    
    return pd.DataFrame(result)
