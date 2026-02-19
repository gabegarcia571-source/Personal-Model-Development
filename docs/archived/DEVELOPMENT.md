````markdown
# Development Notes

This archived document contains development notes and design discussions. It is preserved for historical context.

---

## Repository Architecture (archival snapshot)

- `financial-normalizer/`
  - `src/` - core implementation
    - `ingestion/` - trial balance parsers & synthetic data generators
    - `classification/` - account classification logic
    - `normalization/` - normalization engines and adjustments
    - `export/` - export helpers
  - `config/` - mapping configs and categories
  - `data/` - sample inputs and outputs
  - `run_tests.py` - test harness

---

## Design Notes

- The code follows an ingestion → classification → normalization → export pipeline.
- DataFrames are the primary in-memory representation.
- The engine attempts to produce a `NormalizedFinancialView` with before/after comparisons.

---

## Development TODOs (archival snapshot)

1. Implement `input_router.py` to abstract different source layouts
2. Implement `visualizer.py` to produce before/after waterfalls
3. Add more unit tests for adjustments and edge cases
4. Improve CLI and logging output

---

## Notes on Testing

- Tests are lightweight and primarily verify imports and simple integration paths.
- Add test fixtures for varied trial balance layouts.

---

## Historical Decisions

- Decision to keep `pandas` as the central processing library due to wide adoption.
- YAML configs for industry categories for easy updates without code changes.

---

## Contact

For details about decisions in this archive, see project maintainers or PR history on GitHub.

````
