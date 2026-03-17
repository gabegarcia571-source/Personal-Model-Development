"""
XBRL Ingestion Module

Parses XBRL instance documents (SEC 10-K / 10-Q) by directly reading
the XML structure. Uses defusedxml for secure parsing (mitigates XXE/
entity-expansion attacks) with lxml as the underlying parser for rich
XPath and namespace support.

Library decision: Neither python-xbrl (inconsistent API across versions,
limited us-gaap taxonomy coverage, low maintenance) nor arelle
(enterprise-scale tool, complex non-trivial installation in container
environments, requires network taxonomy resolution) is appropriate here.
Direct lxml + defusedxml parsing provides full control, is secure, and
avoids dependency on third-party XBRL libraries that may become stale.
Known limitation: taxonomy validation is not performed; the parser
trusts that facts use standard us-gaap or ifrs-full namespaces.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import defusedxml.ElementTree as _safe_et

try:
    from ingestion.contract import IngestionContractError, ensure_ingestion_contract
except ModuleNotFoundError:
    from src.ingestion.contract import IngestionContractError, ensure_ingestion_contract


# ---------------------------------------------------------------------------
# us-gaap fact → internal field name mappings
# ---------------------------------------------------------------------------

# Map commonly used us-gaap / ifrs element local-names to internal schema fields.
# Priority order: first match wins.
US_GAAP_FACT_MAP: Dict[str, str] = {
    # Income Statement
    "Revenues": "Revenue",
    "RevenueFromContractWithCustomerExcludingAssessedTax": "Revenue",
    "SalesRevenueNet": "Revenue",
    "GrossProfit": "GrossProfit",
    "CostOfGoodsSold": "COGS",
    "CostOfRevenue": "COGS",
    "OperatingExpenses": "OperatingExpenses",
    "OperatingIncomeLoss": "OperatingIncome",
    "NetIncomeLoss": "NetIncome",
    "EarningsPerShareBasic": "EPSBasic",
    "EarningsPerShareDiluted": "EPSDiluted",
    # EBITDA proxies
    "DepreciationDepletionAndAmortization": "DepreciationAndAmortization",
    "AmortizationOfIntangibleAssets": "Amortization",
    "InterestExpense": "InterestExpense",
    "IncomeTaxExpenseBenefit": "IncomeTaxExpense",
    # Balance Sheet
    "Assets": "TotalAssets",
    "AssetsCurrent": "CurrentAssets",
    "AssetsNoncurrent": "NonCurrentAssets",
    "CashAndCashEquivalentsAtCarryingValue": "Cash",
    "Liabilities": "TotalLiabilities",
    "LiabilitiesCurrent": "CurrentLiabilities",
    "LongTermDebt": "LongTermDebt",
    "StockholdersEquity": "Equity",
    "RetainedEarningsAccumulatedDeficit": "RetainedEarnings",
    # Cash Flow
    "NetCashProvidedByUsedInOperatingActivities": "OperatingCashFlow",
    "NetCashProvidedByUsedInInvestingActivities": "InvestingCashFlow",
    "NetCashProvidedByUsedInFinancingActivities": "FinancingCashFlow",
    "CapitalExpendituresIncurringObligation": "Capex",
    "PaymentsToAcquirePropertyPlantAndEquipment": "Capex",
}

# Namespace prefixes used in us-gaap XBRL instance documents
KNOWN_NAMESPACES = {
    "xbrli": "http://www.xbrl.org/2003/instance",
    "us-gaap": "http://fasb.org/us-gaap/",
    "ifrs-full": "http://xbrl.ifrs.org/taxonomy/",
    "dei": "http://xbrl.sec.gov/dei/",
}

# Pattern to strip namespace URIs like {http://fasb.org/us-gaap/2023-01-31}
_NS_STRIP_RE = re.compile(r"\{[^}]+\}")


def _local_name(tag: str) -> str:
    return _NS_STRIP_RE.sub("", tag)


def _ns_uri(tag: str) -> str:
    m = re.match(r"\{([^}]+)\}", tag)
    return m.group(1) if m else ""


def _is_us_gaap_or_ifrs(ns_uri: str) -> bool:
    return "fasb.org/us-gaap" in ns_uri or "xbrl.ifrs.org" in ns_uri


def _parse_decimals(decimals_str: Optional[str]) -> Optional[int]:
    if decimals_str is None:
        return None
    if decimals_str.strip().upper() == "INF":
        return None
    try:
        return int(decimals_str)
    except ValueError:
        return None


def _scale_value(raw: float, decimals: Optional[int]) -> float:
    """XBRL stores values in document units; decimals attr indicates precision."""
    if decimals is None or decimals >= 0:
        return raw
    # Negative decimals mean the value is expressed in thousands/millions
    return raw  # We keep raw; consumer can interpret decimals field


class XBRLContext:
    __slots__ = ("context_id", "entity_identifier", "period_start", "period_end", "instant")

    def __init__(
        self,
        context_id: str,
        entity_identifier: str,
        period_start: Optional[str],
        period_end: Optional[str],
        instant: Optional[str],
    ) -> None:
        self.context_id = context_id
        self.entity_identifier = entity_identifier
        self.period_start = period_start
        self.period_end = period_end
        self.instant = instant


def _parse_contexts(root: Any) -> Dict[str, XBRLContext]:
    """Extract all <context> elements from the document."""
    contexts: Dict[str, XBRLContext] = {}
    for elem in root.iter():
        if _local_name(elem.tag) != "context":
            continue
        ctx_id = elem.get("id", "")
        entity_id = ""
        period_start = period_end = instant = None

        for child in elem:
            local = _local_name(child.tag)
            if local == "entity":
                for sub in child:
                    if _local_name(sub.tag) == "identifier":
                        entity_id = (sub.text or "").strip()
            elif local == "period":
                for sub in child:
                    sub_local = _local_name(sub.tag)
                    if sub_local == "startDate":
                        period_start = (sub.text or "").strip()
                    elif sub_local == "endDate":
                        period_end = (sub.text or "").strip()
                    elif sub_local == "instant":
                        instant = (sub.text or "").strip()

        contexts[ctx_id] = XBRLContext(ctx_id, entity_id, period_start, period_end, instant)
    return contexts


def _parse_dei_facts(root: Any) -> Dict[str, str]:
    """Extract DEI (document/entity information) facts."""
    dei: Dict[str, str] = {}
    for elem in root.iter():
        ns = _ns_uri(elem.tag)
        if "xbrl.sec.gov/dei" not in ns:
            continue
        local = _local_name(elem.tag)
        text = (elem.text or "").strip()
        if text:
            dei[local] = text
    return dei


def _parse_financial_facts(
    root: Any,
    contexts: Dict[str, XBRLContext],
) -> List[Dict[str, Any]]:
    """Extract standard financial facts and map to internal schema."""
    rows: List[Dict[str, Any]] = []
    warnings_flags: List[str] = []

    for elem in root.iter():
        ns = _ns_uri(elem.tag)
        if not _is_us_gaap_or_ifrs(ns):
            continue

        local = _local_name(elem.tag)
        mapped_name = US_GAAP_FACT_MAP.get(local)
        if mapped_name is None:
            continue  # Skip unmapped facts; only extract known schema fields

        raw_text = (elem.text or "").strip()
        if not raw_text:
            warnings_flags.append(f"Fact {local} has empty/null value — skipped.")
            continue

        try:
            raw_value = float(raw_text)
        except ValueError:
            continue  # Non-numeric fact (e.g. string labels)

        ctx_ref = elem.get("contextRef", "")
        context = contexts.get(ctx_ref)
        decimals = _parse_decimals(elem.get("decimals"))

        entity_id = context.entity_identifier if context else ""
        period = (
            context.instant
            or context.period_end
            or context.period_start
            or ""
        ) if context else ""

        # Skip if value is zero — flag it
        if raw_value == 0.0:
            warnings_flags.append(f"Fact {local} has zero value for context '{ctx_ref}'.")

        rows.append({
            "account_code": f"XBRL_{local}",
            "account_name": mapped_name,
            "amount": raw_value,
            "entity": entity_id,
            "period": period,
            "decimals": decimals,
            "xbrl_element": local,
            "context_ref": ctx_ref,
        })

    return rows, warnings_flags  # type: ignore[return-value]


def _classify_xbrl(facts: List[Dict[str, Any]]) -> str:
    """Classify document type based on which facts are present."""
    names = {row["account_name"] for row in facts}
    if {"OperatingCashFlow", "InvestingCashFlow", "FinancingCashFlow"} & names:
        return "cash_flow"
    if {"TotalAssets", "TotalLiabilities", "Equity"} & names:
        return "balance_sheet"
    if {"Revenue", "GrossProfit", "NetIncome"} & names:
        return "income_statement"
    return "unknown"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class XBRLIngestionEngine:
    """Parse XBRL instance documents and return ingestion contract output."""

    def ingest(self, file_path: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        path = Path(file_path)
        if not path.exists():
            raise IngestionContractError(f"XBRL file not found: {file_path}")

        suffix = path.suffix.lower()
        if suffix not in {".xml", ".xbrl"}:
            raise IngestionContractError(
                f"Unsupported XBRL file extension: {suffix}. Expected .xml or .xbrl"
            )

        warnings: List[str] = []

        try:
            # defusedxml.ElementTree is a secure drop-in replacement for stdlib
            # ElementTree; it forbids entity expansion (XXE), billion-laughs, etc.
            tree = _safe_et.parse(str(path))
            root = tree.getroot()
        except (_safe_et.ParseError, OSError, ValueError) as exc:
            raise IngestionContractError(f"Failed to parse XBRL XML: {exc}") from exc

        contexts = _parse_contexts(root)
        dei = _parse_dei_facts(root)
        facts, fact_warnings = _parse_financial_facts(root, contexts)
        warnings.extend(fact_warnings)

        entity_name = (
            dei.get("EntityRegistrantName")
            or dei.get("EntityCommonStockSharesOutstanding", "")
            or (next(iter(contexts.values())).entity_identifier if contexts else "Unknown")
        )
        fiscal_period = (
            dei.get("DocumentPeriodEndDate")
            or dei.get("CurrentFiscalYearEndDate")
            or ""
        )
        fiscal_year_end = dei.get("CurrentFiscalYearEndDate", "")
        doc_type = dei.get("DocumentType", "unknown")

        if not facts:
            warnings.append(
                "No us-gaap taxonomy facts found. File may use a non-standard namespace."
            )
            df = pd.DataFrame(columns=["Account_Code", "Account_Name", "Amount", "Entity", "Period", "Date"])
            metadata: Dict[str, Any] = {
                "source": str(path),
                "statement_type": "unknown",
                "confidence_level": 0.0,
                "warnings": warnings,
                "entity_name": entity_name,
                "fiscal_period": fiscal_period,
                "fiscal_year_end": fiscal_year_end,
                "document_type": doc_type,
            }
            return ensure_ingestion_contract(df, metadata)

        # Check for unexpected taxonomy namespaces
        for elem in root.iter():
            ns = _ns_uri(elem.tag)
            if ns and not any(
                ns_fragment in ns
                for ns_fragment in ("fasb.org", "xbrl.org", "xbrl.sec.gov", "xbrl.ifrs.org")
            ):
                warnings.append(
                    f"Unexpected taxonomy namespace detected: {ns!r}. "
                    "Facts from this namespace were not extracted."
                )
                break

        statement_type = _classify_xbrl(facts)
        confidence = 0.9 if statement_type != "unknown" else 0.5

        df = pd.DataFrame(facts)
        df = df.rename(columns={
            "account_code": "Account_Code",
            "account_name": "Account_Name",
            "amount": "Amount",
            "entity": "Entity",
            "period": "Period",
        })
        df["Date"] = df.get("Period", "")
        df = df[["Account_Code", "Account_Name", "Amount", "Entity", "Period", "Date"]].copy()

        metadata = {
            "source": str(path),
            "statement_type": statement_type,
            "confidence_level": confidence,
            "warnings": warnings,
            "entity_name": entity_name,
            "fiscal_period": fiscal_period,
            "fiscal_year_end": fiscal_year_end,
            "document_type": doc_type,
        }
        return ensure_ingestion_contract(df, metadata)


def parse_xbrl_contract(file_path: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Convenience wrapper: parse XBRL and enforce contract."""
    engine = XBRLIngestionEngine()
    return engine.ingest(file_path)
