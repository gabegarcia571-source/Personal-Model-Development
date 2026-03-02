"""
Income Statement Parser

INPUT FORMAT:
Expected CSV with columns like:
- Line_Item: Revenue, COGS, OpEx, Depreciation, Interest, Tax, Net Income
- Amount (required)
- Entity (optional, defaults to 'Unknown')
- Period (optional, defaults to current year)
- Date (optional, defaults to today)

EXTRACTS:
Maps standard income statement line items to GL accounts with amounts.
Creates a separate GL entry for each line item with standardized account names.

OUTPUT SCHEMA (required for ClassificationEngine.classify_dataframe()):
- Account_Code: Auto-generated from line item (e.g., "IS_REV", "IS_COGS")
- Account_Name: Line item name (e.g., "Revenue", "Cost of Goods Sold")
- Amount: Numeric amount from CSV
- Entity: Entity name
- Period: Reporting period
- Date: Date of statement (or period end)

DOWNSTREAM:
Output DataFrame feeds directly into ClassificationEngine.classify_dataframe()
No modifications should be made to classifier.py
"""

import pandas as pd
from datetime import datetime
from typing import Optional


def parse_income_statement(file_path: str,
                          entity: str = "Unknown",
                          period: str = None,
                          date: str = None) -> pd.DataFrame:
    """
    Parse an income statement CSV into the internal schema.

    Args:
        file_path: Path to CSV containing income statement
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
        if 'line' in col or 'item' in col or 'account' in col or 'description' in col:
            line_item_col = col
        if 'amount' in col or 'value' in col:
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
        
        # Generate account code from line item (e.g., "Revenue" -> "IS_REV")
        code_prefix = line_item.upper()[:10].replace(" ", "_")
        account_code = f"IS_{code_prefix}"
        
        result.append({
            'Account_Code': account_code,
            'Account_Name': line_item,
            'Amount': amount,
            'Entity': entity,
            'Period': period,
            'Date': date,
        })
    
    return pd.DataFrame(result)
