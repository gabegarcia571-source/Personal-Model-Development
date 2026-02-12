"""
Normalized View Engine

Main orchestrator that:
- Loads raw GL data
- Applies classifications
- Calculates adjustments
- Generates before/after views
- Computes EBITDA metrics
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
import logging

from classification.classifier import ClassificationEngine, AccountClassification, AccountType
from normalization.adjustments import (
    AdjustmentCalculator, AdjustmentDetail, AdjustmentCategory,
    EBITDACalculation, EBITDAMetric, ConsolidationEngine
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class NormalizedViewConfig:
    """Configuration for normalized view generation"""
    include_intercompany_eliminations: bool = True
    apply_industry_normalization: bool = True
    include_recurring_only: bool = False
    base_currency: str = "USD"
    industry: Optional[str] = None
    consolidate_multi_entity: bool = True


@dataclass
class BeforeAfterComparison:
    """Comparison of before/after adjustments"""
    account_code: str
    account_name: str
    account_type: str
    before_amount: float
    after_amount: float
    adjustment_amount: float
    adjustment_reason: str = ""
    is_recurring: bool = True
    
    @property
    def pct_change(self) -> float:
        """Calculate percent change"""
        if self.before_amount == 0:
            return 0.0
        return ((self.after_amount - self.before_amount) / abs(self.before_amount)) * 100


@dataclass
class NormalizedFinancialView:
    """Complete normalized financial view"""
    period: str
    period_end_date: str
    entity: str
    
    # Raw GL
    raw_gl: pd.DataFrame = field(default_factory=pd.DataFrame)
    
    # Classifications
    classifications: Dict[str, AccountClassification] = field(default_factory=dict)
    
    # Adjustments
    adjustments: List[AdjustmentDetail] = field(default_factory=list)
    adjustments_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    
    # Financial statements
    reported_income_statement: pd.DataFrame = field(default_factory=pd.DataFrame)
    normalized_income_statement: pd.DataFrame = field(default_factory=pd.DataFrame)
    
    # EBITDA metrics
    reported_ebitda: float = 0.0
    adjusted_ebitda: float = 0.0
    normalized_ebitda: float = 0.0
    
    # Details
    before_after_details: pd.DataFrame = field(default_factory=pd.DataFrame)
    adjustment_impact_analysis: pd.DataFrame = field(default_factory=pd.DataFrame)
    suspicious_patterns: List[Dict] = field(default_factory=list)
    eliminations: pd.DataFrame = field(default_factory=pd.DataFrame)


class NormalizedViewEngine:
    """Main engine for generating normalized views"""
    
    def __init__(self, config: NormalizedViewConfig = None):
        """Initialize with optional configuration"""
        self.config = config or NormalizedViewConfig()
        self.classifier = ClassificationEngine()
        self.calc_engine = AdjustmentCalculator()
        
        logger.info(f"NormalizedViewEngine initialized")
        logger.info(f"  - Industry: {self.config.industry or 'Generic'}")
        logger.info(f"  - Multi-entity consolidation: {self.config.consolidate_multi_entity}")
    
    def generate_view(self, 
                     gl_path: str,
                     adjustments_path: str = None,
                     entity_name: str = "Company",
                     period_end_date: str = None) -> NormalizedFinancialView:
        """
        Generate complete normalized financial view
        
        Args:
            gl_path: Path to GL data CSV
            adjustments_path: Optional path to adjustments CSV
            entity_name: Name of entity
            period_end_date: Period end date
        
        Returns:
            NormalizedFinancialView with all analyses
        """
        
        logger.info(f"Generating normalized view for {entity_name}...")
        
        # Load GL data
        gl_df = pd.read_csv(gl_path)
        logger.info(f"Loaded GL with {len(gl_df)} entries")
        
        # Multi-entity consolidation if needed
        if self.config.consolidate_multi_entity and 'Entity' in gl_df.columns:
            gl_df, eliminations = self._consolidate_entities(gl_df)
        else:
            eliminations = pd.DataFrame()
        
        # Classify accounts
        logger.info("Classifying accounts...")
        classifications = self._classify_accounts(gl_df)
        
        # Load adjustments
        adjustments = []
        adjustments_df = pd.DataFrame()
        if adjustments_path:
            adjustments, adjustments_df = self._load_adjustments(adjustments_path)
        
        # Build GL in calculator
        self.calc_engine.gl_data = gl_df
        self.calc_engine.adjustments = adjustments
        
        # Calculate EBITDA metrics
        logger.info("Calculating EBITDA metrics...")
        metrics = self.calc_engine.calculate_all_metrics()
        
        # Generate financial statements
        reported_is = self._generate_income_statement(gl_df, classifications, "Reported")
        
        if adjustments:
            normalized_is = self._generate_normalized_income_statement(
                gl_df, classifications, adjustments, "Normalized")
        else:
            normalized_is = reported_is.copy()
        
        # Generate before/after comparison
        before_after = self._generate_before_after(gl_df, classifications, adjustments)
        
        # Analyze suspicious patterns
        suspicious = self.classifier.detect_suspicious_patterns(gl_df)
        suspicious_dicts = [
            {
                'pattern': flag.pattern,
                'risk_level': flag.risk_level,
                'reason': flag.reason,
                'recommended_action': flag.recommended_action
            }
            for flag in suspicious
        ]
        
        # Build view
        view = NormalizedFinancialView(
            period=gl_df.get('Period', ['2024-12-31'])[0] if 'Period' in gl_df.columns else "2024-12-31",
            period_end_date=period_end_date or "2024-12-31",
            entity=entity_name,
            raw_gl=gl_df,
            classifications=classifications,
            adjustments=adjustments,
            adjustments_df=adjustments_df,
            reported_income_statement=reported_is,
            normalized_income_statement=normalized_is,
            reported_ebitda=metrics[EBITDAMetric.REPORTED_EBITDA].ebitda,
            adjusted_ebitda=metrics[EBITDAMetric.ADJUSTED_EBITDA].ebitda,
            normalized_ebitda=metrics[EBITDAMetric.NORMALIZED_EBITDA].ebitda,
            before_after_details=before_after,
            adjustment_impact_analysis=self.calc_engine.get_adjustment_impact_analysis(),
            suspicious_patterns=suspicious_dicts,
            eliminations=eliminations,
        )
        
        logger.info(f"✓ Generated normalized view")
        logger.info(f"  - Reported EBITDA: ${view.reported_ebitda:,.2f}")
        logger.info(f"  - Adjusted EBITDA: ${view.adjusted_ebitda:,.2f}")
        logger.info(f"  - Normalized EBITDA: ${view.normalized_ebitda:,.2f}")
        
        return view
    
    def _consolidate_entities(self, gl_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Consolidate multi-entity trial balance"""
        engine = ConsolidationEngine()
        
        for entity in gl_df['Entity'].unique():
            entity_data = gl_df[gl_df['Entity'] == entity]
            engine.add_entity(entity, entity_data)
        
        consolidated, eliminations = engine.consolidate()
        
        logger.info(f"Consolidated {len(gl_df['Entity'].unique())} entities, "
                   f"eliminated {len(eliminations)} intercompany entries")
        
        return consolidated, eliminations
    
    def _classify_accounts(self, gl_df: pd.DataFrame) -> Dict[str, AccountClassification]:
        """Classify all accounts"""
        classifications = {}
        
        for _, row in gl_df.iterrows():
            account_code = str(row.get('Account_Code', ''))
            account_name = str(row.get('Account_Name', ''))
            
            if account_code and account_name not in classifications:
                classification = self.classifier.classify_account(
                    account_code,
                    account_name,
                    self.config.industry
                )
                classifications[account_name] = classification
        
        logger.info(f"Classified {len(classifications)} unique accounts")
        
        return classifications
    
    def _load_adjustments(self, adjustments_path: str) -> Tuple[List[AdjustmentDetail], pd.DataFrame]:
        """Load adjustments from CSV"""
        adj_df = pd.read_csv(adjustments_path)
        logger.info(f"Loaded {len(adj_df)} adjustment entries")
        
        adjustments = []
        for _, row in adj_df.iterrows():
            try:
                # Try to parse from various column names
                amount = float(row.get('Amount') or row.get('Debit') or row.get('Credit') or 0)
                
                adj = AdjustmentDetail(
                    adjustment_id=str(row.get('Adjustment_ID') or row.get('Journal_Entry_ID') or 'ADJ'),
                    adjustment_name=str(row.get('Adjustment_Name') or row.get('Description') or 'Adjustment'),
                    adjustment_category=AdjustmentCategory(
                        str(row.get('Category') or row.get('Adjustment_Type') or 'add_back').lower()
                    ),
                    account_code=str(row.get('Account_Code') or ''),
                    account_name=str(row.get('Account_Name') or ''),
                    amount=amount,
                    reason=str(row.get('Reason') or ''),
                    is_recurring=row.get('Is_Recurring', True),
                )
                adjustments.append(adj)
            except Exception as e:
                logger.warning(f"Skipped adjustment row: {e}")
        
        return adjustments, adj_df
    
    def _generate_income_statement(self,
                                  gl_df: pd.DataFrame,
                                  classifications: Dict[str, AccountClassification],
                                  statement_type: str) -> pd.DataFrame:
        """Generate income statement from GL"""
        
        rows = []
        
        # Revenue
        revenue_accounts = gl_df[gl_df['Account_Name'].apply(
            lambda x: self.calc_engine.categorize_account(x) == 'revenue'
        )]
        revenue_total = abs(revenue_accounts['Amount'].sum())
        
        # COGS
        cogs_accounts = gl_df[gl_df['Account_Name'].apply(
            lambda x: self.calc_engine.categorize_account(x) == 'cogs'
        )]
        cogs_total = abs(cogs_accounts['Amount'].sum())
        
        # Gross Profit
        gross_profit = revenue_total - cogs_total
        
        # OpEx
        opex_accounts = gl_df[gl_df['Account_Name'].apply(
            lambda x: self.calc_engine.categorize_account(x) == 'opex'
        )]
        opex_total = abs(opex_accounts['Amount'].sum())
        
        # EBIT
        ebit = gross_profit - opex_total
        
        # D&A
        da_accounts = gl_df[gl_df['Account_Name'].apply(
            lambda x: self.calc_engine.categorize_account(x) == 'da'
        )]
        da_total = abs(da_accounts['Amount'].sum())
        
        # EBITDA
        ebitda = ebit + da_total
        
        # Build rows
        rows = [
            {'Line_Item': 'Revenue', 'Amount': revenue_total, 'Percent_of_Revenue': 100.0},
            {'Line_Item': 'COGS', 'Amount': -cogs_total, 'Percent_of_Revenue': -(cogs_total/revenue_total*100) if revenue_total > 0 else 0},
            {'Line_Item': 'Gross Profit', 'Amount': gross_profit, 'Percent_of_Revenue': (gross_profit/revenue_total*100) if revenue_total > 0 else 0},
            {'Line_Item': 'Operating Expenses', 'Amount': -opex_total, 'Percent_of_Revenue': -(opex_total/revenue_total*100) if revenue_total > 0 else 0},
            {'Line_Item': 'EBIT', 'Amount': ebit, 'Percent_of_Revenue': (ebit/revenue_total*100) if revenue_total > 0 else 0},
            {'Line_Item': 'Depreciation & Amortization', 'Amount': -da_total, 'Percent_of_Revenue': -(da_total/revenue_total*100) if revenue_total > 0 else 0},
            {'Line_Item': 'EBITDA', 'Amount': ebitda, 'Percent_of_Revenue': (ebitda/revenue_total*100) if revenue_total > 0 else 0},
        ]
        
        return pd.DataFrame(rows)
    
    def _generate_normalized_income_statement(self,
                                            gl_df: pd.DataFrame,
                                            classifications: Dict[str, AccountClassification],
                                            adjustments: List[AdjustmentDetail],
                                            statement_type: str) -> pd.DataFrame:
        """Generate normalized income statement with adjustments"""
        
        # Start with reported
        normalized_is = self._generate_income_statement(gl_df, classifications, statement_type)
        
        # Add adjustments row
        total_adjustments = sum(a.amount for a in adjustments if a.adjustment_category == AdjustmentCategory.ADDBACK)
        
        normalized_is = normalized_is.copy()
        
        # Calculate normalized EBITDA
        reported_ebitda = normalized_is[normalized_is['Line_Item'] == 'EBITDA']['Amount'].values[0]
        normalized_ebitda = reported_ebitda + total_adjustments
        
        # Update the EBITDA row
        normalized_is.loc[normalized_is['Line_Item'] == 'EBITDA', 'Amount'] = normalized_ebitda
        
        return normalized_is
    
    def _generate_before_after(self,
                              gl_df: pd.DataFrame,
                              classifications: Dict[str, AccountClassification],
                              adjustments: List[AdjustmentDetail]) -> pd.DataFrame:
        """Generate before/after comparison"""
        
        rows = []
        
        # Build before state (from GL)
        before_state = {}
        for _, row in gl_df.iterrows():
            account_name = str(row.get('Account_Name', ''))
            amount = float(row.get('Amount', 0))
            before_state[account_name] = before_state.get(account_name, 0) + amount
        
        # Build adjustment map
        adj_map = {}
        for adj in adjustments:
            if adj.account_name not in adj_map:
                adj_map[adj.account_name] = {'amount': 0, 'reason': ''}
            adj_map[adj.account_name]['amount'] += adj.amount
            adj_map[adj.account_name]['reason'] = adj.reason
        
        # Generate comparisons
        for account_name, before_amount in before_state.items():
            adjustment_amount = adj_map.get(account_name, {}).get('amount', 0)
            after_amount = before_amount + adjustment_amount
            
            account_code = ''
            account_type = ''
            classification = classifications.get(account_name)
            if classification:
                account_code = classification.account_code
                account_type = classification.account_type.value
            
            rows.append(BeforeAfterComparison(
                account_code=account_code,
                account_name=account_name,
                account_type=account_type,
                before_amount=before_amount,
                after_amount=after_amount,
                adjustment_amount=adjustment_amount,
                adjustment_reason=adj_map.get(account_name, {}).get('reason', ''),
            ))
        
        return pd.DataFrame([asdict(r) for r in rows])


