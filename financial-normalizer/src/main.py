"""
Financial Normalizer - Main Application

Complete pipeline for:
1. Parsing trial balance data
2. Classifying accounts
3. Detecting adjustments
4. Calculating EBITDA metrics
5. Generating normalized financial statements
"""

import sys
import argparse
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from ingestion.trial_balance_parser import TrialBalanceParser
    from settings import settings as _settings
    from classification.classifier import ClassificationEngine
    from normalization.adjustments import AdjustmentCalculator
    from normalization.engine import NormalizedViewEngine, NormalizedViewConfig
    from normalization.metrics import FinancialMetricsEngine
except ModuleNotFoundError:
    from src.ingestion.trial_balance_parser import TrialBalanceParser
    from src.settings import settings as _settings
    from src.classification.classifier import ClassificationEngine
    from src.normalization.adjustments import AdjustmentCalculator
    from src.normalization.engine import NormalizedViewEngine, NormalizedViewConfig
    from src.normalization.metrics import FinancialMetricsEngine

# Apply settings-based logging — overwrites basicConfig above
_settings.configure_logging()
logger = logging.getLogger(__name__)


def enforce_python_312() -> None:
    """Require Python 3.12 for reproducible behavior across local and container runs."""
    if (sys.version_info.major, sys.version_info.minor) != (3, 12):
        raise RuntimeError(
            f"Python 3.12 is required; detected {sys.version_info.major}.{sys.version_info.minor}. "
            "Use python3.12 or activate the project 3.12 virtual environment."
        )

def _add_shared_pipeline_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--input', '-i',
                        help='Input trial balance CSV file',
                        default='data/input/sample_trial_balance.csv')
    parser.add_argument('--output', '-o',
                        help='Output directory for results',
                            default=_settings.output_dir)
    parser.add_argument('--industry',
                        choices=[
                            'saas_tech', 'traditional_software', 'ecommerce_retail',
                            'healthcare_medtech', 'financial_services', 'manufacturing',
                            'energy_utilities', 'real_estate', 'media_entertainment',
                            'professional_services', 'consumer_goods_cpg',
                            'industrials_infrastructure',
                        ],
                        help='Industry for benchmark context (see config/benchmarks.yaml)')
    parser.add_argument('--ebitda',
                        action='store_true',
                        help='Calculate and report EBITDA metrics')
    parser.add_argument('--detect-patterns',
                        action='store_true',
                            default=_settings.pipeline_detect_patterns,
                        help='Detect suspicious accounting patterns')
    parser.add_argument('--ev',
                        type=float,
                        default=None,
                        help='Enterprise value for valuation metrics (optional)')
    parser.add_argument('--verbose', '-v',
                        action='store_true',
                        help='Verbose output')


