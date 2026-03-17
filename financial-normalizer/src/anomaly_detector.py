"""
Standalone anomaly detection module.

Compares key financial metrics against industry benchmark ranges
defined in config/benchmarks.yaml. Fully independent of Streamlit.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


@dataclass
class AnomalyEntry:
    field: str
    value: float
    expected_range: Tuple[float, float]
    unit: str
    industry: str
    description: str
    message: str


class AnomalyDetector:
    """Detects out-of-range metrics using industry benchmark data."""

    # Optional aliases where input field names differ from benchmark metric keys.
    FIELD_ALIASES: Dict[str, str] = {
        "interest_coverage": "interest_coverage_ratio",
    }

    def __init__(self, benchmarks_path: Optional[str] = None) -> None:
        if benchmarks_path is None:
            benchmarks_path = str(
                Path(__file__).resolve().parents[1] / "config" / "benchmarks.yaml"
            )
        self.benchmarks: Dict[str, Any] = self._load_benchmarks(benchmarks_path)

    def _load_benchmarks(self, path: str) -> Dict[str, Any]:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return yaml.safe_load(fh) or {}
        except FileNotFoundError:
            return {}

    def _get_benchmark(
        self, metric: str, industry: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Return benchmark dict for a metric, preferring industry-specific over defaults."""
        if industry and industry in self.benchmarks:
            industry_benchmarks = self.benchmarks[industry]
            if metric in industry_benchmarks:
                return industry_benchmarks[metric]

        defaults = self.benchmarks.get("defaults", {})
        return defaults.get(metric)

    def detect(
        self,
        fields: Dict[str, Any],
        industry: Optional[str] = None,
    ) -> List[AnomalyEntry]:
        """Return AnomalyEntry items for any metric outside expected range."""
        anomalies: List[AnomalyEntry] = []
        effective_industry = industry or "defaults"

        # Prefer metrics defined in benchmark defaults so this is data-driven.
        defaults = self.benchmarks.get("defaults", {})
        benchmark_metrics = [k for k in defaults.keys() if k != "source"]

        # Merge aliases into a normalized field map.
        normalized_fields: Dict[str, Any] = dict(fields)
        for input_name, benchmark_key in self.FIELD_ALIASES.items():
            if benchmark_key not in normalized_fields and input_name in normalized_fields:
                normalized_fields[benchmark_key] = normalized_fields[input_name]

        for benchmark_key in benchmark_metrics:
            raw_value = normalized_fields.get(benchmark_key)
            if raw_value is None:
                continue

            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                continue

            benchmark = self._get_benchmark(benchmark_key, industry)
            if benchmark is None:
                continue

            low = benchmark.get("min")
            high = benchmark.get("max")
            unit = benchmark.get("unit", "")
            description = benchmark.get("description", benchmark_key)

            if low is None or high is None:
                continue

            if value < low or value > high:
                anomalies.append(AnomalyEntry(
                    field=benchmark_key,
                    value=value,
                    expected_range=(low, high),
                    unit=unit,
                    industry=effective_industry,
                    description=description,
                    message=(
                        f"{benchmark_key} = {value:.1f}{unit} is outside the expected range "
                        f"[{low:.1f}{unit}, {high:.1f}{unit}] for {effective_industry}. "
                        f"({description})"
                    ),
                ))

        return anomalies

    def detect_from_pipeline_result(
        self,
        pipeline_result: Dict[str, Any],
        industry: Optional[str] = None,
    ) -> List[AnomalyEntry]:
        """Extract benchmark-relevant fields from run_pipeline() output and detect anomalies."""
        metrics_report = pipeline_result.get("metrics_report") or {}
        profitability = metrics_report.get("profitability", {})
        health = metrics_report.get("health", {})

        derived_fields: Dict[str, Any] = {}

        # Map pipeline metric output to benchmark field names
        if "gross_margin_%" in profitability:
            derived_fields["gross_margin"] = profitability["gross_margin_%"]
        if "ebitda_margin_%" in profitability:
            derived_fields["ebitda_margin"] = profitability["ebitda_margin_%"]
        if "operating_margin_%" in profitability:
            derived_fields["opex_ratio"] = 100.0 - (profitability["operating_margin_%"] or 0)
        if "debt_to_equity" in health:
            derived_fields["debt_to_equity"] = health["debt_to_equity"]
        if "current_ratio" in health:
            derived_fields["current_ratio"] = health["current_ratio"]
        if "interest_coverage_ratio" in health:
            derived_fields["interest_coverage_ratio"] = health["interest_coverage_ratio"]

        return self.detect(derived_fields, industry)
