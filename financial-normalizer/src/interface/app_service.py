"""
Application service layer for the Streamlit UI.

All parsing, validation, anomaly detection, and pipeline calls live here.
streamlit_app.py is orchestration-only and delegates business logic to this module.
"""
from __future__ import annotations

import json
import logging
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

try:
    from ingestion.advanced_ingestion import AdvancedIngestionEngine
    from validation import ValidationEngine, ValidationResult
    from anomaly_detector import AnomalyDetector, AnomalyEntry
    from settings import settings
    from main import run_pipeline
except ModuleNotFoundError:
    from src.ingestion.advanced_ingestion import AdvancedIngestionEngine
    from src.validation import ValidationEngine, ValidationResult
    from src.anomaly_detector import AnomalyDetector, AnomalyEntry
    from src.settings import settings
    from src.main import run_pipeline

logger = logging.getLogger(__name__)


@dataclass
class IngestedFile:
    """Result of ingesting a single uploaded file."""

    filename: str
    status: str
    statement_type: str
    confidence: float
    warnings: List[str]
    error: Optional[str]
    dataframe: Optional[pd.DataFrame]
    metadata: Dict[str, Any]
    provenance: Dict[str, Any]


@dataclass
class SessionState:
    """Full session state for a single analyst run."""

    ingested_files: List[IngestedFile] = field(default_factory=list)
    prepared_input_path: str = ""
    fields: Dict[str, Any] = field(default_factory=dict)
    auto_filled_fields: List[str] = field(default_factory=list)
    field_provenance: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)
    pipeline_result: Optional[Dict[str, Any]] = None
    anomalies: List[Dict[str, Any]] = field(default_factory=list)


def _now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""

    return datetime.now(timezone.utc).isoformat()


def audit_event(
    session: SessionState,
    entry_type: str,
    actor: str,
    detail: str,
    diff: Optional[Dict[str, Any]] = None,
) -> None:
    """Append an audit entry to the session audit trail."""

    entry: Dict[str, Any] = {
        "timestamp": _now_iso(),
        "entry_type": entry_type,
        "actor": actor,
        "detail": detail,
    }
    if diff is not None:
        entry["diff"] = diff
    session.audit_trail.append(entry)


def validate_upload_file(file_path: str) -> Optional[str]:
    """Validate uploaded file extension and size limits before ingestion."""

    path = Path(file_path)
    if not path.exists():
        return "Uploaded file is missing."

    suffix = path.suffix.lower()
    if suffix not in set(settings.supported_extensions):
        return f"Unsupported file type: {suffix or 'unknown'}"

    max_bytes = int(settings.max_file_size_mb) * 1024 * 1024
    size = path.stat().st_size
    if size > max_bytes:
        return (
            f"File too large ({size / (1024 * 1024):.1f} MB). "
            f"Maximum allowed is {settings.max_file_size_mb} MB."
        )

    return None


def allowed_upload_extensions() -> List[str]:
    """Return configured upload extensions without leading dots."""

    return [ext.lstrip(".") for ext in settings.supported_extensions]


def max_upload_size_mb() -> int:
    """Return configured upload size limit in MB."""

    return int(settings.max_file_size_mb)


def ingest_file(filename: str, file_path: str) -> IngestedFile:
    """Ingest a single file and return a typed IngestedFile result."""

    validation_error = validate_upload_file(file_path)
    if validation_error:
        return IngestedFile(
            filename=filename,
            status="error",
            statement_type="unknown",
            confidence=0.0,
            warnings=[],
            error=validation_error,
            dataframe=None,
            metadata={},
            provenance={},
        )

    engine = AdvancedIngestionEngine()
    try:
        df, metadata = engine.ingest_file(file_path)
        warnings = metadata.get("warnings", [])
        status = "warning" if warnings else "success"
        provenance = _build_provenance(df, metadata, filename)
        return IngestedFile(
            filename=filename,
            status=status,
            statement_type=metadata.get("statement_type", "unknown"),
            confidence=float(metadata.get("confidence_level", 0.0)),
            warnings=warnings,
            error=None,
            dataframe=df,
            metadata=metadata,
            provenance=provenance,
        )
    except FileNotFoundError:
        logger.error("Ingestion failed: file not found (%s)", file_path)
        error_msg = "Uploaded file could not be found on server."
    except PermissionError:
        logger.error("Ingestion failed: permission denied (%s)", file_path)
        error_msg = "Uploaded file could not be read due to permissions."
    except ValueError as exc:
        logger.warning("Ingestion failed: invalid content for %s: %s", filename, exc)
        error_msg = "File content is invalid or unsupported."
    except OSError as exc:
        logger.error("Ingestion failed: OS error for %s: %s", filename, exc)
        error_msg = "I/O error while reading uploaded file."
    except RuntimeError as exc:
        logger.error("Ingestion failed: parser runtime error for %s: %s", filename, exc)
        error_msg = "Parser failed while processing uploaded file."
    except (TypeError, KeyError, AttributeError, LookupError, ArithmeticError) as exc:
        logger.exception("Unexpected ingestion failure while parsing uploaded file '%s': %s", filename, exc)
        error_msg = "Unexpected parsing error."

    return IngestedFile(
        filename=filename,
        status="error",
        statement_type="unknown",
        confidence=0.0,
        warnings=[],
        error=error_msg,
        dataframe=None,
        metadata={},
        provenance={},
    )


