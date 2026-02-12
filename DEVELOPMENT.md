# Development Guide

This document explains the architecture, design decisions, and how to extend the Financial Statement Normalizer.

---

## 🏗️ Architecture Overview

### High-Level Design

```
                    INPUT LAYER
                        ↓
            TrialBalanceParser (ingestion/)
                        ↓
                        ├─→ CSV/Excel Reader
                        ├─→ Column Detection
                        └─→ Data Validation
                        ↓
                    CLASSIFICATION LAYER
                        ↓
            ClassificationEngine (classification/)
                        ↓
                        ├─→ Load YAML Config
                        ├─→ Industry Matching
                        ├─→ Keyword Matching
                        └─→ Pattern Detection
                        ↓
                   NORMALIZATION LAYER
                        ↓
            AdjustmentCalculator (normalization/)
                        ↓
                        ├─→ Track Adjustments
                        ├─→ EBITDA Calculation
                        ├─→ Consolidation
                        └─→ Impact Analysis
                        ↓
                    OUTPUT LAYER
                        ↓
            NormalizedViewEngine (normalization/)
                        ↓
                        ├─→ Generate Views
                        ├─→ Comparisons
                        └─→ Reports
                        ↓
                    EXPORT LAYER (TODO)
                        ↓
            Exporters (export/)
                        ↓
                        ├─→ CSV Export
                        ├─→ Excel Export (TODO)
                        └─→ PDF Export (TODO)
```

### Module Structure

```
src/
├── __init__.py
├── main.py                              # CLI Entry point
│
├── ingestion/                           # Read and parse files
│   ├── __init__.py
│   ├── trial_balance_parser.py          # Parse GL data
│   └── synthetic_generators.py          # Generate test data
│
├── classification/                      # Account classification
│   ├── __init__.py
│   └── classifier.py                    # Classify accounts
│
├── normalization/                       # Calculations
│   ├── __init__.py
│   ├── adjustments.py                   # EBITDA & adjustments
│   └── engine.py                        # Orchestrator
│
└── export/                              # Output generation (TODO)
    ├── __init__.py
    └── (exporters go here)
```

---

## 🔑 Key Design Principles

### 1. Separation of Concerns
Each module has a single responsibility:
- **Ingestion**: Read files only
- **Classification**: Classify accounts only
- **Normalization**: Calculate metrics only
- **Export**: Save results only

### 2. Configuration-Driven
Rules live in `categories.yaml`, not code:
- No hard-coded account mappings
- Easy to add industries without code changes
- Extensible pattern detection rules

### 3. Type Safety
Uses Python dataclasses and type hints:
- Clear data structures
- IDE autocompletion support
- Easier to catch bugs

### 4. Composition Over Inheritance
Uses composition to build complex behaviors:
- Classes work independently
- Easy to test each component
- Clear dependencies

### 5. Fail Fast
Validates input early:
- Check required columns exist
- Validate data before processing
- Provide clear error messages

---

## 📦 Core Classes & Interfaces

### Ingestion Layer

#### `TrialBalanceParser`
**File**: `src/ingestion/trial_balance_parser.py`

```python
class TrialBalanceParser:
    def __init__(self, file_path: str)
    def parse() -> List[Transaction]
    def _map_columns(columns) -> Dict
    
class Transaction:
    date: datetime
    account: str
    description: str
    amount: float
    entity: Optional[str]
```

**Key Methods**:
- `parse()`: Main method to parse files
- `_map_columns()`: Auto-detect column names
- Validates debits == credits

---

### Classification Layer

#### `ClassificationEngine`
**File**: `src/classification/classifier.py`

```python
class ClassificationEngine:
    def __init__(self, config_path: str)
    def classify_account(account_code: str, name: str) -> AccountClassification
    def classify_dataframe(df: DataFrame) -> DataFrame
    def detect_suspicious_patterns(df: DataFrame) -> List[SuspiciousPatternFlag]
    
class AccountClassification:
    account_code: str
    account_name: str
    account_type: AccountType
    adjustment_type: Optional[AdjustmentType]
    metrics: List[str]
    suspicious_flags: List[SuspiciousPatternFlag]

class AccountType(Enum):
    REVENUE, COGS, OPEX, DEPRECIATION, # ... 11 types total
```

**Key Methods**:
- `classify_account()`: Classify single account
- `classify_dataframe()`: Classify all rows
- `detect_suspicious_patterns()`: Flag unusual entries
- `_classify_by_industry()`: Industry-specific rules
- `_classify_by_keywords()`: Keyword matching

