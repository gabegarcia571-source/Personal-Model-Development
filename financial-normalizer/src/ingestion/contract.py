from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Tuple

import pandas as pd


REQUIRED_METADATA_KEYS = {"source", "statement_type", "confidence_level", "warnings"}


class IngestionContractError(ValueError):
    """Raised when parser output does not match ingestion contract."""


@dataclass
class IngestionMetadata:
    source: str
    statement_type: str
    confidence_level: float
    warnings: List[str]

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def ensure_ingestion_contract(dataframe: pd.DataFrame, metadata: Dict[str, Any]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Validate the shared ingestion contract and return normalized values."""
    if not isinstance(dataframe, pd.DataFrame):
        raise IngestionContractError("Ingestion contract violation: dataframe must be a pandas DataFrame")

    if not isinstance(metadata, dict):
        raise IngestionContractError("Ingestion contract violation: metadata must be a dict")

    missing_keys = REQUIRED_METADATA_KEYS.difference(metadata.keys())
    if missing_keys:
        raise IngestionContractError(
            f"Ingestion contract violation: metadata missing keys {sorted(missing_keys)}"
        )

    confidence = metadata.get("confidence_level")
    if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
        raise IngestionContractError(
            "Ingestion contract violation: confidence_level must be numeric and between 0 and 1"
        )

    warnings = metadata.get("warnings")
    if not isinstance(warnings, list):
        raise IngestionContractError("Ingestion contract violation: warnings must be a list")

    return dataframe, metadata