def _build_provenance(df: pd.DataFrame, metadata: Dict[str, Any], filename: str) -> Dict[str, Any]:
    """Build provenance metadata for each non-empty column in a dataframe."""

    prov: Dict[str, Any] = {}
    if df is None or df.empty:
        return prov
    source = metadata.get("source", filename)
    for col in df.columns:
        non_null = df[col].dropna()
        if non_null.empty:
            continue
        prov[col.lower()] = {
            "file": filename,
            "source": source,
            "column": col,
            "sample_value": str(non_null.iloc[0]),
        }
    return prov


_SECTION_FIELDS: Dict[str, List[str]] = {
    "Income Statement": [
        "revenue",
        "gross_profit",
        "operating_expenses",
        "ebit",
        "ebitda_margin",
        "interest_expense",
    ],
    "Balance Sheet": [
        "total_assets",
        "current_assets",
        "total_liabilities",
        "current_liabilities",
        "equity",
        "total_debt",
    ],
    "Cash Flow": ["operating_cash_flow", "investing_cash_flow", "financing_cash_flow"],
    "Adjustments / Pipeline": [
        "entity",
        "period",
        "industry",
        "ebitda",
        "detect_patterns",
        "ev",
        "output_dir",
    ],
}

REQUIRED_FIELDS = {"entity", "period"}


def build_session_from_uploads(
    uploaded_files: List[Tuple[str, str]],
    existing_session: Optional[SessionState] = None,
) -> SessionState:
    """Ingest multiple files, merge results, and build session state."""

    session = existing_session or SessionState()

    for filename, file_path in uploaded_files:
        result = ingest_file(filename, file_path)
        session.ingested_files.append(result)

        audit_event(
            session,
            entry_type="ingestion",
            actor="system",
            detail=(
                f"Ingested '{filename}': type={result.statement_type}, "
                f"confidence={result.confidence:.0%}, status={result.status}"
                + (f", error={result.error}" if result.error else "")
            ),
        )

        if result.status == "error" or result.dataframe is None:
            continue

        for field_key, prov_info in result.provenance.items():
            if field_key not in session.field_provenance:
                session.field_provenance[field_key] = prov_info

        _merge_fields_from_result(session, result)

    for key, default in [
        ("industry", settings.default_industry or ""),
        ("ebitda", settings.pipeline_ebitda),
        ("detect_patterns", settings.pipeline_detect_patterns),
        ("ev", ""),
        ("output_dir", settings.output_dir),
    ]:
        if key not in session.fields:
            session.fields[key] = default

    _write_prepared_csv(session)
    return session


def _merge_fields_from_result(session: SessionState, result: IngestedFile) -> None:
    """Merge known fields from one ingest result into the session."""

    df = result.dataframe
    if df is None or df.empty:
        return

    for col_key, field_key in [("Entity", "entity"), ("Period", "period")]:
        if col_key in df.columns:
            vals = df[col_key].dropna()
            if not vals.empty:
                val = str(vals.iloc[0])
                if field_key not in session.auto_filled_fields:
                    session.fields[field_key] = val
                    session.auto_filled_fields.append(field_key)

    if result.statement_type != "unknown" and "statement_type" not in session.auto_filled_fields:
        session.fields["statement_type"] = result.statement_type
        session.auto_filled_fields.append("statement_type")


def _write_prepared_csv(session: SessionState) -> None:
    """Write combined ingested dataframes to a temporary CSV for pipeline input."""

    frames = [r.dataframe for r in session.ingested_files if r.dataframe is not None and not r.dataframe.empty]
    if not frames:
        return
    combined = pd.concat(frames, ignore_index=True)
    tmp = tempfile.NamedTemporaryFile(prefix="normalized_input_", suffix=".csv", delete=False)
    combined.to_csv(tmp.name, index=False)
    tmp.close()
    session.prepared_input_path = tmp.name


def build_session_from_upload(file_path: str) -> SessionState:
    """Legacy single-file helper."""

    filename = Path(file_path).name
    return build_session_from_uploads([(filename, file_path)])


_validation_engine = ValidationEngine()


def validate_fields(fields: Dict[str, Any], industry: Optional[str] = None) -> List[ValidationResult]:
    """Run validation rules against current fields."""

    return _validation_engine.validate(fields, industry)


def has_blocking_errors(fields: Dict[str, Any], industry: Optional[str] = None) -> bool:
    """Return True when validation returns at least one ERROR severity issue."""

    return _validation_engine.has_blocking_errors(fields, industry)


_anomaly_detector = AnomalyDetector()