class AdjustmentMemoGenerator:
    """Generate detailed adjustment memo from view"""
    
    @staticmethod
    def generate_memo(view: NormalizedFinancialView) -> str:
        """Generate detailed adjustment memo"""
        
        memo_lines = [
            "=" * 80,
            "ADJUSTMENT MEMORANDUM",
            "=" * 80,
            f"\nEntity: {view.entity}",
            f"Period End: {view.period_end_date}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "\n" + "=" * 80,
            "EXECUTIVE SUMMARY",
            "=" * 80,
            f"\nReported EBITDA:    ${view.reported_ebitda:>15,.2f}",
            f"Adjustments:        ${(view.adjusted_ebitda - view.reported_ebitda):>15,.2f}",
            f"Adjusted EBITDA:    ${view.adjusted_ebitda:>15,.2f}",
            f"Normalizations:     ${(view.normalized_ebitda - view.adjusted_ebitda):>15,.2f}",
            f"Normalized EBITDA:  ${view.normalized_ebitda:>15,.2f}",
            "\n" + "=" * 80,
            "DETAILED ADJUSTMENTS",
            "=" * 80,
        ]
        
        if not view.adjustments_df.empty:
            for idx, adj in view.adjustments_df.iterrows():
                memo_lines.append(f"\n[ADJ-{idx+1:02d}] {adj.get('Description') or adj.get('Adjustment_Name', 'Adjustment')}")
                memo_lines.append(f"  Category: {adj.get('Category') or adj.get('Adjustment_Type', 'Unknown')}")
                memo_lines.append(f"  Amount:   ${adj.get('Amount') or adj.get('Debit', 0):,.2f}")
                memo_lines.append(f"  Reason:   {adj.get('Reason', 'N/A')}")
        
        # Suspicious patterns
        if view.suspicious_patterns:
            memo_lines.append("\n" + "=" * 80)
            memo_lines.append("SUSPICIOUS PATTERNS & FLAGS")
            memo_lines.append("=" * 80)
            
            for pattern in view.suspicious_patterns:
                memo_lines.append(f"\n⚠ {pattern.get('pattern', 'Unknown')}")
                memo_lines.append(f"  Risk Level: {pattern.get('risk_level', 'Unknown')}")
                memo_lines.append(f"  Reason: {pattern.get('reason', 'N/A')}")
                memo_lines.append(f"  Action: {pattern.get('recommended_action', 'Review')}")
        
        memo_lines.extend([
            "\n" + "=" * 80,
            "END OF MEMO",
            "=" * 80,
        ])
        
        return "\n".join(memo_lines)


if __name__ == "__main__":
    # Example usage
    config = NormalizedViewConfig(
        include_intercompany_eliminations=True,
        apply_industry_normalization=False,
        consolidate_multi_entity=False
    )
    
    engine = NormalizedViewEngine(config)
    print("NormalizedViewEngine ready for use")
