#!/usr/bin/env python3
"""
Quick Validation Script - Checks if all core functionality works
Outputs results to verification_report.txt
"""

import sys
from pathlib import Path

# Redirect output to file and console
class DualWriter:
    def __init__(self, file):
        self.file = file
        self.console = sys.__stdout__
    
    def write(self, message):
        self.file.write(message)
        self.console.write(message)
        self.file.flush()
    
    def flush(self):
        self.file.flush()


def validate():
    """Run validation checks"""
    
    output_file = Path(__file__).parent / "financial-normalizer" / "verification_report.txt"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        writer = DualWriter(f)
        sys.stdout = writer
        
        report = []
        
        print("="*80)
        print("FINANCIAL NORMALIZER - VERIFICATION REPORT")
        print("="*80)
        print()
        
        # Check 1: Files exist
        print("[CHECK 1] Verifying project structure...")
        sys.path.insert(0, str(Path(__file__).parent / "financial-normalizer"))
        
        files_to_check = [
            "config/categories.yaml",
            "data/input/sample_trial_balance.csv",
            "src/main.py",
            "src/ingestion/trial_balance_parser.py",
            "src/classification/classifier.py",
            "src/normalization/adjustments.py",
            "src/normalization/engine.py",
            "requirements.txt",
        ]
        
        missing_files = []
        for file_path in files_to_check:
            full_path = Path(__file__).parent / "financial-normalizer" / file_path
            if full_path.exists():
                print(f"  ✓ {file_path}")
                report.append(("File exists", file_path, "PASS"))
            else:
                print(f"  ✗ {file_path}")
                missing_files.append(file_path)
                report.append(("File exists", file_path, "FAIL"))
        
        if missing_files:
            print(f"\n⚠️  Missing {len(missing_files)} files!")
            return False
        
        print(f"\n  All {len(files_to_check)} required files found ✓\n")
        
        # Check 2: Module imports
        print("[CHECK 2] Verifying Python modules can be imported...")
        
        modules = [
            ("pandas", "Data processing library"),
            ("yaml", "YAML configuration parser"),
            ("src.ingestion.trial_balance_parser", "Trial balance parser"),
            ("src.classification.classifier", "Account classifier"),
            ("src.normalization.adjustments", "EBITDA calculator"),
            ("src.normalization.engine", "Normalization engine"),
        ]
        
        import_errors = []
        for module_name, description in modules:
            try:
                __import__(module_name)
                print(f"  ✓ {module_name:<40} ({description})")
                report.append(("Import", module_name, "PASS"))
            except Exception as e:
                print(f"  ✗ {module_name:<40} ERROR: {str(e)}")
                import_errors.append((module_name, str(e)))
                report.append(("Import", module_name, "FAIL"))
        
        if import_errors:
            print(f"\n⚠️  {len(import_errors)} import errors detected")
            for mod, err in import_errors:
                print(f"  - {mod}: {err}")
            return False
        
        print(f"\n  All {len(modules)} modules imported successfully ✓\n")
        
        # Check 3: Configuration
        print("[CHECK 3] Verifying configuration...")
        
        try:
            import yaml
            config_path = Path(__file__).parent / "financial-normalizer" / "config" / "categories.yaml"
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            industries = list(config.keys())
            print(f"  ✓ Configuration loaded with {len(industries)} industries:")
            for industry in industries:
                if isinstance(config[industry], dict):
                    print(f"    - {industry}")
                    report.append(("Config", industry, "PASS"))
            
            print()
        except Exception as e:
            print(f"  ✗ Configuration error: {str(e)}")
            report.append(("Config", "categories.yaml", "FAIL"))
            return False
        
        # Check 4: Sample data
        print("[CHECK 4] Verifying sample data...")
        
        try:
            import pandas as pd
            data_path = Path(__file__).parent / "financial-normalizer" / "data" / "input" / "sample_trial_balance.csv"
            df = pd.read_csv(data_path)
            
            print(f"  ✓ Sample data loaded: {len(df)} rows, {len(df.columns)} columns")
            print(f"    Columns: {', '.join(df.columns.tolist())}")
            report.append(("Sample Data", f"{len(df)} transactions", "PASS"))
            print()
        except Exception as e:
            print(f"  ✗ Sample data error: {str(e)}")
            report.append(("Sample Data", "sample_trial_balance.csv", "FAIL"))
            return False
        
        # Check 5: Core functionality
        print("[CHECK 5] Testing core functionality...")
        
        try:
            from src.ingestion.trial_balance_parser import TrialBalanceParser
            from src.classification.classifier import ClassificationEngine
            
            # Parse
            data_path = Path(__file__).parent / "financial-normalizer" / "data" / "input" / "sample_trial_balance.csv"
            parser = TrialBalanceParser(str(data_path))
            transactions = parser.parse()
            print(f"  ✓ Parsed {len(transactions)} transactions")
            report.append(("Parse", f"{len(transactions)} transactions", "PASS"))
            
            # Classify
            classifier = ClassificationEngine()
            test_accounts = [
                ("4000", "Product Revenue"),
                ("5000", "Cost of Goods Sold"),
                ("6000", "Salaries"),
            ]
            
            classifications_ok = True
            for code, name in test_accounts:
                result = classifier.classify_account(code, name)
                if result.account_type:
                    print(f"  ✓ Classified {code} ({name}) as {result.account_type.value}")
                else:
                    print(f"  ✗ Failed to classify {code} ({name})")
                    classifications_ok = False
            
            report.append(("Classify", "Test accounts", "PASS" if classifications_ok else "FAIL"))
            
            if not classifications_ok:
                return False
            
            print()
        except Exception as e:
            print(f"  ✗ Functionality test error: {str(e)}")
            import traceback
            traceback.print_exc()
            report.append(("Functionality", "Core operations", "FAIL"))
            return False
        
        # Summary
        print("="*80)
        print("VERIFICATION SUMMARY")
        print("="*80)
        
        passes = sum(1 for _, _, status in report if status == "PASS")
        fails = sum(1 for _, _, status in report if status == "FAIL")
        
        print(f"\nTotal checks: {len(report)}")
        print(f"Passed: {passes}")
        print(f"Failed: {fails}")
        
        print("\nStatus by category:")
        categories = {}
        for cat, check, status in report:
            if cat not in categories:
                categories[cat] = {"pass": 0, "fail": 0}
            if status == "PASS":
                categories[cat]["pass"] += 1
            else:
                categories[cat]["fail"] += 1
        
        for cat in sorted(categories.keys()):
            stats = categories[cat]
            status_str = "✓" if stats["fail"] == 0 else "✗"
            print(f"  {status_str} {cat:<20} {stats['pass']}/{stats['pass']+stats['fail']} passed")
        
        print("\n" + "="*80)
        
        if fails == 0:
            print("✅ ALL CHECKS PASSED - YOUR PROJECT IS WORKING!")
            print("="*80)
            return True
        else:
            print(f"⚠️ {fails} CHECKS FAILED - REVIEW ERRORS ABOVE")
            print("="*80)
            return False


if __name__ == "__main__":
    success = validate()
    # Print location of report
    report_path = Path(__file__).parent / "financial-normalizer" / "verification_report.txt"
    print(f"\n📄 Full report saved to: {report_path}\n")
    sys.exit(0 if success else 1)
