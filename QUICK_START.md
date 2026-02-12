# Quick Start Guide

## Overview

You have a **Financial Normalizer** application that processes trial balance data and generates normalized financial statements with EBITDA metrics.

## Installation & Setup

### 1. Install Dependencies
```bash
cd financial-normalizer
pip install -r requirements.txt
```

### 2. Verify Everything Works
```bash
# Run comprehensive test suite
python run_tests.py
```

All tests should pass with output like:
```
✓ Module Imports - PASS
✓ Trial Balance Parser - PASS
✓ Account Classifier - PASS
✓ Adjustments & EBITDA - PASS
✓ Configuration & Data - PASS
✓ Integration Tests - PASS

Overall: 6/6 test suites passed
```

## Using the Application

### Option 1: Run the Full Pipeline (Recommended)

```bash
# Basic usage with sample data
python src/main.py

# With specific settings
python src/main.py --input data/input/sample_trial_balance.csv \
                    --output data/output/ \
                    --industry saas_tech \
                    --ebitda \
                    --verbose
```

**Output files generated:**
- `1_parsed_transactions.csv` - Parsed GL transactions
- `2_classified_accounts.csv` - Accounts classified by type
- `3_ebitda_metrics.csv` - EBITDA calculations (if --ebitda flag used)
- `4_normalized_summary.csv` - Final normalized financial view

### Option 2: Use Individual Modules in Python

```python
from src.ingestion.trial_balance_parser import TrialBalanceParser
from src.classification.classifier import ClassificationEngine
from src.normalization.adjustments import AdjustmentCalculator

# Parse
parser = TrialBalanceParser('data/input/sample_trial_balance.csv')
transactions = parser.parse()
print(f"Loaded {len(transactions)} transactions")

# Convert to DataFrame and classify
import pandas as pd
df = pd.DataFrame({
    'Account_Code': [t.account for t in transactions],
    'Account_Name': [t.description for t in transactions],
    'Amount': [t.amount for t in transactions],
})

classifier = ClassificationEngine()
df_classified = classifier.classify_dataframe(df)

# Calculate EBITDA
calc = AdjustmentCalculator(df_classified)
ebitda_summary = calc.get_summary()
print(ebitda_summary)
```

## Project Structure

```
financial-normalizer/
├── data/
│   ├── input/sample_trial_balance.csv    # Sample data (GreenPower LLC)
│   └── output/                           # Results saved here
├── config/
│   └── categories.yaml                   # Account classification rules
├── src/
│   ├── main.py                           # ⭐ Main application entry point
│   ├── ingestion/
│   │   ├── trial_balance_parser.py       # Parse GL data
│   │   └── synthetic_generators.py       # Generate test data
│   ├── classification/
│   │   └── classifier.py                 # Classify accounts
│   ├── normalization/
│   │   ├── adjustments.py                # EBITDA calculations
│   │   └── engine.py                     # Orchestrator
│   └── export/
│       └── __init__.py                   # (placeholder - TODO)
├── tests/
│   └── __init__.py                       # (placeholder - TODO)
├── requirements.txt                      # Python dependencies
├── run_tests.py                          # ⭐ Run comprehensive tests
├── test_imports.py                       # Quick import validation
└── PROJECT_REVIEW.md                     # ⭐ Full project documentation
```

## Key Modules

### 1. Trial Balance Parser (`ingestion/trial_balance_parser.py`)
Reads GL data from CSV/Excel with automatic column detection

**Usage:**
```python
from src.ingestion.trial_balance_parser import TrialBalanceParser
parser = TrialBalanceParser('your_file.csv')
transactions = parser.parse()
```

### 2. Account Classifier (`classification/classifier.py`)
Classifies accounts as Revenue, COGS, OpEx, Asset, Liability, etc.

**Features:**
- Industry-specific classification (SaaS, Manufacturing, Financial Services)
- Keyword-based matching
- Suspicious pattern detection

**Usage:**
```python
from src.classification.classifier import ClassificationEngine
classifier = ClassificationEngine()
result = classifier.classify_account("4000", "Product Revenue")
print(result.account_type)  # AccountType.REVENUE
```

### 3. Adjustment Calculator (`normalization/adjustments.py`)
Calculates adjusted and normalized EBITDA with adjustment tracking

**Features:**
- Track adjustments (add-backs, eliminations, normalizations)
- Calculate reported vs. adjusted vs. normalized EBITDA
- Multi-entity consolidation with eliminations

