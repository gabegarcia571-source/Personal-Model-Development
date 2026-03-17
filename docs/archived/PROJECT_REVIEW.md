````markdown
# Project Review (archived)

This archived document contains a historical project review and notes.

## Summary

- Project: Financial Statement Normalization Engine
- Scope: Ingest trial balances, classify accounts, apply normalization adjustments, export normalized views
- Status: Active development; documentation consolidated into README/USAGE

## Key Observations (archival)

- Modular design simplifies adding new input parsers
- DataFrame-first approach aids rapid prototyping
- Missing: extensive unit tests and a visualization module

## Recommendations (archival)

1. Add `input_router.py` to centralize format detection
2. Add `visualizer.py` to produce analyst-friendly outputs
3. Expand test coverage to include edge cases and mixed currencies

````
