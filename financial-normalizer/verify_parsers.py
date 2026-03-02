"""
Verification script for all parsers in ingestion/parsers/

This script tests that each parser:
1. Returns a DataFrame
2. Has the required columns: Account_Code, Account_Name, Amount, Entity, Period, Date
3. Has correct data types
4. Output can be passed to ClassificationEngine.classify_dataframe()
"""

import sys
import tempfile
import pandas as pd
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from classification.classifier import ClassificationEngine
from ingestion.parsers import (
    parse_income_statement,
    parse_balance_sheet,
    parse_cash_flow,
    parse_pl_statement,
    parse_manual_input,
)


REQUIRED_COLUMNS = ['Account_Code', 'Account_Name', 'Amount', 'Entity', 'Period', 'Date']


def create_test_csv(parser_type: str) -> str:
    """Create a temporary test CSV for the given parser type."""
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='') as f:
        if parser_type == 'income_statement':
            f.write("Line_Item,Amount\n")
            f.write("Revenue,100000\n")
            f.write("Cost of Goods Sold,40000\n")
            f.write("Operating Expenses,20000\n")
        
        elif parser_type == 'balance_sheet':
            f.write("Account,Balance\n")
            f.write("Cash,50000\n")
            f.write("Accounts Receivable,30000\n")
            f.write("Equipment,100000\n")
            f.write("Accounts Payable,20000\n")
        
        elif parser_type == 'cash_flow':
            f.write("Activity,Line_Item,Cash_Flow\n")
            f.write("Operating,Net Income,40000\n")
            f.write("Operating,Changes in Working Capital,-5000\n")
            f.write("Investing,Capital Expenditures,-15000\n")
            f.write("Financing,Debt Repayment,-10000\n")
        
        elif parser_type == 'pl_statement':
            f.write("Line_Item,Actual\n")
            f.write("Revenue,100000\n")
            f.write("Costs,40000\n")
            f.write("Expenses,20000\n")
        
        elif parser_type == 'manual_input':
            f.write("Account_Code,Account_Name,Amount\n")
            f.write("1000,Cash,50000\n")
            f.write("2000,Payable,20000\n")
            f.write("4000,Revenue,100000\n")
        
        f.flush()
        return f.name


def verify_parser(parser_func, parser_name: str, test_file: str) -> bool:
    """Verify a single parser returns correct schema."""
    
    print(f"\n{'='*70}")
    print(f"Testing: {parser_name}")
    print(f"{'='*70}")
    
    try:
        # Call parser
        df = parser_func(test_file)
        
        # Check it's a DataFrame
        if not isinstance(df, pd.DataFrame):
            print(f"❌ FAILED: Parser returned {type(df)}, expected DataFrame")
            return False
        
        print(f"✓ Returns DataFrame")
        
        # Check required columns
        missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
        if missing_cols:
            print(f"❌ FAILED: Missing columns: {missing_cols}")
            print(f"   Actual columns: {list(df.columns)}")
            return False
        
        print(f"✓ Has all required columns: {REQUIRED_COLUMNS}")
        
        # Check column types
        type_checks = {
            'Account_Code': ['object', 'str'],
            'Account_Name': ['object', 'str'],
            'Amount': ['float64', 'int64', 'float', 'int'],
            'Entity': ['object', 'str'],
            'Period': ['object', 'str'],
            'Date': ['object', 'str'],
        }
        
        type_issues = []
        for col, expected_types in type_checks.items():
            actual_type = str(df[col].dtype)
            if actual_type not in expected_types:
                type_issues.append(f"{col}: expected {expected_types}, got {actual_type}")
        
        if type_issues:
            print(f"⚠ Type warnings (may be OK):")
            for issue in type_issues:
                print(f"  - {issue}")
        else:
            print(f"✓ Column types are correct")
        
        # Check not empty
        if len(df) == 0:
            print(f"❌ FAILED: DataFrame is empty")
            return False
        
        print(f"✓ DataFrame has {len(df)} rows")
        
        # Spot check data
        print(f"\n  Sample data:")
        for idx, row in df.head(2).iterrows():
            print(f"    Row {idx}: {row['Account_Code']:12s} | {row['Account_Name']:20s} | {row['Amount']:10.2f}")
        
        # Try to pass to ClassificationEngine.classify_dataframe()
        print(f"\n  Testing with ClassificationEngine...")
        try:
            classifier = ClassificationEngine()
            df_classified = classifier.classify_dataframe(df)
            
            # Check that classification added expected columns
            expected_cols = ['Account_Type', 'Adjustment_Type', 'Adjustment_Name', 'Adjustment_Reason']
            added_cols = [col for col in expected_cols if col in df_classified.columns]
            
            print(f"  ✓ ClassificationEngine added {len(added_cols)} columns: {added_cols}")
            
        except Exception as e:
            print(f"  ❌ ClassificationEngine.classify_dataframe() failed: {e}")
            return False
        
        print(f"\n✅ {parser_name} PASSED")
        return True
        
    except Exception as e:
        print(f"❌ FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run verification for all parsers."""
    
    print("\n" + "="*70)
    print("PARSER VERIFICATION".center(70))
    print("="*70)
    
    parsers = [
        (parse_income_statement, "Income Statement Parser"),
        (parse_balance_sheet, "Balance Sheet Parser"),
        (parse_cash_flow, "Cash Flow Parser"),
        (parse_pl_statement, "P&L Statement Parser"),
        (parse_manual_input, "Manual Input Parser"),
    ]
    
    results = []
    for parser_func, parser_name in parsers:
        # Map parser names to test CSV types
        parser_type_map = {
            'Income Statement Parser': 'income_statement',
            'Balance Sheet Parser': 'balance_sheet',
            'Cash Flow Parser': 'cash_flow',
            'P&L Statement Parser': 'pl_statement',
            'Manual Input Parser': 'manual_input',
        }
        parser_type = parser_type_map.get(parser_name, parser_name.lower().replace(' ', '_'))
        test_file = create_test_csv(parser_type)
        
        try:
            passed = verify_parser(parser_func, parser_name, test_file)
            results.append((parser_name, passed))
        finally:
            # Clean up temp file
            Path(test_file).unlink(missing_ok=True)
    
    # Summary
    print(f"\n{'='*70}")
    print("VERIFICATION SUMMARY".center(70))
    print(f"{'='*70}\n")
    
    for parser_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{parser_name:30s} {status}")
    
    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)
    
    print(f"\n{passed_count}/{total_count} parsers verified successfully")
    
    return 0 if passed_count == total_count else 1


if __name__ == "__main__":
    sys.exit(main())
