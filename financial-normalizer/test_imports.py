#!/usr/bin/env python3
"""Test script to verify all modules import correctly"""

import sys
import traceback

def test_imports():
    """Test all module imports"""
    tests = [
        ("Trial Balance Parser", "from src.ingestion.trial_balance_parser import TrialBalanceParser"),
        ("Classifier", "from src.classification.classifier import ClassificationEngine, AccountType"),
        ("Adjustments", "from src.normalization.adjustments import AdjustmentCalculator, EBITDACalculation"),
        ("Engine", "from src.normalization.engine import NormalizedViewEngine"),
        ("Synthetic Generators", "from src.ingestion.synthetic_generators import SyntheticAccountGenerator"),
    ]
    
    print("=" * 60)
    print("IMPORT TESTS")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for name, import_stmt in tests:
        try:
            exec(import_stmt)
            print(f"✓ {name:<30} ... OK")
            passed += 1
        except Exception as e:
            print(f"✗ {name:<30} ... FAILED")
            print(f"  Error: {str(e)}")
            traceback.print_exc()
            failed += 1
    
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
