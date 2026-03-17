"""
Financial Normalizer — Settings Loader.

Loads config/settings.yaml at startup and merges with environment variable overrides.
Environment variables take precedence over YAML values.

Environment variable mapping:
    LOG_LEVEL / FINORM_LOG_LEVEL -> logging.log_level
    FINORM_IMBALANCE_TOLERANCE  -> pipeline.imbalance_tolerance
    FINORM_ANOMALY_THRESHOLD    -> anomaly.threshold_pct
    FINORM_DEFAULT_INDUSTRY     -> pipeline.default_industry
    FINORM_OUTPUT_DIR           -> pipeline.output_dir
    FINORM_MAX_FILE_SIZE_MB     -> ingestion.max_file_size_mb
    PORT                        -> ui.port

Usage:
    from src.settings import settings
    log_level = settings.log_level
    tolerance = settings.imbalance_tolerance
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

_SETTINGS_PATH = Path(__file__).resolve().parents[1] / "config" / "settings.yaml"


def _load_yaml(path: Path) -> Dict[str, Any]:
    """Load YAML file; return empty dict on missing or parse error."""
    if not path.exists():
        logger.warning("Settings file not found at %s — using defaults", path)
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        logger.error("Failed to parse settings file %s: %s — using defaults", path, exc)
        return {}


def _get_env(key: str, default: Any) -> Any:
    """Return environment variable value cast to same type as default, or default."""
    raw = os.environ.get(key)
    if raw is None:
        return default
    if isinstance(default, bool):
        return raw.lower() in ("1", "true", "yes")
    if isinstance(default, int):
        try:
            return int(raw)
        except ValueError:
            return default
    if isinstance(default, float):
        try:
            return float(raw)
        except ValueError:
            return default
    return raw  # string


class Settings:
    """Runtime configuration object populated from YAML + environment variables."""

    def __init__(self, config: Dict[str, Any]) -> None:
        logging_cfg = config.get("logging", {})
        pipeline_cfg = config.get("pipeline", {})
        anomaly_cfg = config.get("anomaly", {})
        ingestion_cfg = config.get("ingestion", {})
        ui_cfg = config.get("ui", {})

        # Logging
        self.log_level: str = os.environ.get("LOG_LEVEL") or str(
            _get_env(
                "FINORM_LOG_LEVEL",
                logging_cfg.get("log_level", "INFO"),
            )
        )
        self.log_format: str = logging_cfg.get(
            "format", "%(asctime)s %(levelname)-8s %(name)s — %(message)s"
        )
        self.log_date_format: str = logging_cfg.get("date_format", "%Y-%m-%d %H:%M:%S")

        # Pipeline
        self.imbalance_tolerance: float = float(_get_env(
            "FINORM_IMBALANCE_TOLERANCE",
            pipeline_cfg.get("imbalance_tolerance", 0.01),
        ))
        default_industry_yaml = pipeline_cfg.get("default_industry") or None
        raw_industry_env = os.environ.get("FINORM_DEFAULT_INDUSTRY")
        self.default_industry: Optional[str] = raw_industry_env or default_industry_yaml
        self.output_dir: str = _get_env(
            "FINORM_OUTPUT_DIR",
            pipeline_cfg.get("output_dir", "data/output"),
        )
        self.pipeline_ebitda: bool = bool(pipeline_cfg.get("ebitda", True))
        self.pipeline_detect_patterns: bool = bool(pipeline_cfg.get("detect_patterns", True))

        # Anomaly
        self.anomaly_threshold_pct: float = float(_get_env(
            "FINORM_ANOMALY_THRESHOLD",
            anomaly_cfg.get("threshold_pct", 10.0),
        ))

        # Ingestion
        self.max_file_size_mb: int = int(_get_env(
            "FINORM_MAX_FILE_SIZE_MB",
            ingestion_cfg.get("max_file_size_mb", 50),
        ))
        self.supported_extensions: List[str] = ingestion_cfg.get(
            "supported_extensions",
            [".csv", ".xlsx", ".xls", ".pdf", ".xml", ".xbrl"],
        )

        # UI
        self.ui_port: int = int(_get_env(
            "PORT",
            ui_cfg.get("port", 8501),
        ))

    def configure_logging(self) -> None:
        """Apply log level and format from settings to the root logger."""
        numeric_level = getattr(logging, self.log_level.upper(), logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(self.log_format, datefmt=self.log_date_format))
        root = logging.getLogger()
        root.setLevel(numeric_level)
        # Replace all handlers with the configured one
        root.handlers.clear()
        root.addHandler(handler)

    def __repr__(self) -> str:
        return (
            f"Settings(log_level={self.log_level!r}, "
            f"imbalance_tolerance={self.imbalance_tolerance}, "
            f"default_industry={self.default_industry!r}, "
            f"max_file_size_mb={self.max_file_size_mb})"
        )


# Module-level singleton
settings = Settings(_load_yaml(_SETTINGS_PATH))
