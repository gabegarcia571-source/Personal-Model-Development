"""
Quick test to verify FinancialMetricsEngine works with the normalization pipeline.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from normalization.metrics import FinancialMetricsEngine
from normalization.engine import NormalizedFinancialView, NormalizedViewConfig, NormalizedViewEngine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_metrics_engine():
    """Test FinancialMetricsEngine initialization and basic functionality"""
    
    print("\n" + "="*70)
    print("TESTING: FinancialMetricsEngine Integration")
    print("="*70 + "\n")
    
    # Check imports
    print("✓ Successfully imported FinancialMetricsEngine")
    print("✓ Successfully imported NormalizedFinancialView")
    
    # Verify class has required methods
    required_methods = [
        'gross_margin',
        'ebitda_margin',
        'operating_margin',
        'net_margin',
        'current_ratio',
        'debt_to_ebitda',
        'interest_coverage_ratio',
        'ev_to_ebitda',
        'ev_to_revenue',
        'get_full_report',
    ]
    
    missing_methods = []
    for method in required_methods:
        if not hasattr(FinancialMetricsEngine, method):
            missing_methods.append(method)
    
    if missing_methods:
        print(f"❌ Missing methods: {missing_methods}")
        return False
    
    print(f"✓ All {len(required_methods)} required methods present")
    
    # Test get_full_report structure
    print("\n" + "-"*70)
    print("Checking get_full_report() output structure...")
    print("-"*70)
    
    # Create a minimal test view
    test_view = NormalizedFinancialView(
        period="2024",
        period_end_date="2024-12-31",
        entity="TestCo",
    )
    
    # Create engine without enterprise value
    engine = FinancialMetricsEngine(test_view)
    report = engine.get_full_report()
    
    expected_sections = ['profitability', 'health', 'valuation']
    missing_sections = [s for s in expected_sections if s not in report]
    
    if missing_sections:
        print(f"❌ Missing report sections: {missing_sections}")
        return False
    
    print(f"✓ Report has all sections: {expected_sections}")
    
    # Check section contents
    expected_metrics = {
        'profitability': [
            'gross_margin_%',
            'ebitda_margin_%',
            'operating_margin_%',
            'net_margin_%',
        ],
        'health': [
            'current_ratio',
            'debt_to_ebitda',
            'interest_coverage_ratio',
        ],
        'valuation': [
            'ev_to_ebitda',
            'ev_to_revenue',
        ],
    }
    
    all_good = True
    for section, metrics in expected_metrics.items():
        section_data = report.get(section, {})
        missing = [m for m in metrics if m not in section_data]
        if missing:
            print(f"❌ Section '{section}' missing metrics: {missing}")
            all_good = False
        else:
            print(f"✓ Section '{section}' has all metrics: {metrics}")
    
    if not all_good:
        return False
    
    # Test with enterprise value
    print("\n" + "-"*70)
    print("Testing with enterprise_value parameter...")
    print("-"*70)
    
    engine_with_ev = FinancialMetricsEngine(test_view, enterprise_value=1000000)
    print(f"✓ FinancialMetricsEngine initialized with enterprise_value=$1,000,000")
    report_with_ev = engine_with_ev.get_full_report()
    print(f"✓ get_full_report() returns valid dict with {len(report_with_ev)} sections")
    
    # Check that valuation metrics are None (no revenue/EBITDA in test view)
    if report_with_ev['valuation']['ev_to_ebitda'] is None:
        print(f"✓ EV/EBITDA correctly returns None when EBITDA is unavailable")
    
    if report_with_ev['valuation']['ev_to_revenue'] is None:
        print(f"✓ EV/Revenue correctly returns None when revenue is unavailable")
    
    print("\n" + "="*70)
    print("✅ ALL TESTS PASSED")
    print("="*70 + "\n")
    
    return True


if __name__ == "__main__":
    success = test_metrics_engine()
    sys.exit(0 if success else 1)