---

### Normalization Layer

#### `AdjustmentCalculator`
**File**: `src/normalization/adjustments.py`

```python
class AdjustmentCalculator:
    def __init__(self, gl_data: DataFrame)
    def add_adjustment(adjustment: AdjustmentDetail)
    def calculate_reported_ebitda() -> EBITDACalculation
    def apply_adjustments(base_calc, categories) -> EBITDACalculation
    def calculate_all_metrics() -> Dict[EBITDAMetric, EBITDACalculation]
    def get_summary() -> DataFrame
    def get_adjustment_impact_analysis() -> DataFrame

class AdjustmentDetail:
    adjustment_id: str
    adjustment_name: str
    adjustment_category: AdjustmentCategory
    account_code: str
    account_name: str
    amount: float
    is_recurring: bool

class EBITDACalculation:
    revenue: float
    cogs: float
    gross_profit: float
    opex: float
    ebit: float
    depreciation_amortization: float
    ebitda: float
```

**Key Methods**:
- `calculate_reported_ebitda()`: From raw GL
- `apply_adjustments()`: Apply add-backs, eliminations
- `calculate_all_metrics()`: Get all 3 EBITDA levels
- `get_adjustment_impact_analysis()`: Show impact per adjustment

#### `ConsolidationEngine`
**File**: `src/normalization/adjustments.py`

```python
class ConsolidationEngine:
    def add_entity(entity_name: str, entity_gl: DataFrame)
    def consolidate() -> Tuple[DataFrame, DataFrame]
    def _identify_intercompany_eliminations() -> DataFrame
```

---

### Orchestration Layer

#### `NormalizedViewEngine`
**File**: `src/normalization/engine.py`

```python
class NormalizedViewEngine:
    def __init__(self, config: NormalizedViewConfig)
    def generate_normalized_view(df: DataFrame) -> NormalizedFinancialView

class NormalizedViewConfig:
    include_intercompany_eliminations: bool
    apply_industry_normalization: bool
    base_currency: str
    industry: Optional[str]
    consolidate_multi_entity: bool

class NormalizedFinancialView:
    period: str
    entity: str
    raw_gl: DataFrame
    classifications: Dict[str, AccountClassification]
    adjustments: List[AdjustmentDetail]
    reported_ebitda: float
    adjusted_ebitda: float
    normalized_ebitda: float
    before_after_details: DataFrame
```

---

## 🔄 Data Flow Example

Here's how data flows through the system:

```python
# Step 1: Parse
parser = TrialBalanceParser('trial_balance.csv')
transactions = parser.parse()  # List[Transaction]

# Step 2: Convert to DataFrame
df = pd.DataFrame({
    'Account_Code': [t.account for t in transactions],
    'Account_Name': [t.description for t in transactions],
    'Amount': [t.amount for t in transactions],
})

# Step 3: Classify
classifier = ClassificationEngine()
classified_df = classifier.classify_dataframe(df)
# Now has columns: Account_Type, Adjustment_Type, etc.

# Step 4: Adjust & Calculate
calculator = AdjustmentCalculator(classified_df)
metrics = calculator.calculate_all_metrics()
# Returns: {EBITDAMetric.REPORTED: ..., .ADJUSTED: ..., .NORMALIZED: ...}

# Step 5: Generate View
config = NormalizedViewConfig(industry='saas_tech')
engine = NormalizedViewEngine(config)
view = engine.generate_normalized_view(classified_df)
# Returns: NormalizedFinancialView with all analytics
```

---

## 🔧 How to Add Features

### Feature 1: Add a New Account Type

**Steps**:
1. Add to `AccountType` enum in `classifier.py`
2. Add classification rule in `_classify_by_keywords()`
3. Update `categories.yaml` if needed
4. Add test case in `run_tests.py`

**Example**:
```python
# In src/classification/classifier.py
class AccountType(Enum):
    # ... existing types ...
    MY_NEW_TYPE = "my_new_type"  # Add this

def _classify_by_keywords(self, account_name_lower: str) -> AccountType:
    # ... existing code ...
    
    # Add this check
    if any(keyword in account_name_lower for keyword in ['my', 'keywords']):
        return AccountType.MY_NEW_TYPE
```

### Feature 2: Add a New Industry

**Steps**:
1. Edit `config/categories.yaml`
2. Add industry section with account mappings
3. Test: `python src/main.py --industry new_industry`
4. Add sample data if possible
5. Document in `DEVELOPMENT.md`

