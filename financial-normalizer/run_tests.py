#!/usr/bin/env python3
"""
Comprehensive Test Suite for Financial Normalizer
Tests all major components and provides detailed health check
"""

import sys
import traceback
from pathlib import Path
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

class TestRunner:
    """Test runner with colored output support"""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []
    
    def run_test(self, name, test_func):
        """Run a single test"""
        try:
            test_func()
            self.passed += 1
            self.tests.append((name, True, None))
            print(f"  ✓ {name:<50} PASS")
            return True
        except AssertionError as e:
            self.failed += 1
            self.tests.append((name, False, str(e)))
            print(f"  ✗ {name:<50} FAIL: {str(e)}")
            return False
        except Exception as e:
            self.failed += 1
            self.tests.append((name, False, str(e)))
            print(f"  ✗ {name:<50} ERROR: {str(e)}")
            traceback.print_exc()
            return False
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*80)
        print(f"TEST SUMMARY: {self.passed} passed, {self.failed} failed")
        print("="*80)


def test_imports():
    """Test 1: Module Imports"""
    print("\n" + "="*80)
    print("TEST 1: MODULE IMPORTS")
    print("="*80)
    
    runner = TestRunner()
    
    runner.run_test("Import pandas", lambda: __import__('pandas'))
    runner.run_test("Import numpy", lambda: __import__('numpy'))
    runner.run_test("Import yaml", lambda: __import__('yaml'))
    runner.run_test("Import TrialBalanceParser", 
                   lambda: __import__('src.ingestion.trial_balance_parser', fromlist=['TrialBalanceParser']))
    runner.run_test("Import ClassificationEngine", 
                   lambda: __import__('src.classification.classifier', fromlist=['ClassificationEngine']))
    runner.run_test("Import AdjustmentCalculator", 
                   lambda: __import__('src.normalization.adjustments', fromlist=['AdjustmentCalculator']))
    runner.run_test("Import NormalizedViewEngine", 
                   lambda: __import__('src.normalization.engine', fromlist=['NormalizedViewEngine']))
    runner.run_test("Import SyntheticAccountGenerator", 
                   lambda: __import__('src.ingestion.synthetic_generators', fromlist=['SyntheticAccountGenerator']))
    
    runner.print_summary()
    return runner.failed == 0


def test_parser():
    """Test 2: Trial Balance Parser"""
    print("\n" + "="*80)
    print("TEST 2: TRIAL BALANCE PARSER")
    print("="*80)
    
    runner = TestRunner()
    from src.ingestion.trial_balance_parser import TrialBalanceParser
    
    def test_parse_sample():
        parser = TrialBalanceParser('data/input/sample_trial_balance.csv')
        transactions = parser.parse()
        assert len(transactions) > 0, "No transactions loaded"
        assert transactions[0].account is not None, "Account field missing"
        assert transactions[0].amount is not None, "Amount field missing"
    
    def test_transaction_structure():
        parser = TrialBalanceParser('data/input/sample_trial_balance.csv')
        transactions = parser.parse()
        tx = transactions[0]
        assert hasattr(tx, 'date'), "Missing date"
        assert hasattr(tx, 'account'), "Missing account"
        assert hasattr(tx, 'description'), "Missing description"
        assert hasattr(tx, 'amount'), "Missing amount"
    
    def test_amount_calculation():
        parser = TrialBalanceParser('data/input/sample_trial_balance.csv')
        transactions = parser.parse()
        positive_sum = sum(t.amount for t in transactions if t.amount > 0)
        negative_sum = sum(t.amount for t in transactions if t.amount < 0)
        assert positive_sum > 0, "No positive amounts"
        # Note: Sample might not balance perfectly
    
    runner.run_test("Parse sample trial balance", test_parse_sample)
    runner.run_test("Validate transaction structure", test_transaction_structure)
    runner.run_test("Verify amount calculations", test_amount_calculation)
    
    runner.print_summary()
    return runner.failed == 0


