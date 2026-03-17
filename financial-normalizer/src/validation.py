"""
Standalone, testable field-level validation engine.

All rules live here as declarative ValidationRule instances.
The UI, app_service, and CLI can all import this without Streamlit.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


logger = logging.getLogger(__name__)


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass
class ValidationRule:
    """A single, declarative validation rule."""
    field: str
    severity: Severity
    # condition(value, all_fields) -> True when rule IS violated
    condition: Callable[[Any, Dict[str, Any]], bool]
    message: str


@dataclass
class ValidationResult:
    field: str
    severity: Severity
    message: str
    triggered: bool = True


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _safe_float(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Default rules
# ---------------------------------------------------------------------------

def _revenue_positive(value: Any, _fields: Dict[str, Any]) -> bool:
    v = _safe_float(value)
    return v is not None and v <= 0


def _ebitda_margin_range(value: Any, _fields: Dict[str, Any]) -> bool:
    v = _safe_float(value)
    return v is not None and not (-100.0 <= v <= 100.0)


def _balance_sheet_equation(value: Any, fields: Dict[str, Any]) -> bool:
    ta = _safe_float(value)
    tl = _safe_float(fields.get("total_liabilities"))
    eq = _safe_float(fields.get("equity"))
    if ta is None or tl is None or eq is None:
        return False
    tolerance = max(abs(ta) * 0.01, 1.0)
    return abs(ta - (tl + eq)) > tolerance


def _gross_profit_le_revenue(value: Any, fields: Dict[str, Any]) -> bool:
    gp = _safe_float(value)
    rev = _safe_float(fields.get("revenue"))
    return gp is not None and rev is not None and gp > rev


def _opex_non_negative(value: Any, _fields: Dict[str, Any]) -> bool:
    v = _safe_float(value)
    return v is not None and v < 0


def _debt_equity_ratio(value: Any, fields: Dict[str, Any]) -> bool:
    debt = _safe_float(value)
    eq = _safe_float(fields.get("equity"))
    return (debt is not None and eq is not None
            and eq > 0 and debt / eq > 10.0)


def _working_capital_positive(value: Any, fields: Dict[str, Any]) -> bool:
    ca = _safe_float(value)
    cl = _safe_float(fields.get("current_liabilities"))
    return ca is not None and cl is not None and (ca - cl) <= 0


def _interest_coverage(value: Any, fields: Dict[str, Any]) -> bool:
    ebit = _safe_float(value)
    ii = _safe_float(fields.get("interest_expense"))
    return (ebit is not None and ii is not None
            and ii > 0 and ebit / ii < 1.0)


DEFAULT_RULES: List[ValidationRule] = [
    ValidationRule(
        field="revenue",
        severity=Severity.ERROR,
        condition=_revenue_positive,
        message="Revenue must be positive.",
    ),
    ValidationRule(
        field="ebitda_margin",
        severity=Severity.ERROR,
        condition=_ebitda_margin_range,
        message="EBITDA margin must be between -100% and +100%.",
    ),
    ValidationRule(
        field="total_assets",
        severity=Severity.ERROR,
        condition=_balance_sheet_equation,
        message="Total assets must equal total liabilities + equity (within 1% tolerance).",
    ),
    ValidationRule(
        field="gross_profit",
        severity=Severity.ERROR,
        condition=_gross_profit_le_revenue,
        message="Gross profit cannot exceed revenue.",
    ),
    ValidationRule(
        field="operating_expenses",
        severity=Severity.ERROR,
        condition=_opex_non_negative,
        message="Operating expenses cannot be negative.",
    ),
    ValidationRule(
        field="total_debt",
        severity=Severity.WARNING,
        condition=_debt_equity_ratio,
        message="Debt-to-equity ratio exceeds 10x — verify source data.",
    ),
    ValidationRule(
        field="current_assets",
        severity=Severity.WARNING,
        condition=_working_capital_positive,
        message="Working capital is negative or zero — company may face liquidity risk.",
    ),
    ValidationRule(
        field="ebit",
        severity=Severity.WARNING,
        condition=_interest_coverage,
        message="Interest coverage ratio is below 1.0 — debt service may not be covered.",
    ),
]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class ValidationEngine:
    """Runs declarative validation rules against a field dict."""

    def __init__(self, rules: Optional[List[ValidationRule]] = None) -> None:
        self.rules: List[ValidationRule] = rules if rules is not None else DEFAULT_RULES

    def validate(
        self,
        fields: Dict[str, Any],
        industry: Optional[str] = None,  # reserved for future industry-specific rules
    ) -> List[ValidationResult]:
        """Return only triggered ValidationResult items."""
        results: List[ValidationResult] = []
        for rule in self.rules:
            value = fields.get(rule.field)
            try:
                triggered = rule.condition(value, fields)
            except (TypeError, ValueError, KeyError, AttributeError, ZeroDivisionError) as exc:
                logger.warning("Validation rule '%s' failed for field '%s': %s", rule.message, rule.field, exc)
                triggered = False
            if triggered:
                results.append(ValidationResult(
                    field=rule.field,
                    severity=rule.severity,
                    message=rule.message,
                ))
        return results

    def has_blocking_errors(self, fields: Dict[str, Any], industry: Optional[str] = None) -> bool:
        return any(r.severity == Severity.ERROR for r in self.validate(fields, industry))
