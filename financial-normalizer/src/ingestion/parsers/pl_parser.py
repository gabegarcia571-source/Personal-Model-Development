"""
Profit & Loss (P&L) Statement Parser

INPUT FORMAT:
Expected CSV with columns like:
- Line_Item or Description: Revenue, Costs, Expenses
- Actual or Amount: Numeric amount for the period
- Budget (optional): Budgeted amount for comparison
- Variance (optional): Difference from budget
- Entity (optional, defaults to 'Unknown')
- Period (optional, defaults to current year)
- Date (optional, defaults to today)

EXTRACTS:
Maps P&L statement line items to GL entries.
Focuses on operational performance metrics (revenue, costs, expenses).
Each line item becomes a separate GL entry.

OUTPUT SCHEMA (required for ClassificationEngine.classify_dataframe()):
- Account_Code: Auto-generated from line item (e.g., "PL_REV", "PL_COGS")
- Account_Name: Line item description
- Amount: Numeric amount (uses Actual column, ignores Budget/Variance)
- Entity: Entity name
- Period: Reporting period
- Date: Period end date

DOWNSTREAM:
Output DataFrame feeds directly into ClassificationEngine.classify_dataframe()
No modifications should be made to classifier.py
"""

import pandas as pd
from datetime import datetime
from typing import Optional


def parse_pl_statement(file_path: str,
                      entity: str = "Unknown",
                      period: str = None,
                      date: str = None) -> pd.DataFrame:
    """
    Parse a P&L statement CSV into the internal schema.

    Args:
        file_path: Path to CSV containing P&L statement
        entity: Entity name (optional, defaults to 'Unknown')
        period: Reporting period (optional, defaults to current year)
        date: Statement date (optional, defaults to today)

    Returns:
        DataFrame with columns: Account_Code, Account_Name, Amount, Entity, Period, Date
    """
    
    # Load CSV
    df = pd.read_csv(file_path)
    
    # Set defaults
    if period is None:
        period = str(datetime.now().year)
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    # Normalize column names
    df.columns = df.columns.str.strip().str.lower()
    
    # Find the line item and amount columns
    line_item_col = None
    amount_col = None
    
    for col in df.columns:
        if 'line' in col or 'description' in col or 'item' in col or 'account' in col:
            line_item_col = col
        if 'actual' in col or 'amount' in col or 'value' in col:
            if 'budget' not in col and 'variance' not in col:
                amount_col = col
    
    if line_item_col is None:
        raise ValueError("Could not find line item column")
    if amount_col is None:
        raise ValueError("Could not find amount column")
    
    # Build result
    result = []
    for _, row in df.iterrows():
        line_item = str(row[line_item_col]).strip()
        amount = pd.to_numeric(row[amount_col], errors='coerce')
        
        if pd.isna(amount):
            continue
        
        # Generate account code from line item
        code_prefix = line_item.upper()[:10].replace(" ", "_")
        account_code = f"PL_{code_prefix}"
        
        result.append({
            'Account_Code': account_code,
            'Account_Name': line_item,
            'Amount': amount,
            'Entity': entity,
            'Period': period,
            'Date': date,
        })
    
    return pd.DataFrame(result)
