from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import pandas as pd
import pdfplumber

try:
    from ingestion.contract import IngestionContractError, ensure_ingestion_contract
    from ingestion.parsers import (
        parse_balance_sheet,
        parse_cash_flow,
        parse_income_statement,
        parse_manual_input,
        parse_pl_statement,
    )
    from ingestion.xbrl_ingestion import XBRLIngestionEngine
except ModuleNotFoundError:
    from src.ingestion.contract import IngestionContractError, ensure_ingestion_contract
    from src.ingestion.parsers import (
        parse_balance_sheet,
        parse_cash_flow,
        parse_income_statement,
        parse_manual_input,
        parse_pl_statement,
    )
    from src.ingestion.xbrl_ingestion import XBRLIngestionEngine


class AdvancedIngestionEngine:
    """Flexible ingestion for PDF and spreadsheet-like sources."""

    STATEMENT_HINTS = {
        "income_statement": ["income statement", "revenue", "gross profit", "operating income"],
        "balance_sheet": ["balance sheet", "assets", "liabilities", "equity"],
        "cash_flow": ["cash flow", "operating activities", "investing activities", "financing activities"],
        "pl_statement": ["profit and loss", "p&l", "expenses", "sales"],
    }

    COLUMN_CANDIDATES = {
        "account_code": ["account_code", "code", "gl_code", "account #", "account number"],
        "account_name": ["account_name", "account", "description", "line_item", "line item"],
        "amount": ["amount", "balance", "value", "actual", "debit", "credit", "cash_flow"],
        "entity": ["entity", "company", "legal_entity"],
        "period": ["period", "year", "month"],
        "date": ["date", "posting_date", "period_date"],
    }

    def ingest_file(self, file_path: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix in {".xml", ".xbrl"}:
            return XBRLIngestionEngine().ingest(file_path)

        if suffix == ".pdf":
            return self.ingest_pdf(path)

        if suffix in {".csv", ".xlsx", ".xls"}:
            return self.ingest_table_file(path)

        raise IngestionContractError(f"Unsupported input format: {suffix}")

    def ingest_pdf(self, path: Path) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        extracted_tables: List[pd.DataFrame] = []
        warnings: List[str] = []
        confidence = 1.0  # starts high; degrades on edge cases

        with pdfplumber.open(path) as pdf:
            for page_idx, page in enumerate(pdf.pages, start=1):
                # Skip header-only pages (no table data)
                page_tables = page.extract_tables() or []
                if not page_tables:
                    text = (page.extract_text() or "").strip()
                    if text and len(text.split()) < 20:
                        warnings.append(
                            f"Page {page_idx} appears to contain only a title or section header — skipped."
                        )
                        confidence = min(confidence, 0.7)
                    continue

                for table in page_tables:
                    frame, table_warnings = self._table_to_dataframe_smart(table, page_idx)
                    warnings.extend(table_warnings)
                    if table_warnings:
                        confidence = min(confidence, 0.6)
                    if frame.empty:
                        continue
                    frame["_source_page"] = page_idx
                    extracted_tables.append(frame)

        if not extracted_tables:
            metadata = {
                "source": str(path),
                "statement_type": "unknown",
                "confidence_level": 0.0,
                "warnings": [
                    "No extractable PDF tables were found. Manual review required before normalization."
                ],
            }
            return ensure_ingestion_contract(pd.DataFrame(), metadata)

        combined = self._merge_multi_page_tables_safe(extracted_tables, warnings)
        statement_type, classified_confidence = self._classify_statement(combined)
        confidence = min(confidence, classified_confidence if classified_confidence > 0 else confidence)

        if statement_type == "unknown":
            warnings.append(
                "Unable to confidently classify extracted PDF table. Manual review is required."
            )
            confidence = min(confidence, 0.5)

        normalized = self._normalize_dataframe_columns(combined)
        if normalized.empty:
            warnings.append(
                "Extracted PDF table could not be mapped to internal schema. Manual review required."
            )

        metadata = {
            "source": str(path),
            "statement_type": statement_type,
            "confidence_level": round(confidence, 2),
            "warnings": warnings,
        }
        return ensure_ingestion_contract(normalized, metadata)

    def ingest_table_file(self, path: Path) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        warnings: List[str] = []
        mapped_frames: List[pd.DataFrame] = []
        source_label = str(path)

        if path.suffix.lower() == ".csv":
            raw_df = pd.read_csv(path, header=None)
            frame, frame_warnings = self._parse_tabular_source(raw_df, "csv")
            warnings.extend(frame_warnings)
            if not frame.empty:
                mapped_frames.append(frame)
        else:
            workbook = pd.read_excel(path, sheet_name=None, header=None)
            for sheet_name, raw_df in workbook.items():
                frame, frame_warnings = self._parse_tabular_source(raw_df, sheet_name)
                warnings.extend(frame_warnings)
                if not frame.empty:
                    mapped_frames.append(frame)
                else:
                    warnings.append(
                        f"Sheet '{sheet_name}' could not be mapped to schema and was flagged for manual review."
                    )

        if not mapped_frames:
            raise IngestionContractError(
                f"No sheets or ranges in {source_label} could be mapped to the ingestion schema."
            )

        normalized = pd.concat(mapped_frames, ignore_index=True)
        statement_type, confidence = self._classify_statement(normalized)

        metadata = {
            "source": source_label,
            "statement_type": statement_type,
            "confidence_level": confidence,
            "warnings": warnings,
        }
        return ensure_ingestion_contract(normalized, metadata)

    def _parse_tabular_source(self, raw_df: pd.DataFrame, label: str) -> Tuple[pd.DataFrame, List[str]]:
        warnings: List[str] = []
        header_idx = self._detect_header_row(raw_df)
        if header_idx is None:
            return pd.DataFrame(), [f"Could not detect header row in source '{label}'."]

        trimmed = raw_df.iloc[header_idx:].copy()
        trimmed.columns = [str(value).strip().lower() for value in trimmed.iloc[0].tolist()]
        trimmed = trimmed.iloc[1:].reset_index(drop=True)

        trimmed = trimmed.dropna(how="all")
        trimmed = trimmed.loc[:, trimmed.columns.notna()]

        normalized = self._normalize_dataframe_columns(trimmed)
        if normalized.empty:
            warnings.append(
                f"Header row detected in source '{label}', but normalized mapping failed."
            )
        return normalized, warnings

    def _detect_header_row(self, raw_df: pd.DataFrame) -> int | None:
        search_rows = min(len(raw_df), 12)
        for idx in range(search_rows):
            values = [str(v).strip().lower() for v in raw_df.iloc[idx].tolist() if pd.notna(v)]
            if not values:
                continue
            score = 0
            joined = " ".join(values)
            for candidates in self.COLUMN_CANDIDATES.values():
                if any(candidate in joined for candidate in candidates):
                    score += 1
            if score >= 2:
                return idx
        return None

    def _normalize_dataframe_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()

        frame = df.copy()
        frame.columns = [str(c).strip().lower() for c in frame.columns]

        col_map: Dict[str, str] = {}
        for target_col, aliases in self.COLUMN_CANDIDATES.items():
            for source_col in frame.columns:
                if any(alias in source_col for alias in aliases):
                    col_map[source_col] = target_col
                    break

        frame = frame.rename(columns=col_map)

        if "account_name" not in frame.columns or "amount" not in frame.columns:
            return pd.DataFrame()

        if "account_code" not in frame.columns:
            frame["account_code"] = [f"AUTO_{idx:04d}" for idx in range(len(frame))]

        frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce")
        frame = frame[frame["amount"].notna()].copy()

        if "entity" not in frame.columns:
            frame["entity"] = "Unknown"
        if "period" not in frame.columns:
            frame["period"] = "Unknown"
        if "date" not in frame.columns:
            frame["date"] = "Unknown"

        normalized = frame[["account_code", "account_name", "amount", "entity", "period", "date"]].copy()
        normalized.columns = [
            "Account_Code",
            "Account_Name",
            "Amount",
            "Entity",
            "Period",
            "Date",
        ]
        return normalized

    def _table_to_dataframe_smart(
        self,
        table: List[List[Any]],
        page_idx: int = 0,
    ) -> Tuple["pd.DataFrame", List[str]]:
        """Convert a pdfplumber table to DataFrame with multi-column + nested-header handling."""
        warnings_out: List[str] = []
        if not table:
            return pd.DataFrame(), warnings_out

        def _is_numeric_cell(cell: Any) -> bool:
            if cell is None:
                return False
            try:
                float(str(cell).replace(",", "").replace("$", "").replace("(", "-").replace(")", ""))
                return True
            except ValueError:
                return False

        def _row_mostly_non_numeric(row: List[Any]) -> bool:
            non_empty = [c for c in row if c is not None and str(c).strip()]
            if not non_empty:
                return True
            numeric_count = sum(1 for c in non_empty if _is_numeric_cell(c))
            return numeric_count / len(non_empty) < 0.4

        # Detect nested header: first 2 rows both non-numeric and row 0 has None/merged cells
        has_nested = (
            len(table) >= 3
            and _row_mostly_non_numeric(table[0])
            and _row_mostly_non_numeric(table[1])
            and any(c is None for c in table[0])
        )

        if has_nested:
            warnings_out.append(
                f"Page {page_idx}: Nested/multi-row header detected — flattening to single header row."
            )
            flat_header: List[str] = []
            for i, (top, bot) in enumerate(zip(table[0], table[1])):
                top_s = str(top).strip() if top is not None else ""
                bot_s = str(bot).strip() if bot is not None else ""
                if top_s and bot_s:
                    flat_header.append(f"{top_s}_{bot_s}")
                elif top_s:
                    flat_header.append(top_s)
                elif bot_s:
                    flat_header.append(bot_s)
                else:
                    flat_header.append(f"col_{i}")
            header = flat_header
            body = table[2:]
        else:
            header = [
                str(c).strip().lower() if c is not None else f"col_{i}"
                for i, c in enumerate(table[0])
            ]
            body = table[1:]

        # Detect multi-column layout: rename duplicate columns
        seen: Dict[str, int] = {}
        clean_header: List[str] = []
        for col in header:
            col_l = str(col).strip().lower()
            if col_l in seen:
                seen[col_l] += 1
                new_name = f"{col_l}_{seen[col_l]}"
                clean_header.append(new_name)
                warnings_out.append(
                    f"Page {page_idx}: Duplicate column '{col_l}' detected (multi-column layout) "
                    f"— renamed to '{new_name}'."
                )
            else:
                seen[col_l] = 1
                clean_header.append(col_l)

        # Build DataFrame; pad or truncate data rows to match header length
        result_rows: List[Dict[str, Any]] = []
        for row in body:
            padded = list(row) + [None] * max(0, len(clean_header) - len(row))
            padded = padded[: len(clean_header)]
            result_rows.append(dict(zip(clean_header, padded)))

        return pd.DataFrame(result_rows), warnings_out

    def _table_to_dataframe(self, table: List[List[Any]]) -> "pd.DataFrame":
        """Legacy compat — delegates to smart variant, discards edge-case warnings."""
        df, _ = self._table_to_dataframe_smart(table)
        return df

    def _merge_multi_page_tables_safe(
        self,
        tables: List["pd.DataFrame"],
        warnings: List[str],
    ) -> "pd.DataFrame":
        """Merge tables across pages, handling column-count mismatches safely."""
        if not tables:
            return pd.DataFrame()

        merged = tables[0].copy()
        ref_cols = set(merged.columns)

        for i, frame in enumerate(tables[1:], start=2):
            if set(frame.columns) == ref_cols:
                merged = pd.concat([merged, frame], ignore_index=True)
            else:
                extra = set(frame.columns) - ref_cols
                missing = ref_cols - set(frame.columns)
                if extra or missing:
                    warnings.append(
                        f"Page {i} table continuation has different columns "
                        f"(+{sorted(extra)}, -{sorted(missing)}) — outer-joined safely."
                    )
                merged = pd.concat([merged, frame], ignore_index=True, sort=False)

        return merged

    def _merge_multi_page_tables(self, tables: List["pd.DataFrame"]) -> "pd.DataFrame":
        """Legacy compat — delegates to safe variant."""
        dummy_warnings: List[str] = []
        return self._merge_multi_page_tables_safe(tables, dummy_warnings)

    def _classify_statement(self, df: pd.DataFrame) -> Tuple[str, float]:
        if df.empty:
            return "unknown", 0.0

        haystack = " ".join(str(v).lower() for v in df.columns.tolist())
        if "account_name" in df.columns:
            haystack += " " + " ".join(df["account_name"].astype(str).head(100).str.lower().tolist())

        best_type = "unknown"
        best_score = 0
        for statement_type, hints in self.STATEMENT_HINTS.items():
            score = sum(1 for hint in hints if hint in haystack)
            if score > best_score:
                best_score = score
                best_type = statement_type

        confidence = min(1.0, best_score / 3.0)
        if best_score == 0:
            return "unknown", 0.2
        return best_type, confidence


def _wrap_contract_parser(
    parser_name: str,
    parser_func: Callable[..., pd.DataFrame],
    file_path: str,
    **kwargs: Any,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    df = parser_func(file_path, **kwargs)
    metadata = {
        "source": file_path,
        "statement_type": parser_name,
        "confidence_level": 1.0,
        "warnings": [],
    }
    return ensure_ingestion_contract(df, metadata)


def parse_income_statement_contract(file_path: str, **kwargs: Any) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    return _wrap_contract_parser("income_statement", parse_income_statement, file_path, **kwargs)


def parse_balance_sheet_contract(file_path: str, **kwargs: Any) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    return _wrap_contract_parser("balance_sheet", parse_balance_sheet, file_path, **kwargs)


def parse_cash_flow_contract(file_path: str, **kwargs: Any) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    return _wrap_contract_parser("cash_flow", parse_cash_flow, file_path, **kwargs)


def parse_pl_statement_contract(file_path: str, **kwargs: Any) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    return _wrap_contract_parser("pl_statement", parse_pl_statement, file_path, **kwargs)


def parse_manual_input_contract(file_path: str, **kwargs: Any) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    return _wrap_contract_parser("manual_input", parse_manual_input, file_path, **kwargs)
