"""
Financial Normalizer — Streamlit Application

This file is orchestration-only. No parsing, pipeline, or validation
logic lives here — everything is delegated to src/interface/app_service.py.
"""
from __future__ import annotations

import json
import logging
import sys
import tempfile
from pathlib import Path

import streamlit as st

# Ensure src/ is on path when running directly
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.interface.app_service import (
    IngestedFile,
    SessionState,
    allowed_upload_extensions,
    audit_event,
    build_session_from_uploads,
    detect_anomalies,
    get_required_fields,
    get_section_fields,
    has_blocking_errors,
    load_session_file,
    max_upload_size_mb,
    run_pipeline_from_session,
    save_session_file,
    update_field,
    validate_fields,
)
from src.validation import Severity
from src.reporting import generate_excel, generate_pdf
from src.comparison import FilingData, compare_filings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Financial Normalizer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Color system constants
# ---------------------------------------------------------------------------

COLOR_AUTO = "#d1fae5"       # green  – confirmed / auto-filled
COLOR_MANUAL = "#fef3c7"     # amber  – manual entry / warning
COLOR_MISSING = "#fee2e2"    # red    – required but empty / error
COLOR_ANOMALY = "#fed7aa"    # orange – anomaly detected
BORDER_AUTO = "#059669"
BORDER_MANUAL = "#d97706"
BORDER_MISSING = "#dc2626"
BORDER_ANOMALY = "#ea580c"


# ---------------------------------------------------------------------------
# Session state bootstrap
# ---------------------------------------------------------------------------

def _init_state() -> None:
    if "session" not in st.session_state:
        st.session_state.session = SessionState()
    if "nav" not in st.session_state:
        st.session_state.nav = "Upload"
    if "acknowledged_warnings" not in st.session_state:
        st.session_state.acknowledged_warnings = set()


_init_state()
session: SessionState = st.session_state.session

# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("📊 Financial Normalizer")
    st.markdown("---")
    successful_filings = [f for f in st.session_state.session.ingested_files if f.status in ("success", "warning")]
    num_filings = len(successful_filings)
    nav_options = ["Upload", "Review & Edit", "Validate", "Run", "Results"]
    if num_filings >= 1:
        nav_options.append("Compare")
    selected_nav = st.radio(
        "Navigation",
        nav_options,
        index=nav_options.index(st.session_state.nav),
        key="nav_radio",
    )
    st.session_state.nav = selected_nav

    # Audit trail in sidebar
    st.markdown("---")
    with st.expander("🗒 Audit Trail", expanded=False):
        if session.audit_trail:
            for entry in reversed(session.audit_trail[-50:]):
                ts = entry.get("timestamp", "")[:19].replace("T", " ")
                etype = entry.get("entry_type", "")
                detail = entry.get("detail", "")
                icon = {
                    "ingestion": "📥",
                    "field_edit": "✏️",
                    "validation_event": "✅",
                    "anomaly_detected": "🟠",
                    "pipeline_run": "🚀",
                    "session_load": "📂",
                    "session_save": "💾",
                }.get(etype, "•")
                st.markdown(
                    f"<small><b>{ts}</b> {icon} <i>{etype}</i><br>{detail}</small><hr style='margin:4px 0'>",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No audit entries yet.")

# ---------------------------------------------------------------------------
# Helper: styled badge
# ---------------------------------------------------------------------------

def _badge(label: str, bg: str, border: str) -> str:
    return (
        f"<span style='background:{bg};border:1px solid {border};color:#111;"
        f"padding:1px 8px;border-radius:10px;font-size:11px;font-weight:600'>{label}</span>"
    )


def _confidence_label(confidence: float) -> tuple[str, str]:
    if confidence >= 0.8:
        return "High", COLOR_AUTO
    if confidence >= 0.5:
        return "Medium", COLOR_MANUAL
    return "Low", COLOR_MISSING


# ==========================================================================
# Section: Upload
# ==========================================================================

if st.session_state.nav == "Upload":
    st.header("📂 Upload Financial Files")

    if not session.ingested_files:
        st.info(
            "Upload one or more financial files to begin. "
            "Supported: PDF, Excel (.xlsx/.xls), CSV, and XBRL (.xml)."
        )

    upload_col, session_col = st.columns([2, 1])

    with upload_col:
        upload_exts = allowed_upload_extensions()
        max_size_bytes = max_upload_size_mb() * 1024 * 1024
        uploaded = st.file_uploader(
            "Upload files (PDF, Excel, CSV, XBRL)",
            type=upload_exts,
            accept_multiple_files=True,
            help=f"Max file size: {max_upload_size_mb()} MB per file",
        )

        if uploaded and st.button("Parse Uploaded Files", type="primary"):
            file_pairs = []
            for uf in uploaded:
                if uf.size > max_size_bytes:
                    st.error(
                        f"{uf.name} exceeds the max file size ({max_upload_size_mb()} MB)."
                    )
                    continue
                suffix = Path(uf.name).suffix
                tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
                tmp.write(uf.read())
                tmp.close()
                file_pairs.append((uf.name, tmp.name))

            if not file_pairs:
                st.warning("No valid files to parse after validation checks.")
                st.stop()

            with st.spinner("Parsing files…"):
                st.session_state.session = build_session_from_uploads(
                    file_pairs, existing_session=st.session_state.session
                )
                session = st.session_state.session

            st.success(f"Processed {len(file_pairs)} file(s).")

    with session_col:
        st.markdown("##### Load saved session")
        session_upload = st.file_uploader("Load session JSON", type=["json"], key="session_json")
        if session_upload and st.button("Load Session"):
            tmp_s = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
            tmp_s.write(session_upload.read())
            tmp_s.close()
            try:
                loaded = load_session_file(tmp_s.name)
                audit_event(loaded, "session_load", "user", "Session loaded from JSON file.")
                st.session_state.session = loaded
                session = loaded
                st.success("Session loaded.")
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Failed to load session file: %s", exc)
                st.error("Failed to load session file. Ensure it is a valid Financial Normalizer JSON export.")

    # Per-file status table
    if session.ingested_files:
        st.markdown("### Ingestion Status")
        for ifile in session.ingested_files:
            status_icon = {"success": "✅", "warning": "⚠️", "error": "❌"}.get(ifile.status, "❓")
            conf_label, conf_color = _confidence_label(ifile.confidence)

            with st.container():
                col_icon, col_name, col_type, col_conf, col_detail = st.columns([1, 3, 2, 2, 4])
                col_icon.markdown(status_icon)
                col_name.markdown(f"**{ifile.filename}**")
                col_type.markdown(ifile.statement_type.replace("_", " ").title())
                col_conf.markdown(
                    _badge(conf_label, conf_color, BORDER_AUTO if conf_label == "High" else BORDER_MANUAL),
                    unsafe_allow_html=True,
                )
                if ifile.status == "error":
                    col_detail.error(ifile.error or "Unknown error")
                elif ifile.warnings:
                    with col_detail.expander(f"{len(ifile.warnings)} warning(s)"):
                        for w in ifile.warnings:
                            st.warning(w)
                else:
                    col_detail.caption("Parsed successfully")


# ==========================================================================
# Section: Review & Edit
# ==========================================================================

elif st.session_state.nav == "Review & Edit":
    st.header("✏️ Review & Edit Fields")

    if not session.ingested_files and not session.fields:
        st.info("Upload files first to populate fields.")
        st.stop()

    required_fields = get_required_fields()
    section_fields = get_section_fields()
    industry = session.fields.get("industry") or None

    # Run anomaly detection on current field values
    current_anomaly_fields = {a["field"] for a in session.anomalies}

    for section_name, field_keys in section_fields.items():
        st.markdown(f"### {section_name}")

        for fkey in field_keys:
            current_val = session.fields.get(fkey, "")
            is_auto = fkey in session.auto_filled_fields
            is_required = fkey in required_fields
            is_missing = is_required and (current_val == "" or current_val is None)
            has_anomaly = fkey in current_anomaly_fields

            # Industry field: render as a labeled selectbox
            if fkey == "industry":
                _INDUSTRY_OPTIONS = [
                    "",
                    "saas_tech", "traditional_software", "ecommerce_retail",
                    "healthcare_medtech", "financial_services", "manufacturing",
                    "energy_utilities", "real_estate", "media_entertainment",
                    "professional_services", "consumer_goods_cpg",
                    "industrials_infrastructure",
                ]
                _INDUSTRY_LABELS = {
                    "": "— Select industry —",
                    "saas_tech": "SaaS / Technology",
                    "traditional_software": "Traditional Software",
                    "ecommerce_retail": "E-Commerce / Retail",
                    "healthcare_medtech": "Healthcare / MedTech",
                    "financial_services": "Financial Services / Fintech",
                    "manufacturing": "Manufacturing",
                    "energy_utilities": "Energy / Utilities",
                    "real_estate": "Real Estate",
                    "media_entertainment": "Media / Entertainment",
                    "professional_services": "Professional Services / Consulting",
                    "consumer_goods_cpg": "Consumer Goods / CPG",
                    "industrials_infrastructure": "Industrials / Infrastructure",
                }
                cur_idx = _INDUSTRY_OPTIONS.index(current_val) if current_val in _INDUSTRY_OPTIONS else 0
                sel = st.selectbox(
                    "Industry",
                    options=_INDUSTRY_OPTIONS,
                    index=cur_idx,
                    format_func=lambda k: _INDUSTRY_LABELS.get(k, k),
                    key=f"field__{fkey}",
                )
                if sel != session.fields.get(fkey):
                    update_field(session, fkey, sel)
                continue

            # Determine badge
            if is_missing:
                badge_html = _badge("MISSING", COLOR_MISSING, BORDER_MISSING)
                bg = COLOR_MISSING
                border = BORDER_MISSING
            elif has_anomaly:
                badge_html = _badge("ANOMALY", COLOR_ANOMALY, BORDER_ANOMALY)
                bg = COLOR_ANOMALY
                border = BORDER_ANOMALY
            elif is_auto:
                badge_html = _badge("AUTO", COLOR_AUTO, BORDER_AUTO)
                bg = COLOR_AUTO
                border = BORDER_AUTO
            else:
                badge_html = _badge("MANUAL", COLOR_MANUAL, BORDER_MANUAL)
                bg = COLOR_MANUAL
                border = BORDER_MANUAL

            # Build provenance tooltip text
            prov = session.field_provenance.get(fkey)
            help_text = None
            if prov:
                help_text = (
                    f"Source: {prov.get('file', '?')} | "
                    f"Column: {prov.get('column', '?')} | "
                    f"Sample: {prov.get('sample_value', '?')}"
                )
            elif is_auto:
                help_text = "Auto-filled from ingested file data"

            label_html = (
                f"<div style='background:{bg};border-left:3px solid {border};"
                f"padding:2px 8px;margin-bottom:2px;border-radius:3px;display:inline-block'>"
                f"<b>{fkey}</b>&nbsp;{badge_html}</div>"
            )
            st.markdown(label_html, unsafe_allow_html=True)

            # Inline edit — always editable, no mode toggle
            widget_key = f"field__{fkey}"

            if isinstance(current_val, bool):
                new_val = st.checkbox(
                    fkey, value=bool(current_val), key=widget_key, help=help_text, label_visibility="collapsed"
                )
            else:
                new_val = st.text_input(
                    fkey,
                    value=str(current_val) if current_val is not None else "",
                    key=widget_key,
                    help=help_text,
                    label_visibility="collapsed",
                )

            # On change: update via service (adds audit entry)
            stored = session.fields.get(fkey)
            if isinstance(current_val, bool):
                if new_val != stored:
                    update_field(session, fkey, new_val)
            else:
                if str(new_val) != str(stored if stored is not None else ""):
                    update_field(session, fkey, new_val)

            # Inline validation beneath field
            rules_for_field = [
                r for r in validate_fields(session.fields, industry)
                if r.field == fkey
            ]
            for vr in rules_for_field:
                if vr.severity == Severity.ERROR:
                    st.markdown(
                        f"<small style='color:#dc2626'>🔴 {vr.message}</small>",
                        unsafe_allow_html=True,
                    )
                else:
                    ack_key = f"ack__{fkey}__{vr.message[:30]}"
                    if ack_key not in st.session_state.acknowledged_warnings:
                        col_w, col_btn = st.columns([5, 1])
                        col_w.markdown(
                            f"<small style='color:#d97706'>🟡 {vr.message}</small>",
                            unsafe_allow_html=True,
                        )
                        if col_btn.button("Dismiss", key=f"btn_{ack_key}"):
                            st.session_state.acknowledged_warnings.add(ack_key)

        st.markdown("---")

    # Anomaly inline display
    if session.anomalies:
        st.markdown("### 🟠 Detected Anomalies")
        for a in session.anomalies:
            lo, hi = a["expected_range"]
            unit = a.get("unit", "")
            st.markdown(
                f"<div style='background:{COLOR_ANOMALY};border-left:3px solid {BORDER_ANOMALY};"
                f"padding:6px 10px;border-radius:3px;margin:4px 0'>"
                f"🟠 <b>{a['field']}</b>: {a['value']:.2f}{unit} &nbsp;|&nbsp; "
                f"expected [{lo:.1f}{unit} — {hi:.1f}{unit}]<br>"
                f"<small>{a['message']}</small></div>",
                unsafe_allow_html=True,
            )


# ==========================================================================
# Section: Validate
# ==========================================================================

elif st.session_state.nav == "Validate":
    st.header("✅ Field Validation")

    industry = session.fields.get("industry") or None
    results = validate_fields(session.fields, industry)
    required_fields = get_required_fields()

    errors = [r for r in results if r.severity == Severity.ERROR]
    warnings_list = [r for r in results if r.severity == Severity.WARNING]

    missing = [
        f for f in required_fields
        if not session.fields.get(f)
    ]

    col_e, col_w, col_m = st.columns(3)
    col_e.metric("🔴 Errors", len(errors))
    col_w.metric("🟡 Warnings", len(warnings_list))
    col_m.metric("Required fields empty", len(missing))

    if missing:
        st.error(f"Required fields missing values: {', '.join(missing)}")

    if errors:
        st.markdown("#### Errors (block pipeline execution)")
        for r in errors:
            st.markdown(
                f"<div style='background:{COLOR_MISSING};border-left:3px solid {BORDER_MISSING};"
                f"padding:6px 10px;border-radius:3px;margin:4px 0'>"
                f"🔴 <b>{r.field}</b>: {r.message}</div>",
                unsafe_allow_html=True,
            )
    else:
        st.success("No blocking errors.")

    if warnings_list:
        st.markdown("#### Warnings (acknowledgment required)")
        for r in warnings_list:
            ack_key = f"validate_ack__{r.field}__{r.message[:30]}"
            acked = ack_key in st.session_state.acknowledged_warnings
            col_w2, col_btn2 = st.columns([6, 1])
            col_w2.markdown(
                f"<div style='background:{COLOR_MANUAL};border-left:3px solid {BORDER_MANUAL};"
                f"padding:6px 10px;border-radius:3px'>"
                f"🟡 <b>{r.field}</b>: {r.message}"
                f"{'  ✓ Acknowledged' if acked else ''}</div>",
                unsafe_allow_html=True,
            )
            if not acked:
                if col_btn2.button("Acknowledge", key=f"vbtn_{ack_key}"):
                    st.session_state.acknowledged_warnings.add(ack_key)
                    audit_event(
                        session, "validation_event", "user",
                        f"Warning acknowledged: {r.field} — {r.message}"
                    )


# ==========================================================================
# Section: Run
# ==========================================================================

elif st.session_state.nav == "Run":
    st.header("🚀 Run Pipeline")

    industry = session.fields.get("industry") or None
    blocking = has_blocking_errors(session.fields, industry)
    required_fields = get_required_fields()
    missing_required = [f for f in required_fields if not session.fields.get(f)]

    can_run = not blocking and not missing_required and bool(session.prepared_input_path)

    if not session.prepared_input_path:
        st.warning("No prepared input — upload and parse files first.")

    if missing_required:
        st.error(f"Required fields are empty: {', '.join(missing_required)}. Fill them in Review & Edit.")

    if blocking:
        st.error("Blocking validation errors detected. Fix them in Validate before running.")

    run_btn = st.button(
        "▶ Run Pipeline",
        type="primary",
        disabled=not can_run,
    )

    if run_btn and can_run:
        steps = [
            "Parsing trial balance…",
            "Classifying accounts…",
            "Detecting patterns…",
            "Calculating EBITDA…",
            "Generating normalized view…",
            "Calculating financial metrics…",
        ]
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            result_holder = {}

            def _run() -> None:
                for i, step in enumerate(steps[:-1]):
                    status_text.markdown(f"**Step {i+1}/{len(steps)}:** {step}")
                    progress_bar.progress((i + 1) / len(steps))
                result_holder["result"] = run_pipeline_from_session(session)
                status_text.markdown(f"**Step {len(steps)}/{len(steps)}:** {steps[-1]}")
                progress_bar.progress(1.0)

            _run()
            result = result_holder["result"]
            progress_bar.empty()
            status_text.empty()
            st.success("Pipeline completed successfully!")
            st.session_state.nav = "Results"
            st.rerun()
        except (ValueError, TypeError, RuntimeError, OSError, KeyError) as exc:
            logger.error("Pipeline execution failed in UI: %s", exc)
            progress_bar.empty()
            status_text.empty()
            st.error("Pipeline failed. Check logs for details.")


# ==========================================================================
# Section: Results
# ==========================================================================

elif st.session_state.nav == "Results":
    st.header("📈 Results")

    result = session.pipeline_result
    if result is None:
        st.info("No pipeline results yet. Run the pipeline first.")
        st.stop()

    # Key metrics cards
    metrics_report = result.get("metrics_report") or {}
    profitability = metrics_report.get("profitability", {})

    if profitability:
        st.markdown("### Key Metrics")
        cols = st.columns(min(4, len(profitability)))
        for i, (key, val) in enumerate(profitability.items()):
            label = key.replace("_", " ").replace(" %", "").title()
            if val is None:
                display = "N/A"
            elif key.endswith("_%"):
                display = f"{val:.1f}%"
            else:
                display = f"{val:,.2f}"
            cols[i % len(cols)].metric(label, display)

    # Anomaly summary card
    if session.anomalies:
        st.markdown("### 🟠 Anomaly Summary")
        with st.expander(f"{len(session.anomalies)} anomaly/anomalies detected", expanded=True):
            for a in session.anomalies:
                st.markdown(
                    f"<div style='background:{COLOR_ANOMALY};border-left:3px solid {BORDER_ANOMALY};"
                    f"padding:6px 10px;border-radius:3px;margin:4px 0'>"
                    f"🟠 {a['message']}</div>",
                    unsafe_allow_html=True,
                )
    else:
        st.success("No anomalies detected.")

    # Full output section
    output_files = result.get("files", {})
    if output_files:
        st.markdown("### Full Output")
        import pandas as _pd
        tabs = st.tabs(list(output_files.keys()))
        for tab, (label, fpath) in zip(tabs, output_files.items()):
            with tab:
                try:
                    df = _pd.read_csv(fpath)
                    st.dataframe(df, use_container_width=True)
                    with open(fpath, "rb") as fh:
                        st.download_button(
                            f"⬇ Download {Path(fpath).name}",
                            data=fh.read(),
                            file_name=Path(fpath).name,
                            mime="text/csv",
                            key=f"dl_{label}",
                        )
                except (OSError, ValueError, KeyError, _pd.errors.ParserError) as exc:
                    logger.warning("Could not read output CSV %s: %s", fpath, exc)
                    st.error("Could not read one output file.")

    # Download session JSON and export reports
    st.markdown("---")
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        if st.button("💾 Save & Download Session"):
            tmp_export = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
            tmp_export.close()
            save_session_file(session, tmp_export.name)
            audit_event(session, "session_save", "user", "Session exported to JSON.")
            with open(tmp_export.name, "rb") as fp:
                st.download_button(
                    "⬇ Download Session JSON",
                    data=fp.read(),
                    file_name="financial_normalizer_session.json",
                    mime="application/json",
                    key="dl_session",
                )

    # Excel and PDF exports
    st.markdown("### Export Reports")
    col_ex, col_pdf, col_reset = st.columns(3)
    with col_ex:
        if st.button("📊 Download Excel Report"):
            try:
                tmp_excel = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
                tmp_excel.close()
                generate_excel(
                    tmp_excel.name,
                    result,
                    session.fields,
                    session.audit_trail,
                    session.anomalies,
                )
                with open(tmp_excel.name, "rb") as fp:
                    st.download_button(
                        "⬇ financial_report.xlsx",
                        data=fp.read(),
                        file_name="financial_report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_excel",
                    )
            except (ImportError, OSError, ValueError, RuntimeError) as exc:
                logger.error("Excel export failed in UI: %s", exc)
                st.error("Excel export failed. Check logs for details.")
    with col_pdf:
        if st.button("📄 Download PDF Report"):
            try:
                tmp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
                tmp_pdf.close()
                generate_pdf(
                    tmp_pdf.name,
                    result,
                    session.fields,
                    session.audit_trail,
                    session.anomalies,
                )
                with open(tmp_pdf.name, "rb") as fp:
                    st.download_button(
                        "⬇ financial_report.pdf",
                        data=fp.read(),
                        file_name="financial_report.pdf",
                        mime="application/pdf",
                        key="dl_pdf",
                    )
            except (ImportError, OSError, ValueError, RuntimeError) as exc:
                logger.error("PDF export failed in UI: %s", exc)
                st.error("PDF export failed. Check logs for details.")
    with col_reset:
        if st.button("🔄 Reset Session"):
            st.session_state.session = SessionState()
            st.session_state.nav = "Upload"
            st.session_state.acknowledged_warnings = set()
            st.rerun()


# ==========================================================================
# Section: Compare
# ==========================================================================

elif st.session_state.nav == "Compare":
    st.header("🔀 Compare Filings")

    filings = [f for f in session.ingested_files if f.status in ("success", "warning")]
    if len(filings) < 2:
        st.info("Need at least two successfully parsed filings to compare.")
        st.stop()

    # Build display labels
    filing_labels = [
        f"{f.filename} ({f.statement_type.replace('_', ' ').title()})"
        for f in filings
    ]

    col_a, col_b = st.columns(2)
    with col_a:
        idx_a = st.selectbox("Filing A", range(len(filing_labels)), format_func=lambda i: filing_labels[i], key="cmp_a")
    with col_b:
        idx_b = st.selectbox("Filing B", range(len(filing_labels)), format_func=lambda i: filing_labels[i], key="cmp_b", index=min(1, len(filing_labels) - 1))

    threshold = st.slider("Delta threshold (%)", min_value=1, max_value=50, value=10, step=1)

    if idx_a == idx_b:
        st.warning("Select two different filings to compare.")
        st.stop()

    filing_a_obj = filings[idx_a]
    filing_b_obj = filings[idx_b]

    # Build FilingData from ingested file metadata + dataframe columns
    def _fields_from_ingestedfile(ifile) -> dict:
        fields: dict = {}
        if ifile.dataframe is not None and not ifile.dataframe.empty:
            df = ifile.dataframe
            for col in df.columns:
                col_lower = col.lower()
                non_null = df[col].dropna()
                if non_null.empty:
                    continue
                try:
                    fields[col_lower] = float(non_null.iloc[0])
                except (ValueError, TypeError):
                    pass
        return fields

    fd_a = FilingData(
        name=filing_labels[idx_a],
        statement_type=filing_a_obj.statement_type,
        fields=_fields_from_ingestedfile(filing_a_obj),
    )
    fd_b = FilingData(
        name=filing_labels[idx_b],
        statement_type=filing_b_obj.statement_type,
        fields=_fields_from_ingestedfile(filing_b_obj),
    )

    cmp_result = compare_filings(fd_a, fd_b, threshold_pct=float(threshold))
    cmp_dict = cmp_result.as_dict()

    # Display
    if not cmp_result.rows:
        st.info("No numeric fields found in common between the two filings.")
    else:
        import pandas as _pd

        table_rows = []
        for row in cmp_result.rows:
            table_rows.append({
                "Field": row.field.replace("_", " ").title(),
                filing_labels[idx_a]: f"{row.value_a:,.2f}" if row.value_a is not None else "—",
                filing_labels[idx_b]: f"{row.value_b:,.2f}" if row.value_b is not None else "—",
                "Δ (abs)": f"{row.delta_abs:,.2f}" if row.delta_abs is not None else "—",
                "Δ%": f"{row.delta_pct:.1f}%" if row.delta_pct is not None else "—",
                "Status": row.status.upper(),
            })

        df_cmp = _pd.DataFrame(table_rows)

        # Color rows by status
        def _highlight_row(row):
            if row["Status"] == "MISSING":
                return [f"background-color: {COLOR_MISSING}"] * len(row)
            if row["Status"] == "THRESHOLD_EXCEEDED":
                return [f"background-color: {COLOR_MANUAL}"] * len(row)
            return [""] * len(row)

        st.dataframe(
            df_cmp.style.apply(_highlight_row, axis=1),
            use_container_width=True,
            hide_index=True,
        )

        st.caption(
            f"🟡 Amber = delta > {threshold}% threshold  |  🔴 Red = field missing in one filing"
        )

    # Missing fields
    if cmp_result.missing_fields:
        st.markdown("### Missing Fields")
        for m in cmp_result.missing_fields:
            st.markdown(
                f"<div style='background:{COLOR_MISSING};padding:5px 10px;border-radius:3px;margin:3px 0'>"
                f"<b>{m['field']}</b> — present in <i>{m['present_in']}</i>, "
                f"absent from <i>{m['absent_from']}</i></div>",
                unsafe_allow_html=True,
            )

    # Anomalies unique to each filing
    if cmp_result.anomalies_unique_a or cmp_result.anomalies_unique_b:
        st.markdown("### Anomalies Unique to Each Filing")
        col_ua, col_ub = st.columns(2)
        with col_ua:
            st.markdown(f"**{filing_labels[idx_a]}**")
            if cmp_result.anomalies_unique_a:
                for f in cmp_result.anomalies_unique_a:
                    st.markdown(f"🟠 `{f}`")
            else:
                st.caption("None")
        with col_ub:
            st.markdown(f"**{filing_labels[idx_b]}**")
            if cmp_result.anomalies_unique_b:
                for f in cmp_result.anomalies_unique_b:
                    st.markdown(f"🟠 `{f}`")
            else:
                st.caption("None")

    # Export comparison
    st.markdown("---")
    col_cex, col_cpdf = st.columns(2)
    with col_cex:
        if st.button("📊 Export Comparison Excel"):
            try:
                from src.reporting import generate_comparison_excel
                tmp_cex = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
                tmp_cex.close()
                generate_comparison_excel(tmp_cex.name, cmp_dict, threshold_pct=float(threshold))
                with open(tmp_cex.name, "rb") as fp:
                    st.download_button(
                        "⬇ comparison_report.xlsx",
                        data=fp.read(),
                        file_name="comparison_report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_cmp_excel",
                    )
            except (ImportError, OSError, ValueError, RuntimeError) as exc:
                logger.error("Comparison Excel export failed: %s", exc)
                st.error("Comparison Excel export failed. Check logs for details.")
    with col_cpdf:
        if st.button("📄 Export Comparison PDF"):
            try:
                from src.reporting import generate_comparison_pdf
                tmp_cpdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
                tmp_cpdf.close()
                generate_comparison_pdf(tmp_cpdf.name, cmp_dict, threshold_pct=float(threshold))
                with open(tmp_cpdf.name, "rb") as fp:
                    st.download_button(
                        "⬇ comparison_report.pdf",
                        data=fp.read(),
                        file_name="comparison_report.pdf",
                        mime="application/pdf",
                        key="dl_cmp_pdf",
                    )
            except (ImportError, OSError, ValueError, RuntimeError) as exc:
                logger.error("Comparison PDF export failed: %s", exc)
                st.error("Comparison PDF export failed. Check logs for details.")