**Example**:
```yaml
# In config/categories.yaml
new_industry:
  industry_name: "New Industry"
  revenue_accounts:
    "4000":
      name: "Product Revenue"
      account_type: "revenue"
  cogs_accounts:
    "5000":
      name: "Cost of Goods"
      account_type: "cogs"
  operating_expenses:
    "6000":
      name: "Operating Expenses"
      account_type: "opex"
```

### Feature 3: Add Suspicious Pattern Detection

**Steps**:
1. Implement detection in `ClassificationEngine.detect_suspicious_patterns()`
2. Return `List[SuspiciousPatternFlag]`
3. Add test case
4. Document the pattern

**Example**:
```python
# In src/classification/classifier.py
def detect_suspicious_patterns(self, df, ...) -> List[SuspiciousPatternFlag]:
    flags = []
    
    # Check for my_pattern
    suspicious_rows = df[df[account_col].str.contains('pattern', case=False, na=False)]
    if not suspicious_rows.empty:
        flags.append(SuspiciousPatternFlag(
            account_name="Account",
            pattern="my_pattern",
            risk_level="medium",
            reason="Description of why this is suspicious",
            recommended_action="What to do about it"
        ))
    
    return flags
```

### Feature 4: Add Export Format (CSV/JSON/etc)

**Steps**:
1. Create new file: `src/export/my_exporter.py`
2. Implement `export(data: DataFrame, path: str)` method
3. Update `src/main.py` to use new exporter
4. Add tests
5. Document usage

**Example Structure**:
```python
# In src/export/my_exporter.py
class MyExporter:
    """Exports to my format"""
    
    def __init__(self, options: Dict = None):
        self.options = options or {}
    
    def export(self, 
               normalized_view: NormalizedFinancialView,
               output_path: str) -> bool:
        """
        Export normalized view to my format
        
        Returns: True if successful
        """
        try:
            # Implementation here
            return True
        except Exception as e:
            logger.error(f"Export failed: {e}")
            return False
```

---

## 🧪 Testing Best Practices

### Writing Tests

Tests should follow the **Arrange-Act-Assert** pattern:

```python
def test_classification_accuracy():
    # Arrange: Set up test data
    test_accounts = [
        ("4000", "Product Revenue"),
        ("5000", "Cost of Goods Sold"),
    ]
    classifier = ClassificationEngine()
    
    # Act: Run the function
    results = [classifier.classify_account(code, name) for code, name in test_accounts]
    
    # Assert: Check results
    assert results[0].account_type == AccountType.REVENUE
    assert results[1].account_type == AccountType.COGS
```

### Test Organization

Group related tests:
```python
def test_imports():
    """Group 1: Test imports"""
    # ... import tests

def test_parser():
    """Group 2: Test parser"""
    # ... parser tests

def test_classifier():
    """Group 3: Test classifier"""
    # ... classifier tests
```

### Running Tests

```bash
# All tests
python run_tests.py

# Quick validation
python test_imports.py

# Verify setup
python verify_setup.py
```

---

## 🐛 Debugging Tips

### Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Now all DEBUG messages will print
```

### Inspect DataFrames
```python
# In your code
print(df.head())        # First 5 rows
print(df.info())        # Column types
print(df.describe())    # Statistics
print(df.columns)       # Column names
print(df.dtypes)        # Data types
```

### Test Individual Modules
```bash
# Test parser
python test_imports.py

# Test individual function
python -c "from src.classification.classifier import ClassificationEngine; ..."

# Debug with print statements
python -u src/main.py --verbose
```

---

## 📊 Performance Considerations

### Current Performance

Tested with sample data (20 transactions):
- Parse: < 100ms
- Classify: < 50ms
- EBITDA calc: < 50ms
- Total: < 300ms

### Optimization for Large Files

For 100K+ transactions:
1. Use `chunksize` in pandas read operations
2. Batch classification calls
3. Use `groupby()` for aggregations
4. Consider vectorization with numpy

Example:
```python
# Slow: Process row by row
for _, row in df.iterrows():
    classify_account(row['code'], row['name'])

