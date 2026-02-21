# Financial Normalizer

A Python-based financial statement normalization engine that parses trial balance data, classifies accounts, applies adjustments, and computes reported, adjusted, and normalized EBITDA.

The system is designed as a modular financial data pipeline with clearly separated stages for ingestion, classification, adjustment logic, and metric calculation.

---

## Purpose

This project models a simplified financial normalization workflow similar to what is performed in financial due diligence and internal reporting. Given general ledger (GL) or trial balance data, the engine:

- Parses structured financial data
- Maps accounts to standardized categories
- Applies adjustment rules (e.g., non-recurring items, reclassifications)
- Computes EBITDA metrics at multiple levels
- Outputs normalized financial views

The emphasis is on transparent transformation of financial data rather than UI or presentation.

---

## System Architecture

The application follows a linear pipeline:

```
Trial Balance Input
        ↓
[Ingestion Layer]
        ↓
[Classification Layer]
        ↓
[Adjustment Layer]
        ↓
[Metric Engine]
        ↓
Normalized Output Files
```

Each stage operates independently and transforms structured data from the previous stage.

---

## Project Structure

```
financial-normalizer/
├── config/
│   └── categories.yaml        # Account classification and adjustment rules
│
├── data/
│   ├── input/                 # Input trial balance files
│   └── output/                # Generated outputs
│
├── src/
│   ├── main.py                # CLI entry point
│   │
│   ├── ingestion/
│   │   └── trial_balance_parser.py
│   │
│   ├── classification/
│   │   └── classifier.py
│   │
│   ├── normalization/
│   │   ├── adjustments.py
│   │   └── engine.py
│   │
│   └── export/                # Output formatting (in progress)
│
├── run_tests.py               # Integration-style test runner
└── verify_setup.py            # Environment verification
```

---

## Core Concepts

### Transactions as Source of Truth

All calculations are derived from parsed trial balance data. No financial metrics (e.g., EBITDA) are stored as persistent values — metrics are computed from underlying classified transaction data at runtime.

### Classification via Configuration

Account classification rules are defined in `config/categories.yaml`. This file controls:

- Industry templates
- Revenue mappings
- COGS mappings
- Operating expense mappings
- Adjustment categories

This allows extension without modifying core logic.

### Adjustment Layer

The adjustment layer applies structured rules to classified data, including:

- Add-backs
- Reclassifications
- Non-recurring exclusions
- Intercompany eliminations (if applicable)

Raw financial data remains intact; adjustments are layered logically.

### EBITDA Calculation

The engine computes three variants:

| Metric | Description |
|---|---|
| **Reported EBITDA** | Derived directly from classified accounts |
| **Adjusted EBITDA** | Excludes flagged non-recurring items |
| **Normalized EBITDA** | Applies industry-specific normalization rules |

All values are calculated dynamically from structured data.

---

## Installation

**Requirements:** Python 3.12+

```bash
git clone <repo-url>
cd financial-normalizer
pip install -r requirements.txt
```

Verify your environment:

```bash
python verify_setup.py
```

---

## Usage

**Process sample data:**

```bash
python src/main.py --ebitda
```

**Process a custom file:**

```bash
python src/main.py --input path/to/trial_balance.csv --output results/ --industry saas_tech --ebitda
```

**View help:**

```bash
python src/main.py --help
```

---

## Data Flow

### Step 1 – Ingestion
- Parses CSV/Excel trial balance
- Standardizes column names
- Converts rows into structured transaction records

### Step 2 – Classification
- Maps accounts to categories using YAML rules
- Produces categorized financial dataset

### Step 3 – Adjustments
- Applies defined normalization logic
- Flags and adjusts qualifying entries

### Step 4 – Metric Engine
- Aggregates classified data
- Computes EBITDA variants
- Outputs normalized financial views

---

## Extending the System

### Add a new industry

1. Modify `config/categories.yaml`
2. Define account mappings
3. Define applicable adjustment logic
4. Run with:

```bash
python src/main.py --industry your_industry
```

### Extend existing logic

| Area | File |
|---|---|
| Classification logic | `classification/classifier.py` |
| Adjustment logic | `normalization/adjustments.py` |
| Metric calculations | `normalization/engine.py` |

---

## Testing

Run integration tests:

```bash
python run_tests.py
```

Run setup verification:

```bash
python verify_setup.py
```

---

## Design Principles

- Clear separation of concerns
- Configuration-driven classification
- Derived financial metrics (no stored EBITDA)
- Transparent data transformation
- Minimal hidden state
- Extendable without structural refactoring

---

## Limitations

- No web interface
- Export module incomplete
- Not intended as a full accounting system
- Assumes reasonably structured input data

---

## Summary

This project models a structured financial normalization workflow using modular Python components. It is intended as:

- A learning tool for financial data transformation
- A prototype normalization engine
- A foundation for further financial analytics development
