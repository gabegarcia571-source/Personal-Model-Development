"""
Manual Input Parser

INPUT FORMAT:
Expected CSV with columns in any of these variations:
Required columns (any spelling variations):
  - Account_Code / Code / GL_Code
  - Account_Name / Account / Description / Line_Item
  - Amount / Balance / Value
  
Optional columns:
  - Entity / Company / Legal_Entity (defaults to 'Unknown')
  - Period / Year / Month (defaults to current year)
  - Date / Period_Date / Posting_Date (defaults to today)

EXTRACTS:
Maps user-provided journal entries or adjustments to GL format.
Minimal transformation - column names are normalized to the internal schema.
Accepts flexible input formats to support ad-hoc data entry.

OUTPUT SCHEMA (required for ClassificationEngine.classify_dataframe()):
- Account_Code: From input (or auto-generated if missing)
- Account_Name: From input
- Amount: Numeric amount
- Entity: Entity name
- Period: Reporting period
- Date: Entry date

DOWNSTREAM:
Output DataFrame feeds directly into ClassificationEngine.classify_dataframe()
No modifications should be made to classifier.py
"""

import pandas as pd
from datetime import datetime
from typing import Optional


def parse_manual_input(file_path: str,
                      entity: str = None,
                      period: str = None,
                      date: str = None) -> pd.DataFrame:
    """
    Parse manually entered GL data (flexible format) into the internal schema.

    Args:
        file_path: Path to CSV with GL entries
        entity: Entity to assign if not in file (optional)
        period: Period to assign if not in file (optional)
        date: Date to assign if not in file (optional)

    Returns:
        DataFrame with columns: Account_Code, Account_Name, Amount, Entity, Period, Date
    """
    
    # Load CSV
    df = pd.read_csv(file_path)
    
    # Normalize column names to lower case and strip whitespace
    df.columns = df.columns.str.strip().str.lower()
    
    # Find and rename columns to standard names
    code_col = None
    name_col = None
    amount_col = None
    entity_col = None
    period_col = None
    date_col = None
    
    for col in df.columns:
        if 'code' in col or 'gl' in col:
            code_col = col
        elif 'name' in col or 'account' in col or 'description' in col:
            name_col = col
        elif 'amount' in col or 'balance' in col or 'value' in col:
            amount_col = col
        elif 'entity' in col or 'company' in col:
            entity_col = col
        elif 'period' in col or 'year' in col or 'month' in col:
            period_col = col
        elif 'date' in col:
            date_col = col
    
    # Validate required columns
    if name_col is None:
        raise ValueError("Could not find account name column")
    if amount_col is None:
        raise ValueError("Could not find amount column")
    
    # Build result
    result = []
    for idx, row in df.iterrows():
        account_code = str(row[code_col]) if code_col else f"MAN_{idx:04d}"
        account_name = str(row[name_col]).strip()
        amount = pd.to_numeric(row[amount_col], errors='coerce')
        
        if pd.isna(amount):
            continue
        
        # Resolve entity, period, date from parameters or CSV
        resolved_entity = entity
        if entity_col and pd.notna(row.get(entity_col)):
            resolved_entity = str(row[entity_col]).strip()
        if resolved_entity is None:
            resolved_entity = "Unknown"
        
        resolved_period = period
        if period_col and pd.notna(row.get(period_col)):
            resolved_period = str(row[period_col]).strip()
        if resolved_period is None:
            resolved_period = str(datetime.now().year)
        
        resolved_date = date
        if date_col and pd.notna(row.get(date_col)):
            resolved_date = str(row[date_col]).strip()
        if resolved_date is None:
            resolved_date = datetime.now().strftime("%Y-%m-%d")
        
        result.append({
            'Account_Code': account_code,
            'Account_Name': account_name,
            'Amount': amount,
            'Entity': resolved_entity,
            'Period': resolved_period,
            'Date': resolved_date,
        })
    
    return pd.DataFrame(result)