# Fast: Batch process
df_classified = classifier.classify_dataframe(df)
```

---

## 🏢 Code Organization

### File Naming
- **Classes**: `PascalCase` (e.g., `ClassificationEngine`)
- **Modules**: `snake_case` (e.g., `trial_balance_parser.py`)
- **Functions**: `snake_case` (e.g., `classify_account()`)

### Module Size Guidelines
- < 500 lines: single file OK
- 500-1000 lines: consider splitting
- > 1000 lines: definitely split into sub-modules

### Import Organization
```python
# Standard library
import logging
from datetime import datetime
from pathlib import Path

# Third-party
import pandas as pd
import yaml

# Local
from ..classification.classifier import ClassificationEngine
```

---

## 🔐 Error Handling

### Pattern: Validation First
```python
def classify_account(self, account_code: str, account_name: str) -> AccountClassification:
    # Validate inputs first
    if not account_code or not account_name:
        raise ValueError("Account code and name are required")
    
    # Then process
    # ...
```

### Pattern: Meaningful Errors
```python
# Bad
raise Exception("Error")

# Good
raise ValueError(f"Invalid account code: {account_code}. Expected format: 4-digit number")
```

### Pattern: Logging Errors
```python
import logging
logger = logging.getLogger(__name__)

try:
    result = do_something()
except Exception as e:
    logger.error(f"Failed to classify account: {e}", exc_info=True)
    raise
```

---

## 📚 Documentation Standards

### Docstring Format (Google Style)
```python
def my_function(data: pd.DataFrame, threshold: float) -> Dict[str, float]:
    """
    Brief one-line description.
    
    Longer description explaining what the function does,
    including any important details about behavior or
    side effects.
    
    Args:
        data: Description of DataFrame structure
        threshold: Description of threshold parameter
        
    Returns:
        Description of returned dictionary structure
        
    Raises:
        ValueError: When input is invalid
        
    Example:
        >>> result = my_function(data, 0.5)
        >>> print(result)
        {'key': 'value', ...}
    """
    # Implementation
```

### Class Docstrings
```python
class MyClass:
    """
    One-line summary.
    
    Longer description of the class purpose and behavior.
    
    Attributes:
        attr1: Description
        attr2: Description
        
    Example:
        >>> obj = MyClass(param1="value")
        >>> obj.do_something()
    """
```

---

## 🚀 Common Development Tasks

### Task: Run the Full Pipeline
```bash
cd financial-normalizer
python src/main.py --input data/input/sample_trial_balance.csv \
                    --output data/output/ \
                    --ebitda \
                    --verbose
```

### Task: Add a Test
```python
# In run_tests.py, add to appropriate test function:
def test_your_feature():
    your_obj = YourClass()
    result = your_obj.do_something()
    assert result is not None
```

### Task: Debug an Issue
```python
# Add debug output
import logging
logging.basicConfig(level=logging.DEBUG)

# Add print statements
print(f"DEBUG: variable_name = {variable_name}")

# Run with verbose flag
python src/main.py --verbose
```

### Task: Add New Dependency
```bash
# Install it
pip install new_package

# Add to requirements.txt
echo "new_package==1.2.3" >> financial-normalizer/requirements.txt

# Update import
from new_package import SomeClass
```

---

## 🔗 Related Documentation

- [QUICK_START.md](QUICK_START.md) - How to use the app
- [PROJECT_REVIEW.md](PROJECT_REVIEW.md) - Technical deep dive
- [CONTRIBUTING.md](CONTRIBUTING.md) - Contributing guidelines
- [README.md](README.md) - Project overview

---

## ✅ Development Checklist

Before committing code:
- [ ] Code runs without errors
- [ ] Tests pass: `python run_tests.py`
- [ ] No new warnings in output
- [ ] Code follows style guidelines
- [ ] Docstrings added for public methods
- [ ] Type hints included
- [ ] No print() statements (use logging)
- [ ] Error handling in place
- [ ] Commit message is clear
- [ ] Documentation updated if needed

---

## 🤔 FAQ

**Q: How do I add a new file format (not CSV)?**
A: Implement a new parser class in `src/ingestion/` following the `TrialBalanceParser` interface.

**Q: How do I change the EBITDA calculation?**
A: Edit `AdjustmentCalculator` in `src/normalization/adjustments.py`, specifically the `calculate_reported_ebitda()` method.

**Q: How do I add a new suspicious pattern?**
A: Edit `detect_suspicious_patterns()` in `src/classification/classifier.py`.

**Q: Can I modify the configuration without touching code?**
A: Yes! Edit `config/categories.yaml` to add industries or change account mappings.

**Q: How do I test my changes?**
A: Run `python run_tests.py` to ensure everything still works.

---

Happy coding! 🚀