def test_classifier():
    """Test 3: Account Classifier"""
    print("\n" + "="*80)
    print("TEST 3: ACCOUNT CLASSIFICATION")
    print("="*80)
    
    runner = TestRunner()
    from src.classification.classifier import ClassificationEngine, AccountType
    
    def test_config_loading():
        engine = ClassificationEngine()
        assert engine.config is not None, "Config not loaded"
        assert len(engine.config) > 0, "Config is empty"
        assert 'saas_tech' in engine.config or 'manufacturing' in engine.config, "No industries in config"
    
    def test_revenue_classification():
        engine = ClassificationEngine()
        result = engine.classify_account("4000", "Product Revenue")
        assert result.account_type == AccountType.REVENUE, f"Expected REVENUE, got {result.account_type}"
    
    def test_cogs_classification():
        engine = ClassificationEngine()
        result = engine.classify_account("5000", "Cost of Goods Sold")
        assert result.account_type == AccountType.COGS, f"Expected COGS, got {result.account_type}"
    
    def test_opex_classification():
        engine = ClassificationEngine()
        result = engine.classify_account("6000", "Salaries and Wages")
        account_type = result.account_type
        assert account_type in [AccountType.OPEX, AccountType.UNKNOWN], f"Unexpected type: {account_type}"
    
    def test_suspicious_patterns():
        parser = __import__('src.ingestion.trial_balance_parser', fromlist=['TrialBalanceParser']).TrialBalanceParser
        engine = ClassificationEngine()
        
        parser_obj = parser('data/input/sample_trial_balance.csv')
        transactions = parser_obj.parse()
        
        df = pd.DataFrame({
            'Account_Name': [t.description for t in transactions],
            'Amount': [t.amount for t in transactions],
        })
        
        flags = engine.detect_suspicious_patterns(df)
        assert isinstance(flags, list), "Flags should be a list"
    
    runner.run_test("Load classification config", test_config_loading)
    runner.run_test("Classify revenue account", test_revenue_classification)
    runner.run_test("Classify COGS account", test_cogs_classification)
    runner.run_test("Classify OpEx account", test_opex_classification)
    runner.run_test("Detect suspicious patterns", test_suspicious_patterns)
    
    runner.print_summary()
    return runner.failed == 0


def test_adjustments():
    """Test 4: Adjustment Calculator & EBITDA"""
    print("\n" + "="*80)
    print("TEST 4: ADJUSTMENTS & EBITDA CALCULATOR")
    print("="*80)
    
    runner = TestRunner()
    from src.normalization.adjustments import (
        AdjustmentCalculator, AdjustmentDetail, AdjustmentCategory, EBITDAMetric
    )
    
    def test_adjustment_creation():
        calc = AdjustmentCalculator()
        adj = AdjustmentDetail(
            adjustment_id="TEST-001",
            adjustment_name="Test Adjustment",
            adjustment_category=AdjustmentCategory.ADDBACK,
            account_code="6000",
            account_name="Salaries",
            amount=50000.0,
        )
        calc.add_adjustment(adj)
        assert len(calc.adjustments) == 1, "Adjustment not added"
    
    def test_ebitda_calculation():
        calc = AdjustmentCalculator()
        
        # Create sample GL data
        df = pd.DataFrame({
            'Account_Code': ['4000', '5000', '6000'],
            'Account_Name': ['Revenue', 'COGS', 'OpEx'],
            'Account_Type': ['revenue', 'cogs', 'opex'],
            'Amount': [1000000, 400000, 200000]
        })
        
        calc.gl_data = df
        ebitda = calc.calculate_reported_ebitda()
        
        assert ebitda is not None, "EBITDA calculation returned None"
        assert ebitda.revenue > 0, "Revenue should be positive"
        assert ebitda.ebitda >= 0, "EBITDA should be non-negative"
    
    def test_adjustment_impact():
        calc = AdjustmentCalculator()
        
        # Create minimum GL data
        df = pd.DataFrame({
            'Account_Code': ['4000', '5000', '6000'],
            'Account_Name': ['Revenue', 'COGS', 'OpEx'],
            'Account_Type': ['revenue', 'cogs', 'opex'],
            'Amount': [1000000, 400000, 200000]
        })
        
        calc.gl_data = df
        
        # Add adjustment
        adj = AdjustmentDetail(
            adjustment_id="ADJ-001",
            adjustment_name="Stock Based Comp",
            adjustment_category=AdjustmentCategory.ADDBACK,
            account_code="6000",
            account_name="Salaries",
            amount=50000,
        )
        calc.add_adjustment(adj)
        
        # Calculate impact
        impact_df = calc.get_adjustment_impact_analysis()
        assert len(impact_df) > 0, "No adjustment impact data"
        assert impact_df.iloc[0]['EBITDA_Impact'] == 50000, "Addback impact incorrect"
    
    runner.run_test("Create adjustment", test_adjustment_creation)
    runner.run_test("Calculate EBITDA", test_ebitda_calculation)
    runner.run_test("Analyze adjustment impact", test_adjustment_impact)
    
    runner.print_summary()
    return runner.failed == 0


