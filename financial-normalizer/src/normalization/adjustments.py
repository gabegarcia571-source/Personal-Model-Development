"""
Adjustment Tracking and Calculation Module

Handles:
- Tracking of adjustments from raw GL
- Calculation of adjustment impacts
- EBITDA calculations (reported, adjusted, normalized)
- Intercompany eliminations
- Multi-currency consolidation
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, asdict, field
from enum import Enum
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AdjustmentCategory(Enum):
    """Classification of adjustment types"""
    ADDBACK = "add_back"
    ELIMINATE = "eliminate"
    NORMALIZE = "normalize"
    ACCRUAL_CONVERSION = "accrual_conversion"
    CURRENCY_TRANSLATION = "currency_translation"


class EBITDAMetric(Enum):
    """Types of EBITDA metrics calculated"""
    REPORTED_EBITDA = "reported_ebitda"  # From GAAP financials
    ADJUSTED_EBITDA = "adjusted_ebitda"  # GAAP + one-time adj
    NORMALIZED_EBITDA = "normalized_ebitda"  # Adjusted + normalization
    CASH_FLOW_EBITDA = "cash_flow_ebitda"  # Cash basis


@dataclass
class AdjustmentDetail:
    """Individual adjustment entry"""
    adjustment_id: str
    adjustment_name: str
    adjustment_category: AdjustmentCategory
    account_code: str
    account_name: str
    amount: float
    currency: str = "USD"
    is_recurring: bool = True
    reason: str = ""
    impact_metrics: List[str] = field(default_factory=list)
    source_doc: str = ""
    approved_by: str = ""
    effective_date: str = ""
    
    def __post_init__(self):
        if not self.accounting_impact:
            if self.amount > 0:
                self.accounting_impact = "debit"
            elif self.amount < 0:
                self.accounting_impact = "credit"


@dataclass
class GLEntry:
    """General ledger entry with account and amount"""
    account_code: str
    account_name: str
    amount: float
    currency: str = "USD"
    exchange_rate: float = 1.0
    entity: str = ""
    period: str = "2024-12-31"
    basis: str = "accrual"  # accrual or cash


@dataclass
class EBITDACalculation:
    """Complete EBITDA calculation with components"""
    metric_type: EBITDAMetric
    revenue: float = 0.0
    cogs: float = 0.0
    gross_profit: float = 0.0
    gross_margin_pct: float = 0.0
    opex: float = 0.0
    ebit: float = 0.0
    depreciation_amortization: float = 0.0
    ebitda: float = 0.0
    interest_and_taxes: float = 0.0
    net_income: float = 0.0
    adjustments_detail: Dict[str, float] = field(default_factory=dict)
    period: str = "2024-12-31"
    

class AdjustmentCalculator:
    """Calculate impacts of adjustments on financial metrics"""
    
    def __init__(self, gl_data: pd.DataFrame = None):
        """
        Initialize with GL data
        
        Args:
            gl_data: DataFrame with columns: Account_Code, Account_Name, Amount, etc.
        """
        self.gl_data = gl_data if gl_data is not None else pd.DataFrame()
        self.adjustments: List[AdjustmentDetail] = []
        self.ebitda_components = {
            'revenue': [],
            'cogs': [],
            'opex': [],
            'da': [],  # Depreciation & Amortization
            'interest': [],
            'taxes': [],
        }
    
    def add_adjustment(self, adjustment: AdjustmentDetail):
        """Add an adjustment to track"""
        self.adjustments.append(adjustment)
        logger.info(f"Added adjustment: {adjustment.adjustment_name} (${adjustment.amount:,.2f})")
    
    def add_adjustments_from_dataframe(self, 
                                      df: pd.DataFrame,
                                      category_col: str = 'Adjustment_Category',
                                      amount_col: str = 'Amount',
                                      account_code_col: str = 'Account_Code',
                                      account_name_col: str = 'Account_Name') -> int:
        """
        Load adjustments from DataFrame
        
        Returns:
            Number of adjustments added
        """
        added = 0
        for _, row in df.iterrows():
            try:
                adj = AdjustmentDetail(
                    adjustment_id=row.get('Adjustment_ID', f'ADJ-{added}'),
                    adjustment_name=row.get('Adjustment_Name', 'Unknown'),
                    adjustment_category=AdjustmentCategory(row.get(category_col, 'add_back')),
                    account_code=str(row.get(account_code_col)),
                    account_name=str(row.get(account_name_col)),
                    amount=float(row.get(amount_col, 0)),
                    reason=row.get('Reason', ''),
                    is_recurring=row.get('Is_Recurring', True),
                )
                self.add_adjustment(adj)
                added += 1
            except Exception as e:
                logger.warning(f"Failed to add adjustment from row: {e}")
                continue
        
        return added
    
    def categorize_account(self, account_name: str) -> Optional[str]:
        """Categorize account into EBITDA component"""
        name_lower = account_name.lower()
        
        if any(kw in name_lower for kw in ['revenue', 'sales', 'income']):
            return 'revenue'
        elif any(kw in name_lower for kw in ['cogs', 'cost of', 'cost of goods', 'cost of sales']):
            return 'cogs'
        elif any(kw in name_lower for kw in ['salary', 'wage', 'rent', 'utilities', 'marketing', 'administrative', 'office']):
            return 'opex'
        elif any(kw in name_lower for kw in ['depreciation', 'amortization', 'da&a']):
            return 'da'
        elif any(kw in name_lower for kw in ['interest', 'financing']):
            return 'interest'
        elif any(kw in name_lower for kw in ['income tax', 'tax expense']):
            return 'taxes'
        
        return None
    
    def parse_gl_data(self, 
                     account_code_col: str = 'Account_Code',
                     account_name_col: str = 'Account_Name',
                     amount_col: str = 'Amount') -> Dict[str, float]:
        """
        Parse GL data and categorize into EBITDA components
        
        Returns:
            Dict with categorized amounts: {revenue, cogs, opex, da, interest, taxes}
        """
        components = {k: 0.0 for k in self.ebitda_components.keys()}
        
        for _, row in self.gl_data.iterrows():
            account_name = str(row.get(account_name_col, ''))
            category = self.categorize_account(account_name)
            amount = float(row.get(amount_col, 0))
            
            if category and category in components:
                components[category] += amount
        
        return components
    
    def calculate_reported_ebitda(self) -> EBITDACalculation:
        """
        Calculate EBITDA from raw GL data (no adjustments)
        
        Returns:
            EBITDACalculation for reported financials
        """
        components = self.parse_gl_data()
        
        # For revenue, take absolute value and flip sign if negative (returns)
        revenue = abs(components.get('revenue', 0))
        cogs = abs(components.get('cogs', 0))
        opex = abs(components.get('opex', 0))
        da = abs(components.get('da', 0))
        interest = abs(components.get('interest', 0))
        
        gross_profit = revenue - cogs
        gross_margin_pct = (gross_profit / revenue * 100) if revenue > 0 else 0
        ebit = gross_profit - opex
        ebitda = ebit + da
        
        calc = EBITDACalculation(
            metric_type=EBITDAMetric.REPORTED_EBITDA,
            revenue=revenue,
            cogs=cogs,
            gross_profit=gross_profit,
            gross_margin_pct=gross_margin_pct,
            opex=opex,
            ebit=ebit,
            depreciation_amortization=da,
            ebitda=ebitda,
            interest_and_taxes=interest,
        )
        
        return calc
    
    def apply_adjustments(self, 
                         base_calc: EBITDACalculation,
                         adjustment_categories: Optional[Set[AdjustmentCategory]] = None) -> EBITDACalculation:
        """
        Apply adjustments to base EBITDA calculation
        
        Args:
            base_calc: Base EBITDA calculation (typically reported)
            adjustment_categories: Specific categories to apply (default: all)
        
        Returns:
            New EBITDACalculation with adjustments applied
        """
        # Filter adjustments
        active_adjs = self.adjustments
        if adjustment_categories:
            active_adjs = [a for a in self.adjustments 
                          if a.adjustment_category in adjustment_categories]
        
        # Calculate adjustment totals
        adj_revenue = 0.0
        adj_cogs = 0.0
        adj_opex = 0.0
        adj_da = 0.0
        
        adj_detail = {}
        
        for adj in active_adjs:
            account_category = self.categorize_account(adj.account_name)
            
            if adj.adjustment_category == AdjustmentCategory.ADDBACK:
                # Add-backs increase EBITDA
                if account_category == 'da':
                    adj_da += adj.amount
                elif account_category == 'opex':
                    adj_opex += adj.amount
                elif account_category == 'cogs':
                    adj_cogs += adj.amount
            
            elif adj.adjustment_category == AdjustmentCategory.ELIMINATE:
                # Eliminations remove from relevant categories
                if account_category == 'revenue':
                    adj_revenue -= adj.amount
                elif account_category == 'cogs':
                    adj_cogs -= adj.amount
                elif account_category == 'opex':
                    adj_opex -= adj.amount
            
            elif adj.adjustment_category == AdjustmentCategory.NORMALIZE:
                # Normalizations adjust to normalized level
                if account_category == 'opex':
                    adj_opex += adj.amount
                elif account_category == 'revenue':
                    adj_revenue += adj.amount
            
            adj_detail[adj.adjustment_name] = adj.amount
        
        # Calculate adjusted EBITDA
        adj_revenue_total = base_calc.revenue + adj_revenue
        adj_cogs_total = base_calc.cogs + adj_cogs
        adj_opex_total = base_calc.opex + adj_opex
        adj_da_total = base_calc.depreciation_amortization + adj_da
        
        adj_gross_profit = adj_revenue_total - adj_cogs_total
        adj_gross_margin = (adj_gross_profit / adj_revenue_total * 100) if adj_revenue_total > 0 else 0
        adj_ebit = adj_gross_profit - adj_opex_total
        adj_ebitda = adj_ebit + adj_da_total
        
        # Determine metric type
        if any(a.adjustment_category == AdjustmentCategory.NORMALIZE for a in active_adjs):
            metric_type = EBITDAMetric.NORMALIZED_EBITDA
        else:
            metric_type = EBITDAMetric.ADJUSTED_EBITDA
        
        calc = EBITDACalculation(
            metric_type=metric_type,
            revenue=adj_revenue_total,
            cogs=adj_cogs_total,
            gross_profit=adj_gross_profit,
            gross_margin_pct=adj_gross_margin,
            opex=adj_opex_total,
            ebit=adj_ebit,
            depreciation_amortization=adj_da_total,
            ebitda=adj_ebitda,
            adjustments_detail=adj_detail,
        )
        
        return calc
    
    def calculate_all_metrics(self) -> Dict[EBITDAMetric, EBITDACalculation]:
        """
        Calculate all EBITDA metrics: reported, adjusted, normalized
        
        Returns:
            Dict mapping metric types to calculations
        """
        metrics = {}
        
        # 1. Reported EBITDA
        reported = self.calculate_reported_ebitda()
        metrics[EBITDAMetric.REPORTED_EBITDA] = reported
        
        # 2. Adjusted EBITDA (non-recurring items)
        non_recurring = {AdjustmentCategory.ADDBACK, AdjustmentCategory.ELIMINATE}
        adjusted = self.apply_adjustments(reported, non_recurring)
        metrics[EBITDAMetric.ADJUSTED_EBITDA] = adjusted
        
        # 3. Normalized EBITDA (includes normalization)
        all_categories = set(AdjustmentCategory)
        normalized = self.apply_adjustments(reported, all_categories)
        metrics[EBITDAMetric.NORMALIZED_EBITDA] = normalized
        
        return metrics
    
    def get_summary(self) -> pd.DataFrame:
        """
        Generate summary of all EBITDA metrics
        
        Returns:
            DataFrame with rows for each metric
        """
        metrics = self.calculate_all_metrics()
        
        summary_rows = []
        for metric_type, calc in metrics.items():
            summary_rows.append({
                'Metric': metric_type.value,
                'Revenue': calc.revenue,
                'COGS': calc.cogs,
                'Gross_Profit': calc.gross_profit,
                'Gross_Margin_%': calc.gross_margin_pct,
                'OpEx': calc.opex,
                'EBIT': calc.ebit,
                'D&A': calc.depreciation_amortization,
                'EBITDA': calc.ebitda,
            })
        
        return pd.DataFrame(summary_rows)
    
    def get_adjustment_impact_analysis(self) -> pd.DataFrame:
        """
        Analyze impact of each adjustment on EBITDA
        
        Returns:
            DataFrame showing each adjustment and its impact
        """
        rows = []
        for adj in self.adjustments:
            impact = 0.0
            
            if adj.adjustment_category == AdjustmentCategory.ADDBACK:
                impact = adj.amount  # Positive impact (increases EBITDA)
            elif adj.adjustment_category == AdjustmentCategory.ELIMINATE:
                impact = -adj.amount  # Negative impact on stated EBITDA
            elif adj.adjustment_category == AdjustmentCategory.NORMALIZE:
                impact = adj.amount
            
            rows.append({
                'Adjustment_ID': adj.adjustment_id,
                'Adjustment_Name': adj.adjustment_name,
                'Category': adj.adjustment_category.value,
                'Amount': adj.amount,
                'EBITDA_Impact': impact,
                'Is_Recurring': adj.is_recurring,
                'Reason': adj.reason,
            })
        
        return pd.DataFrame(rows)


class ConsolidationEngine:
    """Handle multi-entity consolidations and eliminations"""
    
    def __init__(self):
        self.entities: Dict[str, pd.DataFrame] = {}
        self.intercompany_accounts: List[str] = [
            'intercompany receivable',
            'intercompany payable',
            'intercompany sale',
            'intercompany purchase',
        ]
    
    def add_entity(self, entity_name: str, entity_gl: pd.DataFrame):
        """Add entity to consolidation"""
        self.entities[entity_name] = entity_gl
        logger.info(f"Added entity '{entity_name}' with {len(entity_gl)} GL entries")
    
    def consolidate(self,
                   account_code_col: str = 'Account_Code',
                   account_name_col: str = 'Account_Name',
                   amount_col: str = 'Amount',
                   consolidation_type: str = 'full') -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Consolidate all entities with eliminations
        
        Args:
            consolidation_type: 'full' (with eliminations) or 'sum' (simple sum)
        
        Returns:
            (consolidated_gl, eliminations)
        """
        if not self.entities:
            return pd.DataFrame(), pd.DataFrame()
        
        # Combine all entities
        all_rows = []
        for entity_name, entity_df in self.entities.items():
            entity_df_copy = entity_df.copy()
            entity_df_copy['Entity'] = entity_name
            all_rows.append(entity_df_copy)
        
        combined = pd.concat(all_rows, ignore_index=True)
        
        if consolidation_type == 'sum':
            # Simple consolidation: sum amounts by account
            consolidated = combined.groupby([account_code_col, account_name_col])[amount_col].sum().reset_index()
            return consolidated, pd.DataFrame()
        
        # Full consolidation with elimination
        eliminations = self._identify_intercompany_eliminations(
            combined, account_code_col, account_name_col, amount_col)
        
        # Remove intercompany accounts
        consolidated = combined[~combined[account_name_col].str.lower().str.contains(
            '|'.join(self.intercompany_accounts), na=False)
        ].copy()
        
        # Aggregate by account
        consolidated = consolidated.groupby([account_code_col, account_name_col])[amount_col].sum().reset_index()
        
        return consolidated, eliminations
    
    def _identify_intercompany_eliminations(self,
                                            df: pd.DataFrame,
                                            account_code_col: str,
                                            account_name_col: str,
                                            amount_col: str) -> pd.DataFrame:
        """
        Identify intercompany transactions that should be eliminated
        
        Returns:
            DataFrame of elimination entries
        """
        elim_rows = []
        
        # Find intercompany receivables/payables
        ic_recs = df[df[account_name_col].str.lower().str.contains('intercompany receivable', na=False)]
        ic_pays = df[df[account_name_col].str.lower().str.contains('intercompany payable', na=False)]
        
        if not ic_recs.empty and not ic_pays.empty:
            rec_total = ic_recs[amount_col].sum()
            pay_total = ic_pays[amount_col].sum()
            
            if abs(rec_total + pay_total) < 1:  # Match within rounding
                elim_rows.append({
                    'Entry_Type': 'intercompany_elimination',
                    'Account_Eliminated': 'Intercompany Receivable/Payable',
                    'Amount_Eliminated': rec_total,
                    'Reason': 'Consolidated view - eliminate intercompany transactions'
                })
        
        return pd.DataFrame(elim_rows)


