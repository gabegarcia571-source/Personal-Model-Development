Financial Normalizer

A Python-based financial statement normalization engine that parses trial balance data, classifies accounts, applies adjustments, and computes reported, adjusted, and normalized EBITDA.

The system is designed as a modular financial data pipeline with clearly separated stages for ingestion, classification, adjustment logic, and metric calculation.

Purpose

This project models a simplified financial normalization workflow similar to what is performed in financial due diligence and internal reporting.

Given general ledger (GL) or trial balance data, the engine:

Parses structured financial data

Maps accounts to standardized categories

Applies adjustment rules (e.g., non-recurring items, reclassifications)

Computes EBITDA metrics at multiple levels

Outputs normalized financial views

The emphasis is on transparent transformation of financial data rather than UI or presentation.

System Architecture

The application follows a linear pipeline:

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

Each stage operates independently and transforms structured data from the previous stage.

Project Structure
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
Core Concepts
1. Transactions as Source of Truth

All calculations are derived from parsed trial balance data.
No financial metrics (e.g., EBITDA) are stored as persistent values.

Metrics are computed from underlying classified transaction data at runtime.

2. Classification via Configuration

Account classification rules are defined in:

config/categories.yaml

This file controls:

Industry templates

Revenue mappings

COGS mappings

Operating expense mappings

Adjustment categories

This allows extension without modifying core logic.

3. Adjustment Layer

The adjustment layer applies structured rules to classified data, including:

Add-backs

Reclassifications

Non-recurring exclusions

Intercompany eliminations (if applicable)

Raw financial data remains intact; adjustments are layered logically.

4. EBITDA Calculation

The engine computes:

Reported EBITDA – Derived directly from classified accounts

Adjusted EBITDA – Excludes flagged non-recurring items

Normalized EBITDA – Applies industry-specific normalization rules

All values are calculated dynamically from structured data.

Installation
Requirements

Python 3.12+

pip

Setup
git clone <repo-url>
cd financial-normalizer
pip install -r requirements.txt

Verify environment:

python verify_setup.py
Usage
Process Sample Data
python src/main.py --ebitda
Process Custom File
python src/main.py \
  --input path/to/trial_balance.csv \
  --output results/ \
  --industry saas_tech \
  --ebitda
View Help
python src/main.py --help
Data Flow in Detail
Step 1 – Ingestion

Parses CSV/Excel trial balance

Standardizes column names

Converts rows into structured transaction records

Step 2 – Classification

Maps accounts to categories using YAML rules

Produces categorized financial dataset

Step 3 – Adjustments

Applies defined normalization logic

Flags and adjusts qualifying entries

Step 4 – Metric Engine

Aggregates classified data

Computes EBITDA variants

Outputs normalized financial views

Extending the System

To add a new industry:

Modify config/categories.yaml

Define account mappings

Define applicable adjustment logic

Run with:

python src/main.py --industry your_industry

To extend logic:

Classification logic → classification/classifier.py

Adjustment logic → normalization/adjustments.py

Metric calculations → normalization/engine.py

Testing

Run integration tests:

python run_tests.py

Run setup verification:

python verify_setup.py
Design Principles

Clear separation of concerns

Configuration-driven classification

Derived financial metrics (no stored EBITDA)

Transparent data transformation

Minimal hidden state

Extendable without structural refactoring

Limitations

No web interface

Export module incomplete

Not intended as a full accounting system

Assumes reasonably structured input data

Summary

This project models a structured financial normalization workflow using modular Python components.

It is intended as:

A learning tool for financial data transformation

A prototype normalization engine

A foundation for further financial analytics development

next steps:

a. file upload directory
File Upload (any type)
        ↓
File Reader (PDF → text, Excel → DataFrame, etc.)
        ↓
Document Classifier (what kind of document is this?)
        ↓
LLM Extraction Layer (pull specific financial fields)
        ↓
Existing Parsers (map to internal schema)
        ↓
Classification → Adjustments → Normalization → EBITDA

b. extensive systematic calucalations

fix list:
1. Duplicate rows in classification
classify_dataframe() merge logic is creating duplicates. O&M appears 3x, insurance 2x. Inflating all numbers.
2. Wrong account type keywords in categories.yaml
These are misclassified and need fixing:

Property insurance → opex not asset
Equipment maintenance → opex not asset
Tax equity structuring fee → interest not equity

3. Missing keywords causing unknown classifications
Add these to categories.yaml:

Legal fees → opex
Operations and maintenance → opex
Professional services → opex
Grid interconnection fees → opex
Feasibility study costs → opex
Environmental compliance → opex
Regulatory compliance → opex
Swap breakage → interest

4. Metrics section
Verify it actually printed at the end — you didn't share that part of the output. If it didn't print, the generate_view() method name mismatch still needs resolving.
5. Adjustment coverage
Only management fee got flagged. Legal fees, feasibility costs, swap breakage, and construction interest should all be flagged as non-recurring add-backs. That's an adjustment rule expansion in categories.yaml.