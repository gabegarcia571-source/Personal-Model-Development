"""
Parser collection for different financial statement formats.

Each parser normalizes its specific input format to the internal schema:
- Account_Code, Account_Name, Amount, Entity, Period, Date

Output DataFrames feed directly into ClassificationEngine.classify_dataframe()
"""

from .income_statement_parser import parse_income_statement
from .balance_sheet_parser import parse_balance_sheet
from .cash_flow_parser import parse_cash_flow
from .pl_parser import parse_pl_statement
from .manual_input_parser import parse_manual_input

__all__ = [
    'parse_income_statement',
    'parse_balance_sheet',
    'parse_cash_flow',
    'parse_pl_statement',
    'parse_manual_input',
]