**Usage:**
```python
from src.normalization.adjustments import AdjustmentCalculator
calc = AdjustmentCalculator(gl_data)
ebitda_metrics = calc.calculate_all_metrics()
print(ebitda_metrics)
```

### 4. Normalized View Engine (`normalization/engine.py`)
Orchestrates the complete pipeline

**Usage:**
```python
from src.normalization.engine import NormalizedViewEngine, NormalizedViewConfig
config = NormalizedViewConfig(industry='saas_tech')
engine = NormalizedViewEngine(config)
view = engine.generate_normalized_view(classified_df)
```

## Sample Data

The project includes `data/input/sample_trial_balance.csv` with:
- **Company**: GreenPower LLC (renewable energy)
- **Period**: Jan-Mar 2024
- **Transactions**: 20 entries
- **Account Codes**: 5100-7300 range

This is perfect for testing and understanding the pipeline.

## Testing

### Run All Tests
```bash
python run_tests.py
```

This runs 6 test suites:
1. Module imports
2. Trial balance parsing
3. Account classification
4. EBITDA calculations
5. Configuration validation
6. Integration tests

### Quick Import Check
```bash
python test_imports.py
```

## Configuration

Edit `config/categories.yaml` to customize:
- Account classifications for different industries
- Adjustment rules and keywords
- Suspicious pattern detection thresholds
- Account numbering schemes

**Industries currently configured:**
- `saas_tech` - Software/SaaS companies
- `manufacturing` - Manufacturing companies
- `financial_services` - Banks, insurance, etc.

## Common Tasks

### Task 1: Classify Your Own GL Data
```bash
python src/main.py --input your_trial_balance.csv \
                    --output results/ \
                    --industry manufacturing
```

### Task 2: Generate EBITDA Metrics
```bash
python src/main.py --input your_trial_balance.csv \
                    --output results/ \
                    --ebitda
```

### Task 3: Detect Suspicious Entries
```bash
python src/main.py --input your_trial_balance.csv --detect-patterns
```

### Task 4: Process Multiple Files
```bash
for file in *.csv; do
  python src/main.py --input "$file" --output "results/$file"
done
```

## File Format

**Input CSV Requirements:**
- Must contain Account/Account Code column
- Must contain Amount column (OR Debit + Credit columns)
- Optional: Date, Description, Entity columns

**Column Name Variations Supported:**
- Account: `account`, `account name`, `gl account`, `account_name`
- Amount: `amount`, `value`
- Debit: `debit`, `dr`, `debits`
- Credit: `credit`, `cr`, `credits`
- Date: `date`, `period`, `month`, `posting_date`

## Troubleshooting

### Problem: Module not found errors
**Solution:** Make sure you're in the `financial-normalizer` directory and dependencies are installed:
```bash
cd financial-normalizer
pip install -r requirements.txt
```

### Problem: "Config file not found"
**Solution:** Run from the `financial-normalizer` directory:
```bash
cd financial-normalizer
python src/main.py
```

### Problem: CSV parsing fails
**Solution:** Ensure your CSV has proper column names or use standard columns from the sample file

### Problem: Want to add your own industries
**Solution:** Edit `config/categories.yaml` and add a new industry section with account mappings

## Next: What to Implement

The project is **80% complete**. Below are suggested improvements:

1. **Export Module** (currently empty)
   - PDF report generation
   - Excel export with charts
   - JSON API output
   
2. **Unit Tests** (tests/ directory is empty)
   - Parser edge cases
   - Classification accuracy
   - EBITDA calculation validation
   
3. **Documentation Improvements**
   - Add more code comments
   - Create usage examples
   - Add industry-specific guides
   
4. **Web Interface** (currently CLI only)
   - Flask/FastAPI application
   - File upload
   - Interactive results

## Documentation

See [PROJECT_REVIEW.md](PROJECT_REVIEW.md) for:
- Complete project architecture
- Detailed module descriptions
- Known issues and recommendations
- Future enhancement suggestions

## Support

For issues or questions:
1. Check [PROJECT_REVIEW.md](PROJECT_REVIEW.md) for detailed documentation
2. Review code comments in source files
3. Look at sample data in `data/input/sample_trial_balance.csv`
4. Run `python run_tests.py` to validate your setup

---

**Ready to go!** 🚀

Start with: `python src/main.py --help`
