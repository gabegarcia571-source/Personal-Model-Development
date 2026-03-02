"""
Financial Metrics Engine

Sits at the end of the normalization pipeline. Takes the output of NormalizedViewEngine
(a NormalizedFinancialView object) and calculates financial ratios and metrics.

Input:
  - NormalizedFinancialView from NormalizedViewEngine.generate_view()

Metrics Calculated:
  - Profitability: gross margin, EBITDA margin, operating margin, net margin
  - Financial Health: current ratio, debt to EBITDA, interest coverage
  - Valuation: EV/EBITDA, EV/Revenue (requires optional enterprise value input)

Enterprise value must be provided by the user as it cannot be derived from 
financial statements alone. All other metrics are calculated from available
GL data and income statement.

Returns:
  - None for any metric where required data is unavailable
  - Percentages for margin metrics (not decimals)
  - Rounded to 2 decimal places
"""

from typing import Optional, Dict, Any
from normalization.engine import NormalizedFinancialView
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FinancialMetricsEngine:
    """Calculate financial metrics from a normalized view"""
    
    def __init__(self, view: NormalizedFinancialView, enterprise_value: Optional[float] = None):
        """
        Initialize with a normalized financial view.
        
        Args:
            view: NormalizedFinancialView from NormalizedViewEngine
            enterprise_value: Optional enterprise value for valuation metrics
        """
        self.view = view
        self.enterprise_value = enterprise_value
        
        logger.info(f"FinancialMetricsEngine initialized for {view.entity}")
    
    # =====================================================================
    # PROFITABILITY METRICS
    # =====================================================================
    
    def gross_margin(self) -> Optional[float]:
        """
        Calculate gross profit margin as a percentage.
        
        Formula: (Gross Profit / Revenue) * 100
        
        Returns:
            Gross margin as percentage, or None if data unavailable
        """
        try:
            if self.view.normalized_income_statement.empty:
                return None
            
            is_df = self.view.normalized_income_statement
            
            # Extract revenue and gross profit from income statement
            revenue_row = is_df[is_df['Line_Item'] == 'Revenue']
            gp_row = is_df[is_df['Line_Item'] == 'Gross Profit']
            
            if revenue_row.empty or gp_row.empty:
                return None
            
            revenue = float(revenue_row['Amount'].values[0])
            gross_profit = float(gp_row['Amount'].values[0])
            
            if revenue <= 0:
                return None
            
            margin = (gross_profit / revenue) * 100
            return round(margin, 2)
        
        except Exception as e:
            logger.debug(f"Could not calculate gross margin: {e}")
            return None
    
    def ebitda_margin(self) -> Optional[float]:
        """
        Calculate EBITDA margin as a percentage.
        
        Formula: (Normalized EBITDA / Revenue) * 100
        
        Returns:
            EBITDA margin as percentage, or None if data unavailable
        """
        try:
            if self.view.normalized_income_statement.empty:
                return None
            
            is_df = self.view.normalized_income_statement
            
            # Extract revenue
            revenue_row = is_df[is_df['Line_Item'] == 'Revenue']
            if revenue_row.empty:
                return None
            
            revenue = float(revenue_row['Amount'].values[0])
            ebitda = self.view.normalized_ebitda
            
            if revenue <= 0:
                return None
            
            margin = (ebitda / revenue) * 100
            return round(margin, 2)
        
        except Exception as e:
            logger.debug(f"Could not calculate EBITDA margin: {e}")
            return None
    
    def operating_margin(self) -> Optional[float]:
        """
        Calculate operating margin (EBIT margin) as a percentage.
        
        Formula: (Operating Income / Revenue) * 100
        
        Returns:
            Operating margin as percentage, or None if data unavailable
        """
        try:
            if self.view.normalized_income_statement.empty:
                return None
            
            is_df = self.view.normalized_income_statement
            
            # Extract revenue and EBIT
            revenue_row = is_df[is_df['Line_Item'] == 'Revenue']
            ebit_row = is_df[is_df['Line_Item'] == 'EBIT']
            
            if revenue_row.empty or ebit_row.empty:
                return None
            
            revenue = float(revenue_row['Amount'].values[0])
            ebit = float(ebit_row['Amount'].values[0])
            
            if revenue <= 0:
                return None
            
            margin = (ebit / revenue) * 100
            return round(margin, 2)
        
        except Exception as e:
            logger.debug(f"Could not calculate operating margin: {e}")
            return None
    
    def net_margin(self) -> Optional[float]:
        """
        Calculate net profit margin as a percentage.
        
        Formula: (Net Income / Revenue) * 100
        
        Returns:
            Net margin as percentage, or None if data unavailable
        """
        try:
            net_income = self._extract_net_income()
            if net_income is None:
                return None
            
            revenue = self._extract_revenue()
            if revenue is None or revenue <= 0:
                return None
            
            margin = (net_income / revenue) * 100
            return round(margin, 2)
        
        except Exception as e:
            logger.debug(f"Could not calculate net margin: {e}")
            return None
    
    # =====================================================================
    # FINANCIAL HEALTH METRICS
    # =====================================================================
    
    def current_ratio(self) -> Optional[float]:
        """
        Calculate current ratio (liquidity metric).
        
        Formula: Current Assets / Current Liabilities
        
        Returns:
            Current ratio, or None if data unavailable
        """
        try:
            current_assets = self._extract_current_assets()
            current_liabilities = self._extract_current_liabilities()
            
            if current_assets is None or current_liabilities is None:
                return None
            
            if current_liabilities <= 0:
                return None
            
            ratio = current_assets / current_liabilities
            return round(ratio, 2)
        
        except Exception as e:
            logger.debug(f"Could not calculate current ratio: {e}")
            return None
    
    def debt_to_ebitda(self) -> Optional[float]:
        """
        Calculate debt to EBITDA ratio (leverage metric).
        
        Formula: Total Debt / Normalized EBITDA
        
        Returns:
            Debt to EBITDA ratio, or None if data unavailable
        """
        try:
            total_debt = self._extract_total_debt()
            if total_debt is None:
                return None
            
            ebitda = self.view.normalized_ebitda
            if ebitda is None or ebitda <= 0:
                return None
            
            ratio = total_debt / ebitda
            return round(ratio, 2)
        
        except Exception as e:
            logger.debug(f"Could not calculate debt to EBITDA: {e}")
            return None
    
    def interest_coverage_ratio(self) -> Optional[float]:
        """
        Calculate interest coverage ratio (solvency metric).
        
        Formula: EBITDA / Interest Expense
        
        Returns:
            Interest coverage ratio, or None if data unavailable
        """
        try:
            ebitda = self.view.normalized_ebitda
            if ebitda is None:
                return None
            
            interest_expense = self._extract_interest_expense()
            if interest_expense is None or interest_expense <= 0:
                return None
            
            ratio = ebitda / interest_expense
            return round(ratio, 2)
        
        except Exception as e:
            logger.debug(f"Could not calculate interest coverage ratio: {e}")
            return None
    
    # =====================================================================
    # VALUATION METRICS
    # =====================================================================
    
    def ev_to_ebitda(self) -> Optional[float]:
        """
        Calculate EV/EBITDA multiple.
        
        Formula: Enterprise Value / Normalized EBITDA
        
        Requires enterprise_value to be provided at initialization.
        
        Returns:
            EV/EBITDA multiple, or None if data unavailable
        """
        try:
            if self.enterprise_value is None:
                return None
            
            ebitda = self.view.normalized_ebitda
            if ebitda is None or ebitda <= 0:
                return None
            
            multiple = self.enterprise_value / ebitda
            return round(multiple, 2)
        
        except Exception as e:
            logger.debug(f"Could not calculate EV/EBITDA: {e}")
            return None
    
    def ev_to_revenue(self) -> Optional[float]:
        """
        Calculate EV/Revenue multiple.
        
        Formula: Enterprise Value / Revenue
        
        Requires enterprise_value to be provided at initialization.
        
        Returns:
            EV/Revenue multiple, or None if data unavailable
        """
        try:
            if self.enterprise_value is None:
                return None
            
            revenue = self._extract_revenue()
            if revenue is None or revenue <= 0:
                return None
            
            multiple = self.enterprise_value / revenue
            return round(multiple, 2)
        
        except Exception as e:
            logger.debug(f"Could not calculate EV/Revenue: {e}")
            return None
    
    # =====================================================================
    # REPORTING
    # =====================================================================
    
    def get_full_report(self) -> Dict[str, Any]:
        """
        Generate complete metrics report organized by category.
        
        Returns:
            Dict with three sections: profitability, health, valuation
            Each metric is included with its value (or None if unavailable)
        """
        return {
            'profitability': {
                'gross_margin_%': self.gross_margin(),
                'ebitda_margin_%': self.ebitda_margin(),
                'operating_margin_%': self.operating_margin(),
                'net_margin_%': self.net_margin(),
            },
            'health': {
                'current_ratio': self.current_ratio(),
                'debt_to_ebitda': self.debt_to_ebitda(),
                'interest_coverage_ratio': self.interest_coverage_ratio(),
            },
            'valuation': {
                'ev_to_ebitda': self.ev_to_ebitda(),
                'ev_to_revenue': self.ev_to_revenue(),
            },
        }
    
    # =====================================================================
    # HELPER METHODS (extract data from view)
    # =====================================================================
    
    def _extract_revenue(self) -> Optional[float]:
        """Extract revenue from income statement"""
        try:
            if self.view.normalized_income_statement.empty:
                return None
            
            is_df = self.view.normalized_income_statement
            revenue_row = is_df[is_df['Line_Item'] == 'Revenue']
            
            if revenue_row.empty:
                return None
            
            revenue = float(revenue_row['Amount'].values[0])
            return revenue if revenue > 0 else None
        
        except Exception as e:
            logger.debug(f"Could not extract revenue: {e}")
            return None
    
    def _extract_net_income(self) -> Optional[float]:
        """
        Extract or calculate net income.
        
        Tries to find in income statement first, otherwise calculates from GL.
        """
        try:
            if not self.view.normalized_income_statement.empty:
                is_df = self.view.normalized_income_statement
                ni_row = is_df[is_df['Line_Item'] == 'Net Income']
                if not ni_row.empty:
                    return float(ni_row['Amount'].values[0])
            
            # Fallback: try to extract net income from GL
            # Net Income = EBITDA - D&A - Interest - Taxes
            if self.view.raw_gl.empty:
                return None
            
            gl_df = self.view.raw_gl
            
            # Try to find by account name keywords
            taxes = 0.0
            tax_rows = gl_df[gl_df['Account_Name'].str.lower().str.contains('tax', na=False)]
            if not tax_rows.empty:
                taxes = abs(tax_rows['Amount'].sum())
            
            ebitda = self.view.normalized_ebitda
            
            # Extract D&A from income statement
            da = 0.0
            if not self.view.normalized_income_statement.empty:
                is_df = self.view.normalized_income_statement
                da_row = is_df[is_df['Line_Item'] == 'Depreciation & Amortization']
                if not da_row.empty:
                    da = abs(float(da_row['Amount'].values[0]))
            
            # Extract interest from GL
            interest = self._extract_interest_expense()
            if interest is None:
                interest = 0.0
            
            net_income = ebitda - da - interest - taxes
            return net_income
        
        except Exception as e:
            logger.debug(f"Could not extract net income: {e}")
            return None
    
    def _extract_current_assets(self) -> Optional[float]:
        """Extract current assets from GL"""
        try:
            if self.view.raw_gl.empty:
                return None
            
            gl_df = self.view.raw_gl
            
            # Match current asset accounts
            current_asset_keywords = [
                'cash', 'receivable', 'inventory', 'prepaid', 'current asset'
            ]
            
            current_assets = gl_df[
                gl_df['Account_Name'].str.lower().str.contains(
                    '|'.join(current_asset_keywords), na=False
                )
            ]
            
            if current_assets.empty:
                return None
            
            total = current_assets['Amount'].sum()
            return total if total > 0 else None
        
        except Exception as e:
            logger.debug(f"Could not extract current assets: {e}")
            return None
    
    def _extract_current_liabilities(self) -> Optional[float]:
        """Extract current liabilities from GL"""
        try:
            if self.view.raw_gl.empty:
                return None
            
            gl_df = self.view.raw_gl
            
            # Match current liability accounts
            current_liability_keywords = [
                'payable', 'accrued', 'current liability', 'short term'
            ]
            
            current_liabilities = gl_df[
                gl_df['Account_Name'].str.lower().str.contains(
                    '|'.join(current_liability_keywords), na=False
                )
            ]
            
            if current_liabilities.empty:
                return None
            
            total = abs(current_liabilities['Amount'].sum())
            return total if total > 0 else None
        
        except Exception as e:
            logger.debug(f"Could not extract current liabilities: {e}")
            return None
    
    def _extract_total_debt(self) -> Optional[float]:
        """Extract total debt from GL"""
        try:
            if self.view.raw_gl.empty:
                return None
            
            gl_df = self.view.raw_gl
            
            # Match debt accounts (loans, bonds, etc.)
            debt_keywords = ['debt', 'loan', 'bond', 'notes payable', 'term loan']
            
            debt_accounts = gl_df[
                gl_df['Account_Name'].str.lower().str.contains(
                    '|'.join(debt_keywords), na=False
                )
            ]
            
            if debt_accounts.empty:
                return None
            
            total = abs(debt_accounts['Amount'].sum())
            return total if total > 0 else None
        
        except Exception as e:
            logger.debug(f"Could not extract total debt: {e}")
            return None
    
    def _extract_interest_expense(self) -> Optional[float]:
        """Extract interest expense from GL"""
        try:
            if self.view.raw_gl.empty:
                return None
            
            gl_df = self.view.raw_gl
            
            # Match interest accounts
            interest_keywords = ['interest', 'financing']
            
            interest_accounts = gl_df[
                gl_df['Account_Name'].str.lower().str.contains(
                    '|'.join(interest_keywords), na=False
                )
            ]
            
            if interest_accounts.empty:
                return None
            
            total = abs(interest_accounts['Amount'].sum())
            return total if total > 0 else None
        
        except Exception as e:
            logger.debug(f"Could not extract interest expense: {e}")
            return None
