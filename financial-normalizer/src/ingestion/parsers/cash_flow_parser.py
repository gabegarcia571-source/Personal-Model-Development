"""
Cash Flow Statement Parser

INPUT FORMAT:
Expected CSV with columns like:
- Activity: Operating, Investing, Financing
- Line_Item: Specific activity (e.g., "Net Income", "Changes in Working Capital")
- Cash_Flow: Numeric cash flow amount (positive for inflow, negative for outflow)
- Entity (optional, defaults to 'Unknown')
- Period (optional, defaults to current year)
- Date (optional, defaults to today)

EXTRACTS:
Maps cash flow statement line items to GL entries.
Each line item becomes a separate GL entry with its cash impact.
Maintains activity classification (operating, investing, financing) in account codes.

OUTPUT SCHEMA (required for ClassificationEngine.classify_dataframe()):
- Account_Code: Auto-generated from activity and line item (e.g., "CF_OPS_NI")
- Account_Name: Descriptive name combining activity and line item
- Amount: Cash flow amount
- Entity: Entity name
- Period: Reporting period
- Date: Statement date

DOWNSTREAM:
Output DataFrame feeds directly into ClassificationEngine.classify_dataframe()
No modifications should be made to classifier.py
"""

import pandas as pd
from datetime import datetime
from typing import Optional


def parse_cash_flow(file_path: str,
                   entity: str = "Unknown",
                   period: str = None,
                   date: str = None) -> pd.DataFrame:
    """
    Parse a cash flow statement CSV into the internal schema.

    Args:
        file_path: Path to CSV containing cash flow statement
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
    
    # Find required columns
    activity_col = None
    line_item_col = None
    amount_col = None
    
    for col in df.columns:
        if 'activity' in col or 'section' in col or 'category' in col:
            activity_col = col
        if 'line' in col or 'item' in col or 'description' in col:
            line_item_col = col
        if 'cash' in col or 'flow' in col or 'amount' in col:
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
        
        # Build account code
        activity = ""
        if activity_col and pd.notna(row.get(activity_col)):
            activity = str(row[activity_col]).upper()[:3]  # OPS, INV, FIN
        
        line_code = line_item.upper()[:10].replace(" ", "_")
        account_code = f"CF_{activity}_{line_code}" if activity else f"CF_{line_code}"
        
        # Build account name
        account_name = f"{activity} - {line_item}" if activity else line_item
        
        result.append({
            'Account_Code': account_code,
            'Account_Name': account_name,
            'Amount': amount,
            'Entity': entity,
            'Period': period,
            'Date': date,
        })
    
    return pd.DataFrame(result)
