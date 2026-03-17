"""
Financial Normalizer — Filing Comparison Module.

Provides side-by-side comparison of two parsed financial filings.
This module is UI-independent and can be called from CLI or Streamlit.

Key exports:
    FilingData          — dataclass for a single filing's field values
    ComparisonRow       — dataclass for a single compared field row
    ComparisonResult    — dataclass contract for compare_filings() output
    compare_filings()   — main comparison entry point
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------


@dataclass
class FilingData:
    """A single filing's metadata and field values for comparison purposes."""

    name: str                            # display name (e.g. filename + statement type)
    statement_type: str                  # e.g. "income_statement"
    fields: Dict[str, Any]              # field_name -> value (floats preferred)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComparisonRow:
    """Result for a single compared field."""

    field: str                           # internal field name
    value_a: Optional[float]             # value from filing A (None if missing)
    value_b: Optional[float]             # value from filing B (None if missing)
    delta_abs: Optional[float]           # absolute difference (B - A)
    delta_pct: Optional[float]           # relative difference %
    status: str                          # "ok" | "threshold_exceeded" | "missing"


@dataclass
class ComparisonResult:
    """Full comparison result — the contract returned by compare_filings()."""

    name_a: str
    name_b: str
    threshold_pct: float
    rows: List[ComparisonRow]
    missing_fields: List[Dict[str, Any]]     # fields present in one filing only
    anomalies_unique_a: List[str]            # field names with anomalies only in A
    anomalies_unique_b: List[str]            # field names with anomalies only in B

    def as_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict (compatible with reporting.py)."""
        return {
            "name_a": self.name_a,
            "name_b": self.name_b,
            "threshold_pct": self.threshold_pct,
            "rows": [
                {
                    "field": r.field,
                    "value_a": r.value_a,
                    "value_b": r.value_b,
                    "delta_abs": r.delta_abs,
                    "delta_pct": r.delta_pct,
                    "status": r.status,
                }
                for r in self.rows
            ],
            "missing_fields": self.missing_fields,
            "anomalies_unique_a": self.anomalies_unique_a,
            "anomalies_unique_b": self.anomalies_unique_b,
        }


# ---------------------------------------------------------------------------
# Numeric fields eligible for comparison
# ---------------------------------------------------------------------------

_NUMERIC_FIELDS = [
    "revenue",
    "gross_profit",
    "operating_expenses",
    "ebit",
    "ebitda_margin",
    "interest_expense",
    "total_assets",
    "current_assets",
    "total_liabilities",
    "current_liabilities",
    "equity",
    "total_debt",
    "operating_cash_flow",
    "investing_cash_flow",
    "financing_cash_flow",
    "gross_margin",
    "opex_ratio",
    "revenue_growth",
    "debt_to_equity",
    "interest_coverage_ratio",
    "current_ratio",
    "ebitda",
    "ev",
]


# ---------------------------------------------------------------------------
# Main comparison function
# ---------------------------------------------------------------------------


def compare_filings(
    filing_a: FilingData,
    filing_b: FilingData,
    threshold_pct: float = 10.0,
    anomaly_fields_a: Optional[List[str]] = None,
    anomaly_fields_b: Optional[List[str]] = None,
) -> ComparisonResult:
    """Compare two financial filings field-by-field.

    Args:
        filing_a: First filing's data and fields.
        filing_b: Second filing's data and fields.
        threshold_pct: Delta percentage above which a row is flagged
            as ``"threshold_exceeded"``.  Default 10%.
        anomaly_fields_a: Field names from anomaly detection on filing A.
        anomaly_fields_b: Field names from anomaly detection on filing B.

    Returns:
        A ComparisonResult dataclass.
    """
    anomaly_fields_a = anomaly_fields_a or []
    anomaly_fields_b = anomaly_fields_b or []

    # Determine which fields to compare: union of numeric keys present in either
    all_fields = sorted(
        {
            k for k in list(filing_a.fields.keys()) + list(filing_b.fields.keys())
            if k in _NUMERIC_FIELDS
        }
    )

    rows: List[ComparisonRow] = []
    missing_fields: List[Dict[str, Any]] = []

    for fname in all_fields:
        raw_a = filing_a.fields.get(fname)
        raw_b = filing_b.fields.get(fname)

        val_a = _to_float(raw_a)
        val_b = _to_float(raw_b)

        has_a = val_a is not None
        has_b = val_b is not None

        if not has_a and not has_b:
            continue   # not meaningful to compare missing-on-both

        if not has_a or not has_b:
            # Field present in one filing but not the other
            status = "missing"
            present_in = filing_a.name if has_a else filing_b.name
            absent_from = filing_b.name if has_a else filing_a.name
            missing_fields.append({
                "field": fname,
                "present_in": present_in,
                "absent_from": absent_from,
            })
            rows.append(ComparisonRow(
                field=fname,
                value_a=val_a,
                value_b=val_b,
                delta_abs=None,
                delta_pct=None,
                status="missing",
            ))
            continue

        delta_abs = val_b - val_a
        if val_a != 0:
            delta_pct = abs(delta_abs / val_a) * 100.0
        else:
            delta_pct = 0.0 if val_b == 0 else 100.0

        status = "threshold_exceeded" if delta_pct > threshold_pct else "ok"

        rows.append(ComparisonRow(
            field=fname,
            value_a=val_a,
            value_b=val_b,
            delta_abs=round(delta_abs, 4),
            delta_pct=round(delta_pct, 2),
            status=status,
        ))

    # Anomalies unique to each filing
    set_a = set(anomaly_fields_a)
    set_b = set(anomaly_fields_b)
    anomalies_unique_a = sorted(set_a - set_b)
    anomalies_unique_b = sorted(set_b - set_a)

    logger.info(
        "Comparison %s vs %s: %d fields compared, %d missing, %d threshold exceeded",
        filing_a.name,
        filing_b.name,
        len(rows),
        len(missing_fields),
        sum(1 for r in rows if r.status == "threshold_exceeded"),
    )

    return ComparisonResult(
        name_a=filing_a.name,
        name_b=filing_b.name,
        threshold_pct=threshold_pct,
        rows=rows,
        missing_fields=missing_fields,
        anomalies_unique_a=anomalies_unique_a,
        anomalies_unique_b=anomalies_unique_b,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_float(value: Any) -> Optional[float]:
    """Convert a value to float; return None if not convertible."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None  # boolean flags are not comparable numerically
    try:
        result = float(value)
        if result != result:  # NaN check
            return None
        return result
    except (TypeError, ValueError):
        return None