def parse_arguments(argv=None):
    """Parse command line arguments with subcommands and legacy fallback."""
    raw_args = list(sys.argv[1:] if argv is None else argv)

    # Backward compatibility: if first argument is an option, treat as legacy normalize call.
    if not raw_args or raw_args[0].startswith('-'):
        legacy_parser = argparse.ArgumentParser(
            description="Financial Statement Normalization Engine",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        _add_shared_pipeline_args(legacy_parser)
        legacy_args = legacy_parser.parse_args(raw_args)
        setattr(legacy_args, 'command', 'normalize')
        return legacy_args

    parser = argparse.ArgumentParser(
        description="Financial Statement Normalization Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Backward-compatible basic processing
  python main.py --input data/input/sample_trial_balance.csv --output data/output/

  # Explicit normalize subcommand
  python main.py normalize --input data/input/sample_trial_balance.csv --output data/output/

  # With industry-specific classification
  python main.py normalize --input trial_balance.csv --output results/ --industry saas_tech

  # Validation suite
  python main.py validate

  # Report from output CSVs
  python main.py report --output data/output/

  # CI smoke-test
  python main.py smoke-test
"""
    )

    subparsers = parser.add_subparsers(dest='command')

    normalize_parser = subparsers.add_parser('normalize', help='Run normalization pipeline')
    _add_shared_pipeline_args(normalize_parser)

    validate_parser = subparsers.add_parser('validate', help='Run verification scripts and tests')
    validate_parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    report_parser = subparsers.add_parser('report', help='Print key metric summary from output CSVs')
    report_parser.add_argument('--output', '-o', default='data/output/', help='Output directory for results')
    report_parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    report_parser.add_argument(
        '--format',
        choices=['csv', 'excel', 'pdf'],
        default='csv',
        help='Export format: csv (stdout), excel (.xlsx), pdf (.pdf)',
    )
    report_parser.add_argument(
        '--report-file',
        default=None,
        dest='report_file',
        help='Output file path for excel/pdf exports (default: data/output/financial_report.{ext})',
    )

    smoke_parser = subparsers.add_parser('smoke-test', help='Run smoke test for CI confidence')
    smoke_parser.add_argument('--input', '-i', default='data/input/sample_trial_balance.csv')
    smoke_parser.add_argument('--output', '-o', default='data/output/smoke')
    smoke_parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    app_parser = subparsers.add_parser('app', help='Launch the Streamlit web interface')
    app_parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    return parser.parse_args(raw_args, namespace=None) if raw_args[0] != 'app' else parser.parse_known_args(raw_args)[0]


def validate_cli_args(args: argparse.Namespace) -> None:
    """Fail fast on invalid argument combinations."""
    if hasattr(args, 'ev') and args.ev is not None:
        try:
            float(args.ev)
        except (TypeError, ValueError) as exc:
            raise ValueError("--ev must be a valid number") from exc

    if hasattr(args, 'output') and args.output:
        out = Path(args.output)
        parent = out.parent if out.suffix else out
        if parent and not parent.exists():
            # create when possible for smoother UX
            parent.mkdir(parents=True, exist_ok=True)

    if hasattr(args, 'input') and args.command in ('normalize', 'smoke-test'):
        if args.input and not Path(args.input).exists():
            raise FileNotFoundError(f"Input file not found: {args.input}")


def run_pipeline(
    input_path: str,
    output_path: str,
    industry: Optional[str] = None,
    ebitda: bool = False,
    detect_patterns: bool = True,
    ev: Optional[float] = None,
) -> Dict[str, Any]:
    """Run full normalization pipeline and return structured outputs."""
    result: Dict[str, Any] = {
        'success': False,
        'output_dir': str(output_path),
        'files': {},
        'metrics_report': None,
        'flags': [],
    }

    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Processing: {input_path}")
    logger.info(f"Output directory: {output_dir}")
    if industry:
        logger.info(f"Industry: {industry}")

    # Step 1: Parse trial balance
    logger.info("Step 1/5: parsing trial balance")

    parser = TrialBalanceParser(
        str(input_file),
        imbalance_tolerance=_settings.imbalance_tolerance,
    )
    transactions = parser.parse()
    logger.info(f"Loaded {len(transactions)} transactions")

    df = pd.DataFrame({
        'Account_Code': [t.account for t in transactions],
        'Account_Name': [t.description for t in transactions],
        'Amount': [t.amount for t in transactions],
        'Date': [t.date for t in transactions],
        'Entity': [t.entity for t in transactions],
    })

    parsed_output = output_dir / "1_parsed_transactions.csv"
    df.to_csv(parsed_output, index=False)
    result['files']['parsed'] = str(parsed_output)
    logger.info("Parsed %d transactions and saved to %s", len(transactions), parsed_output)

    # Step 2: Classify accounts
    logger.info("Step 2/5: classifying accounts")

    classifier = ClassificationEngine()
    df_classified = classifier.classify_dataframe(df, industry=industry)

    classified_output = output_dir / "2_classified_accounts.csv"
    df_classified.to_csv(classified_output, index=False)
    result['files']['classified'] = str(classified_output)
    logger.info("Saved classified accounts to %s", classified_output)

    if detect_patterns:
        logger.info("Step 2b/5: detecting suspicious patterns")
        flags = classifier.detect_suspicious_patterns(df_classified)
        result['flags'] = flags
        if flags:
            logger.warning("Found %d suspicious patterns", len(flags))
            for flag in flags:
                logger.warning("Pattern=%s reason=%s risk=%s", flag.pattern, flag.reason, flag.risk_level)
        else:
            logger.info("No suspicious patterns detected")

    if ebitda:
        logger.info("Step 3/5: calculating EBITDA metrics")

        calc = AdjustmentCalculator(df_classified)
        ebitda_summary = calc.get_summary()

        ebitda_output = output_dir / "3_ebitda_metrics.csv"
        ebitda_summary.to_csv(ebitda_output, index=False)
        result['files']['ebitda'] = str(ebitda_output)

        for _, row in ebitda_summary.iterrows():
            logger.info("EBITDA metric %s=%s", row['Metric'], f"{row['EBITDA']:,.0f}")
        logger.info("Saved EBITDA metrics to %s", ebitda_output)

    # Step 4: Generate normalized view
    logger.info("Step 4/5: generating normalized financial view")

    config = NormalizedViewConfig(
        industry=industry,
        include_intercompany_eliminations=True,
        apply_industry_normalization=True,
    )

    engine = NormalizedViewEngine(config)
    normalized_view = engine.generate_view(str(parsed_output))
    logger.info("Generated normalized view")

    summary_output = output_dir / "4_normalized_summary.csv"
    if not normalized_view.normalized_income_statement.empty:
        normalized_view.normalized_income_statement.to_csv(summary_output, index=False)
        result['files']['summary'] = str(summary_output)
        logger.info("Generated and saved normalized view to %s", summary_output)
    else:
        logger.warning("Normalized view is empty (check input data)")

    # Step 5: Calculate financial metrics
    logger.info("Step 5/5: calculating financial metrics")
    try:
        metrics_engine = FinancialMetricsEngine(normalized_view, enterprise_value=ev)
        metrics_report = metrics_engine.get_full_report()
        result['metrics_report'] = metrics_report

        for section in ('profitability', 'health', 'valuation'):
            section_data = metrics_report.get(section, {})
            logger.info("Metrics section: %s", section.capitalize())
            for metric_key, metric_val in section_data.items():
                if metric_key.endswith('_%'):
                    label = metric_key[:-2].replace('_', ' ').title()
                    val_str = "N/A" if metric_val is None else f"{metric_val:.2f}%"
                else:
                    label = metric_key.replace('_', ' ').title()
                    val_str = "N/A" if metric_val is None else f"{metric_val:.2f}"

                logger.info("%s: %s", label, val_str)
    except (TypeError, ValueError, KeyError, AttributeError, ZeroDivisionError) as exc:
        logger.error("Failed to calculate financial metrics for input=%s: %s", input_path, exc)

    result['success'] = True
    return result


def run_app(extra_args: list | None = None) -> int:
    """Launch the Streamlit web interface."""
    import importlib.util
    if importlib.util.find_spec("streamlit") is None:
        logger.error("Streamlit is not installed")
        return 1

    app_entry = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
    if not app_entry.exists():
        logger.error("App entry point not found")
        return 1

    cmd = [sys.executable, "-m", "streamlit", "run", str(app_entry)]
    if extra_args:
        cmd.extend(extra_args)

    logger.info("Launching Streamlit app")
    return subprocess.run(cmd).returncode


def _check_app_entry_point() -> bool:
    """Check that the Streamlit app entry point exists and is syntactically importable. For CI use."""
    import ast
    app_entry = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
    if not app_entry.exists():
        logger.error("App entry point check failed: streamlit_app.py not found")
        return False
    try:
        source = app_entry.read_text(encoding="utf-8")
        ast.parse(source)
        logger.info("App entry point check passed")
        return True
    except SyntaxError as exc:
        logger.error("App entry point check failed due to syntax error: %s", exc)
        return False


def run_validation_suite() -> int:
    """Run verification scripts and tests."""
    root = Path(__file__).resolve().parents[1]
    scripts = ['verify_parsers.py', 'verify_setup.py', 'run_tests.py']

    for script in scripts:
        logger.info("Validation suite running script=%s", script)
        completed = subprocess.run([sys.executable, script], cwd=root, check=False)
        if completed.returncode != 0:
            logger.error("Validation script failed: script=%s exit_code=%d", script, completed.returncode)
            return 1

    logger.info("Validation suite checking app entry point")
    if not _check_app_entry_point():
        return 1

    logger.info("All validation scripts passed")
    return 0


def print_report(output_path: str) -> int:
    """Print key EBITDA and normalized summary metrics from output CSVs."""
    output_dir = Path(output_path)
    ebitda_file = output_dir / '3_ebitda_metrics.csv'
    summary_file = output_dir / '4_normalized_summary.csv'

    logger.info("%s", "=" * 80)
    logger.info("%s", "METRIC REPORT".center(80))
    logger.info("%s", "=" * 80)

    if ebitda_file.exists():
        ebitda_df = pd.read_csv(ebitda_file)
        logger.info("EBITDA Metrics:")
        for _, row in ebitda_df.iterrows():
            logger.info("%s: %s", row['Metric'], f"{row['EBITDA']:,.2f}")
    else:
        logger.warning("EBITDA metrics file not found")

    if summary_file.exists():
        summary_df = pd.read_csv(summary_file)
        ebitda_row = summary_df[summary_df['Line_Item'] == 'EBITDA']
        if not ebitda_row.empty:
            logger.info("Normalized EBITDA: %s", f"{float(ebitda_row.iloc[0]['Amount']):,.2f}")
    else:
        logger.warning("Normalized summary file not found")

    return 0


def run_smoke_test(args) -> int:
    """Run a minimal normalize flow for CI confidence."""
    logger.info("Smoke test: checking app entry point")
    if not _check_app_entry_point():
        return 1

    try:
        run_pipeline(
            input_path=args.input,
            output_path=args.output,
            industry=None,
            ebitda=False,
            detect_patterns=True,
            ev=None,
        )
        logger.info("Smoke test: pipeline completed successfully")
        return 0
    except (FileNotFoundError, ValueError, TypeError, RuntimeError, OSError, KeyError) as exc:
        logger.error("Smoke test failed for input=%s output=%s: %s", args.input, args.output, exc)
        return 1

def export_report(args) -> int:
    """Export a formatted Excel or PDF report from pipeline output CSVs."""
    output_dir = Path(args.output)
    fmt = getattr(args, "format", "csv")
    report_file = getattr(args, "report_file", None)

    if fmt == "csv":
        return print_report(args.output)

    pipeline_result: Dict[str, Any] = {"success": True, "files": {}, "metrics_report": None}
    for key, fname in [
        ("parsed", "1_parsed_transactions.csv"),
        ("classified", "2_classified_accounts.csv"),
        ("ebitda", "3_ebitda_metrics.csv"),
        ("summary", "4_normalized_summary.csv"),
    ]:
        p = output_dir / fname
        if p.exists():
            pipeline_result["files"][key] = str(p)

    try:
        from reporting import generate_excel, generate_pdf
    except ModuleNotFoundError:
        from src.reporting import generate_excel, generate_pdf

    if report_file is None:
        ext = ".xlsx" if fmt == "excel" else ".pdf"
        report_file = str(output_dir / f"financial_report{ext}")

    try:
        if fmt == "excel":
            out = generate_excel(report_file, pipeline_result, {}, [])
        else:
            out = generate_pdf(report_file, pipeline_result, {}, [])
        logger.info("Report written to %s", out)
    except (ImportError, OSError) as exc:
        logger.error("Report export failed: %s", exc)
        return 1
    return 0

def main():
    """Main application workflow."""
    enforce_python_312()

    logger.info("%s", "=" * 80)
    logger.info("%s", "FINANCIAL NORMALIZER".center(80))
    logger.info("%s", "=" * 80)

    # For 'app' command, capture extra flags to pass to Streamlit
    raw_args = list(sys.argv[1:])
    extra_streamlit_args: list = []
    if raw_args and raw_args[0] == 'app':
        extra_streamlit_args = raw_args[1:]

    args = parse_arguments()

    validate_cli_args(args)
    
    # Set logging level
    if getattr(args, 'verbose', False):
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        if args.command == 'app':
            return run_app(extra_streamlit_args or None)

        if args.command == 'validate':
            return run_validation_suite()

        if args.command == 'report':
            fmt = getattr(args, "format", "csv")
            if fmt == "csv":
                return print_report(args.output)
            return export_report(args)

        if args.command == 'smoke-test':
            return run_smoke_test(args)

        result = run_pipeline(
            input_path=args.input,
            output_path=args.output,
            industry=getattr(args, 'industry', None) or _settings.default_industry,
            ebitda=getattr(args, 'ebitda', _settings.pipeline_ebitda),
            detect_patterns=getattr(args, 'detect_patterns', _settings.pipeline_detect_patterns),
            ev=getattr(args, 'ev', None),
        )

        output_dir = Path(result['output_dir'])
        logger.info("%s", "=" * 80)
        logger.info("%s", "PROCESSING COMPLETE".center(80))
        logger.info("%s", "=" * 80)
        logger.info("Results saved to: %s", output_dir)
        logger.info("Generated files:")
        for file in sorted(output_dir.glob("*.csv")):
            size = file.stat().st_size
            logger.info("  - %s (%s bytes)", f"{file.name:<40}", f"{size:,}")

        logger.info("All processing completed successfully")
        logger.info("Processing completed successfully")
        return 0

    except (FileNotFoundError, ValueError, TypeError, RuntimeError, OSError, KeyError, subprocess.SubprocessError) as exc:
        logger.error("Error during processing command=%s: %s", getattr(args, 'command', 'unknown'), exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
