# Usage and Input Formats

This document describes accepted input file types, how to run the pipeline, and what outputs are produced.

## Accepted input formats

- Trial balance CSV (standard GL rows): columns such as `Account`, `Account_Code`, `Account_Name`, `Description`, `Debit`, `Credit`, `Amount`, `Entity`, `Period`, `Date`.
- Multi-sheet Excel workbooks: the router will look for sensible sheet names (`Trial Balance`, `GL`, `Transactions`, `Income Statement`) and normalize the first matching sheet.
- Public financial statements (income statement format): single-sheet P&L where rows are line items; will be mapped to `Account_Name` + `Amount`.
- P&L exports from QuickBooks, Xero, NetSuite: common export layouts are handled via built-in mappers; ambiguous/unknown layouts will be routed to the flexible parser.

## Running the tool (CLI)

From the repository root run the main pipeline. By default, the sample data is used.

```bash
python financial-normalizer/src/main.py --input financial-normalizer/data/input/sample_trial_balance.csv --output financial-normalizer/data/output/ --ebitda
```

Key CLI flags (see `--help` for full list):
- `--input` / `-i`: input file path (CSV or XLSX)
- `--output` / `-o`: output directory
- `--industry`: classification context (`saas_tech`, `manufacturing`, `financial_services`)
- `--ebitda`: calculate and save EBITDA metrics
- `--detect-patterns`: enable suspicious pattern detection

## Outputs produced

When run end-to-end the pipeline produces (by default) CSVs in the output directory:

- `1_parsed_transactions.csv`: parsed and normalized transaction rows
- `2_classified_accounts.csv`: parsed rows merged with classification columns (`Account_Type`, `Adjustment_Type`, ...)
- `3_ebitda_metrics.csv`: EBITDA summary rows (`reported`, `adjusted`, `normalized`)
- `4_normalized_summary.csv`: normalized income statement (if available)
- `adjustments_*.csv` / `eliminations_*.csv`: optional files when adjustments/consolidation are present

The visualization module (planned in Task 3) will read engine outputs and produce charts (no files written by default).

## Error handling & tips

- If the parser cannot find an `amount` column, it will attempt to use `debit` and `credit` to compute amounts.
- For multi-sheet workbooks, ensure the sheet name includes `Trial`/`Balance`/`Income` where possible to help routing.
- If column names are ambiguous, the optional `anthropic` SDK (if installed and configured) may be used as a fallback to interpret column semantics.

## Next steps

- See `README.md` for project layout and quick setup.
- After Task 2 completes, `input_router.py` will expose additional mapping hooks for QuickBooks/Xero/NetSuite exports.
