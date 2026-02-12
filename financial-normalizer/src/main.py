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
from pathlib import Path
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from ingestion.trial_balance_parser import TrialBalanceParser
from classification.classifier import ClassificationEngine
from normalization.adjustments import AdjustmentCalculator, AdjustmentDetail, AdjustmentCategory
from normalization.engine import NormalizedViewEngine, NormalizedViewConfig


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Financial Statement Normalization Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic processing
  python main.py --input data/input/sample_trial_balance.csv --output data/output/

  # With industry-specific classification
  python main.py --input trial_balance.csv --output results/ --industry saas_tech

  # Process and generate EBITDA metrics
  python main.py --input trial_balance.csv --output results/ --ebitda
"""
    )
    
    parser.add_argument('--input', '-i',
                       help='Input trial balance CSV file',
                       default='data/input/sample_trial_balance.csv')
    parser.add_argument('--output', '-o',
                       help='Output directory for results',
                       default='data/output/')
    parser.add_argument('--industry', 
                       choices=['saas_tech', 'manufacturing', 'financial_services'],
                       help='Industry for classification context')
    parser.add_argument('--ebitda',
                       action='store_true',
                       help='Calculate and report EBITDA metrics')
    parser.add_argument('--detect-patterns',
                       action='store_true',
                       default=True,
                       help='Detect suspicious accounting patterns')
    parser.add_argument('--verbose', '-v',
                       action='store_true',
                       help='Verbose output')
    
    return parser.parse_args()


def main():
    """Main application workflow"""
    
    print("="*80)
    print("FINANCIAL NORMALIZER".center(80))
    print("="*80)
    
    # Parse arguments
    args = parse_arguments()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate input
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"Input file not found: {args.input}")
        return 1
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Processing: {args.input}")
    logger.info(f"Output directory: {output_dir}")
    if args.industry:
        logger.info(f"Industry: {args.industry}")
    
    try:
        # Step 1: Parse trial balance
        print("\n[1/4] Parsing trial balance...")
        logger.info("Parsing trial balance data")
        
        parser = TrialBalanceParser(str(input_path))
        transactions = parser.parse()
        logger.info(f"Loaded {len(transactions)} transactions")
        
        # Convert to DataFrame
        df = pd.DataFrame({
            'Account_Code': [t.account for t in transactions],
            'Account_Name': [t.description for t in transactions],
            'Amount': [t.amount for t in transactions],
            'Date': [t.date for t in transactions],
            'Entity': [t.entity for t in transactions],
        })
        
        # Save parsed data
        parsed_output = output_dir / "1_parsed_transactions.csv"
        df.to_csv(parsed_output, index=False)
        print(f"   ✓ Parsed {len(transactions)} transactions")
        logger.info(f"Saved parsed data to {parsed_output}")
        
        # Step 2: Classify accounts
        print("\n[2/4] Classifying accounts...")
        logger.info("Classifying accounts")
        
        classifier = ClassificationEngine()
        df_classified = classifier.classify_dataframe(df, industry=args.industry)
        
        # Save classified data
        classified_output = output_dir / "2_classified_accounts.csv"
        df_classified.to_csv(classified_output, index=False)
        print(f"   ✓ Classified accounts")
        logger.info(f"Saved classified accounts to {classified_output}")
        
        # Detect suspicious patterns if requested
        if args.detect_patterns:
            print("\n[2b] Detecting suspicious patterns...")
            flags = classifier.detect_suspicious_patterns(df)
            if flags:
                print(f"   ⚠ Found {len(flags)} suspicious patterns:")
                for flag in flags:
                    print(f"      - {flag.pattern}: {flag.reason} [{flag.risk_level}]")
                logger.warning(f"Found {len(flags)} suspicious patterns")
            else:
                print("   ✓ No suspicious patterns detected")
        
        # Step 3: Calculate EBITDA metrics if requested
        if args.ebitda:
            print("\n[3/4] Calculating EBITDA metrics...")
            logger.info("Calculating EBITDA metrics")
            
            calc = AdjustmentCalculator(df_classified)
            ebitda_summary = calc.get_summary()
            
            ebitda_output = output_dir / "3_ebitda_metrics.csv"
            ebitda_summary.to_csv(ebitda_output, index=False)
            
            print("   ✓ EBITDA Metrics:")
            for _, row in ebitda_summary.iterrows():
                print(f"      {row['Metric']}: ${row['EBITDA']:,.0f}")
            logger.info(f"Saved EBITDA metrics to {ebitda_output}")
        
        # Step 4: Generate normalized view
        print("\n[4/4] Generating normalized financial view...")
        logger.info("Generating normalized view")
        
        config = NormalizedViewConfig(
            industry=args.industry,
            include_intercompany_eliminations=True,
            apply_industry_normalization=True
        )
        
        engine = NormalizedViewEngine(config)
        normalized_view = engine.generate_normalized_view(df_classified)
        logger.info("Generated normalized view")
        
        # Save summary
        summary_output = output_dir / "4_normalized_summary.csv"
        if not normalized_view.normalized_income_statement.empty:
            normalized_view.normalized_income_statement.to_csv(summary_output, index=False)
            print(f"   ✓ Generated normalized view")
            logger.info(f"Saved normalized view to {summary_output}")
        else:
            print(f"   ℹ Normalized view is empty (check input data)")
        
        # Final summary
        print("\n" + "="*80)
        print("PROCESSING COMPLETE".center(80))
        print("="*80)
        print(f"\nResults saved to: {output_dir}")
        print("\nGenerated files:")
        for file in sorted(output_dir.glob("*.csv")):
            size = file.stat().st_size
            print(f"  - {file.name:<40} ({size:,} bytes)")
        
        print("\n✓ All processing completed successfully!")
        logger.info("Processing completed successfully")
        return 0
        
    except Exception as e:
        logger.error(f"Error during processing: {str(e)}", exc_info=True)
        print(f"\n✗ Error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