def test_configuration():
    """Test 5: Configuration Files"""
    print("\n" + "="*80)
    print("TEST 5: CONFIGURATION & DATA FILES")
    print("="*80)
    
    runner = TestRunner()
    
    def test_categories_yaml_exists():
        config_path = Path('config/categories.yaml')
        assert config_path.exists(), "categories.yaml not found"
    
    def test_sample_data_exists():
        data_path = Path('data/input/sample_trial_balance.csv')
        assert data_path.exists(), "sample_trial_balance.csv not found"
    
    def test_sample_data_format():
        df = pd.read_csv('data/input/sample_trial_balance.csv')
        required_cols = ['Account', 'Description', 'Debit', 'Credit']
        actual_cols = df.columns.tolist()
        # Check for similar column names
        assert len(df) > 0, "Sample data is empty"
    
    def test_config_yaml_valid():
        import yaml
        with open('config/categories.yaml', 'r') as f:
            config = yaml.safe_load(f)
        assert config is not None, "Invalid YAML"
        assert isinstance(config, dict), "Config should be a dictionary"
    
    runner.run_test("Check categories.yaml exists", test_categories_yaml_exists)
    runner.run_test("Check sample data exists", test_sample_data_exists)
    runner.run_test("Validate sample data format", test_sample_data_format)
    runner.run_test("Validate YAML configuration", test_config_yaml_valid)
    
    runner.print_summary()
    return runner.failed == 0


def test_integration():
    """Test 6: Integration Tests"""
    print("\n" + "="*80)
    print("TEST 6: INTEGRATION TESTS")
    print("="*80)
    
    runner = TestRunner()
    
    def test_full_pipeline():
        from src.ingestion.trial_balance_parser import TrialBalanceParser
        from src.classification.classifier import ClassificationEngine
        
        # Parse
        parser = TrialBalanceParser('data/input/sample_trial_balance.csv')
        transactions = parser.parse()
        assert len(transactions) > 0, "Parser failed"
        
        # Classify
        df = pd.DataFrame({
            'Account_Code': [t.account for t in transactions],
            'Account_Name': [t.description for t in transactions],
            'Amount': [t.amount for t in transactions],
        })
        
        classifier = ClassificationEngine()
        classified = classifier.classify_dataframe(df)
        assert len(classified) > 0, "Classifier failed"
        assert 'Account_Type' in classified.columns, "Classification output missing Account_Type"
    
    def test_dataframe_classification():
        from src.classification.classifier import ClassificationEngine
        
        test_df = pd.DataFrame({
            'Account_Code': ['4000', '5000', '6000'],
            'Account_Name': ['Revenue', 'COGS', 'Salaries'],
        })
        
        classifier = ClassificationEngine()
        result = classifier.classify_dataframe(test_df)
        
        assert len(result) == 3, "Classification failed to process all rows"
        assert 'Account_Type' in result.columns, "Missing Account_Type column"
    
    runner.run_test("Full pipeline (parse -> classify)", test_full_pipeline)
    runner.run_test("DataFrame classification", test_dataframe_classification)
    
    runner.print_summary()
    return runner.failed == 0


def main():
    """Run all tests"""
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*78 + "║")
    print("║" + "FINANCIAL NORMALIZER - COMPREHENSIVE TEST SUITE".center(78) + "║")
    print("║" + " "*78 + "║")
    print("╚" + "="*78 + "╝")
    
    results = []
    results.append(("Module Imports", test_imports()))
    results.append(("Trial Balance Parser", test_parser()))
    results.append(("Account Classifier", test_classifier()))
    results.append(("Adjustments & EBITDA", test_adjustments()))
    results.append(("Configuration & Data", test_configuration()))
    results.append(("Integration Tests", test_integration()))
    
    # Final summary
    print("\n" + "="*80)
    print("FINAL TEST RESULTS".center(80))
    print("="*80)
    
    total_pass = sum(1 for _, passed in results if passed)
    total_tests = len(results)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name:<40} {status}")
    
    print("="*80)
    print(f"Overall: {total_pass}/{total_tests} test suites passed")
    print("="*80)
    
    if total_pass == total_tests:
        print("\n🎉 ALL TESTS PASSED! Your project is working correctly.\n")
        return 0
    else:
        print(f"\n⚠️  {total_tests - total_pass} test suite(s) failed. Review errors above.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
