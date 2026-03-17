# Financial Normalizer

Financial Normalizer ingests trial balances and financial statements (CSV, Excel, PDF, XBRL), classifies accounts, computes normalized outputs, and produces analyst-friendly reports. It includes a Streamlit UI for interactive review/edit/validation and a CLI for batch processing and CI. The project is designed for auditability with anomaly detection, validation rules, and a persistent audit trail.

## Prerequisites

- Python 3.12
- Docker (for containerized usage)

## Quick Start

### Docker path

```bash
docker compose up --build app
```

Open: http://localhost:8501

Run CLI inside container:

```bash
CLI_COMMAND="validate" docker compose up --build cli
```

### Local path

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3.12 src/main.py validate
python3.12 src/main.py app
```

## CLI Reference

### Normalize pipeline

```bash
python src/main.py normalize --input data/input/sample_trial_balance.csv --output data/output --industry saas_tech --ebitda
```

Flags:
- `--input`, `-i`: input CSV path
- `--output`, `-o`: output directory
- `--industry`: one of configured industries in config/benchmarks.yaml
- `--ebitda`: include EBITDA step
- `--detect-patterns`: suspicious-pattern checks
- `--ev`: enterprise value for valuation metrics
- `--verbose`, `-v`: debug logging

### Validate + smoke-test

```bash
python src/main.py validate
python src/main.py smoke-test
```

### Report exports

```bash
python src/main.py report --output data/output --format csv
python src/main.py report --output data/output --format excel --report-file data/output/financial_report.xlsx
python src/main.py report --output data/output --format pdf --report-file data/output/financial_report.pdf
```

### Launch Streamlit app

```bash
python src/main.py app
```

## Run Tests

```bash
python run_tests.py
```

## Add a New Industry Benchmark

1. Open `config/benchmarks.yaml`.
2. Add a new top-level key (for example `telecom`).
3. Include:
   - `source`
   - `gross_margin`
   - `ebitda_margin`
   - `opex_ratio`
   - `revenue_growth`
   - `debt_to_equity`
   - `interest_coverage_ratio`
4. For each metric include `min`, `max`, `unit`, and `description`.
5. Add the key to the industry selector in `app/streamlit_app.py`.

## Add a New Validation Rule

1. Open `src/validation.py`.
2. Add a predicate function that accepts `(value, fields)`.
3. Append a `ValidationRule` entry to `DEFAULT_RULES` with `field`, `severity`, `condition`, and `message`.
4. Add or update tests in `run_tests.py` under validation tests.

## Runtime Configuration

Defaults live in `config/settings.yaml` and can be overridden by environment variables:

- `FINORM_LOG_LEVEL`
- `FINORM_IMBALANCE_TOLERANCE`
- `FINORM_ANOMALY_THRESHOLD`
- `FINORM_DEFAULT_INDUSTRY`
- `FINORM_OUTPUT_DIR`
- `FINORM_MAX_FILE_SIZE_MB`
- `PORT`

## Known Limitations

- PDF table extraction is heuristic-driven and may need manual review for complex multi-column annual reports.
- XBRL ingestion targets common us-gaap facts and does not perform full taxonomy validation.
- Comparison mode currently compares numeric fields detected in parsed filing data; sparse filings may yield fewer comparable rows.
- Very large reports are truncated in PDF output to keep rendering stable and fast.