def consolidate_multi_entity_trial(
    trial_balance_path: str,
    entity_col: str = 'Entity',
    account_code_col: str = 'Account_Code',
    account_name_col: str = 'Account_Name',
    amount_col: str = 'Amount',
    output_path: str = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Consolidate a multi-entity trial balance with eliminations
    
    Returns:
        (consolidated_gl, eliminations)
    """
    df = pd.read_csv(trial_balance_path)
    logger.info(f"Loaded trial balance with {len(df)} entries")
    
    engine = ConsolidationEngine()
    
    # Add each entity
    for entity in df[entity_col].unique():
        entity_df = df[df[entity_col] == entity]
        engine.add_entity(entity, entity_df)
    
    consolidated, eliminations = engine.consolidate(
        account_code_col, account_name_col, amount_col, 'full')
    
    if output_path:
        consolidated.to_csv(f"{output_path}_consolidated.csv", index=False)
        if not eliminations.empty:
            eliminations.to_csv(f"{output_path}_eliminations.csv", index=False)
        logger.info(f"Saved consolidated output to {output_path}")
    
    return consolidated, eliminations


if __name__ == "__main__":
    # Example usage
    calc = AdjustmentCalculator()
    
    # Add sample adjustments
    adj1 = AdjustmentDetail(
        adjustment_id="ADJ-001",
        adjustment_name="Stock-Based Compensation",
        adjustment_category=AdjustmentCategory.ADDBACK,
        account_code="6000",
        account_name="Salaries & Wages",
        amount=50000,
        reason="Non-cash expense"
    )
    
    adj2 = AdjustmentDetail(
        adjustment_id="ADJ-002",
        adjustment_name="Depreciation Addback",
        adjustment_category=AdjustmentCategory.ADDBACK,
        account_code="6200",
        account_name="Depreciation Expense",
        amount=75000,
        reason="Non-cash expense"
    )
    
    calc.add_adjustment(adj1)
    calc.add_adjustment(adj2)
    
    print("Adjustment Summary:")
    print(calc.get_adjustment_impact_analysis())