def detect_anomalies(fields: Dict[str, Any], industry: Optional[str] = None) -> List[AnomalyEntry]:
    """Run direct anomaly detection on user-provided fields."""

    return _anomaly_detector.detect(fields, industry)


def detect_anomalies_from_pipeline(
    pipeline_result: Dict[str, Any],
    industry: Optional[str] = None,
) -> List[AnomalyEntry]:
    """Run anomaly detection from a completed pipeline result payload."""

    return _anomaly_detector.detect_from_pipeline_result(pipeline_result, industry)


def update_field(session: SessionState, field_name: str, new_value: Any) -> None:
    """Update one session field and append an audit event with before/after diff."""

    old_value = session.fields.get(field_name)
    session.fields[field_name] = new_value
    if field_name in session.auto_filled_fields:
        session.auto_filled_fields.remove(field_name)
    audit_event(
        session,
        entry_type="field_edit",
        actor="user",
        detail=f"Field '{field_name}' changed by user.",
        diff={"field": field_name, "before": old_value, "after": new_value},
    )


def run_pipeline_from_session(session: SessionState) -> Dict[str, Any]:
    """Execute normalization pipeline from session state and record audit events."""

    ev_value = session.fields.get("ev")
    ev_float = None
    try:
        ev_float = float(str(ev_value).strip()) if str(ev_value).strip() else None
    except (ValueError, TypeError):
        ev_float = None

    start = datetime.now(timezone.utc)
    result = run_pipeline(
        input_path=session.prepared_input_path,
        output_path=session.fields.get("output_dir", settings.output_dir),
        industry=session.fields.get("industry") or settings.default_industry,
        ebitda=bool(session.fields.get("ebitda", settings.pipeline_ebitda)),
        detect_patterns=bool(session.fields.get("detect_patterns", settings.pipeline_detect_patterns)),
        ev=ev_float,
    )
    duration_s = (datetime.now(timezone.utc) - start).total_seconds()
    session.pipeline_result = result

    industry = session.fields.get("industry") or settings.default_industry
    anomalies = detect_anomalies_from_pipeline(result, industry)
    session.anomalies = [
        {
            "field": a.field,
            "value": a.value,
            "expected_range": list(a.expected_range),
            "unit": a.unit,
            "industry": a.industry,
            "message": a.message,
        }
        for a in anomalies
    ]

    for anomaly in anomalies:
        audit_event(
            session,
            entry_type="anomaly_detected",
            actor="system",
            detail=anomaly.message,
        )

    audit_event(
        session,
        entry_type="pipeline_run",
        actor="user",
        detail=(
            f"Pipeline executed in {duration_s:.1f}s. "
            f"Success={result.get('success')}. "
            f"Outputs: {list(result.get('files', {}).keys())}. "
            f"Anomalies detected: {len(anomalies)}."
        ),
    )
    return result


def save_session_file(session: SessionState, file_path: str) -> None:
    """Persist SessionState to disk as JSON."""

    payload = {
        "ingested_files": [
            {
                "filename": f.filename,
                "status": f.status,
                "statement_type": f.statement_type,
                "confidence": f.confidence,
                "warnings": f.warnings,
                "error": f.error,
                "provenance": f.provenance,
                "metadata": f.metadata,
            }
            for f in session.ingested_files
        ],
        "prepared_input_path": session.prepared_input_path,
        "fields": session.fields,
        "auto_filled_fields": session.auto_filled_fields,
        "field_provenance": session.field_provenance,
        "warnings": session.warnings,
        "audit_trail": session.audit_trail,
        "anomalies": session.anomalies,
    }
    Path(file_path).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def load_session_file(file_path: str) -> SessionState:
    """Load SessionState JSON export from disk."""

    payload = json.loads(Path(file_path).read_text(encoding="utf-8"))
    session = SessionState(
        prepared_input_path=payload.get("prepared_input_path", ""),
        fields=payload.get("fields", {}),
        auto_filled_fields=payload.get("auto_filled_fields", []),
        field_provenance=payload.get("field_provenance", {}),
        warnings=payload.get("warnings", []),
        audit_trail=payload.get("audit_trail", []),
        anomalies=payload.get("anomalies", []),
    )
    for f_data in payload.get("ingested_files", []):
        session.ingested_files.append(
            IngestedFile(
                filename=f_data.get("filename", ""),
                status=f_data.get("status", "unknown"),
                statement_type=f_data.get("statement_type", "unknown"),
                confidence=float(f_data.get("confidence", 0.0)),
                warnings=f_data.get("warnings", []),
                error=f_data.get("error"),
                dataframe=None,
                metadata=f_data.get("metadata", {}),
                provenance=f_data.get("provenance", {}),
            )
        )
    return session


def get_section_fields() -> Dict[str, List[str]]:
    """Return grouped editable fields for the UI."""

    return _SECTION_FIELDS


def get_required_fields() -> set:
    """Return required UI fields that gate pipeline execution."""

    return REQUIRED_FIELDS
