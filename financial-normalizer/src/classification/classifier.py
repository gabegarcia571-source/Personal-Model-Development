"""
Account Classification Engine

Classifies accounts for normalization purposes:
- Maps accounts to account types (revenue, cogs, opex, etc.)
- Detects adjustment candidates
- Flags suspicious patterns
"""

import pandas as pd
import yaml
import logging
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AccountType(Enum):
    """Standard account types"""
    REVENUE = "revenue"
    RETURNS = "returns"
    COGS = "cogs"
    OPEX = "opex"
    DEPRECIATION = "depreciation"
    INTEREST = "interest"
    OTHER_INCOME = "other_income"
    OTHER_EXPENSE = "other_expense"
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    UNKNOWN = "unknown"


class AdjustmentType(Enum):
    """Types of adjustments for normalization"""
    ADD_BACK = "add_back"
    ELIMINATE = "eliminate"
    NORMALIZE = "normalize"
    ACCRUAL_CONVERSION = "accrual_conversion"


@dataclass
class SuspiciousPatternFlag:
    """Flag for suspicious accounting patterns"""
    account_name: str
    pattern: str
    risk_level: str  # low, medium, high
    reason: str
    threshold_exceeded: Optional[float] = None
    recommended_action: str = "Review"


@dataclass
class AccountClassification:
    """Classification result for an account"""
    account_code: str
    account_name: str
    account_type: AccountType
    adjustment_type: Optional[AdjustmentType] = None
    adjustment_name: Optional[str] = None
    adjustment_reason: Optional[str] = None
    is_recurring: Optional[bool] = None
    industry: Optional[str] = None
    metrics: List[str] = None
    suspicious_flags: List[SuspiciousPatternFlag] = None
    
    def __post_init__(self):
        if self.metrics is None:
            self.metrics = []
        if self.suspicious_flags is None:
            self.suspicious_flags = []


class ClassificationEngine:
    """Main engine for account classification and pattern detection"""
    
    def __init__(self, config_path: str = None):
        """Initialize with classification rules from YAML config"""
        if config_path is None:
            config_path = "/workspaces/Personal-Model-Development/financial-normalizer/config/categories.yaml"
        
        self.config_path = config_path
        self.config = self._load_config()
        self.keyword_index = self._build_keyword_index()
        self.suspicious_rules = self._extract_suspicious_patterns()
    
    def _load_config(self) -> Dict:
        """Load classification rules from YAML"""
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        logger.info(f"Loaded classification config from {self.config_path}")
        return config
    
    def _build_keyword_index(self) -> Dict[str, List[str]]:
        """Build index of keywords to adjustment mappings"""
        index = {}
        
        if 'adjustments' in self.config:
            for adj_name, adj_config in self.config['adjustments'].items():
                for keyword in adj_config.get('keywords', []):
                    keyword_lower = keyword.lower()
                    if keyword_lower not in index:
                        index[keyword_lower] = []
                    index[keyword_lower].append(adj_name)
        
        return index
    
    def _extract_suspicious_patterns(self) -> Dict[str, Dict]:
        """Extract suspicious pattern rules from config"""
        patterns = {}
        
        if 'suspicious_patterns' in self.config:
            for pattern_name, pattern_config in self.config['suspicious_patterns'].items():
                patterns[pattern_name] = pattern_config
        
        return patterns
    
    def classify_account(self, 
                        account_code: str, 
                        account_name: str,
                        industry: str = None) -> AccountClassification:
        """
        Classify a single account
        
        Args:
            account_code: Chart of accounts code
            account_name: Human-readable account name
            industry: Optional industry context (saas_tech, manufacturing, etc.)
        
        Returns:
            AccountClassification with account type and adjustment info
        """
        account_name_lower = account_name.lower()
        account_code_lower = str(account_code).lower()
        
        # Initialize classification
        classification = AccountClassification(
            account_code=str(account_code),
            account_name=account_name,
            account_type=AccountType.UNKNOWN,
            industry=industry
        )
        
        # 1. Check industry-specific mappings first
        if industry and industry in self.config:
            classification = self._classify_by_industry(classification, industry)
            if classification.account_type != AccountType.UNKNOWN:
                return classification
        
        # 2. Check general account classification by keywords
        classification.account_type = self._classify_by_keywords(account_name_lower)
        
        # 3. Check for adjustments that might apply
        adj = self._find_applicable_adjustment(account_name_lower, account_code_lower)
        if adj:
            adj_name, adj_config = adj
            classification.adjustment_type = AdjustmentType(adj_config['adjustment_type'])
            classification.adjustment_name = adj_name
            classification.adjustment_reason = adj_config.get('reason')
            classification.is_recurring = adj_config.get('is_recurring', True)
        
        return classification
    
    def _classify_by_industry(self, 
                              classification: AccountClassification,
                              industry: str) -> AccountClassification:
        """Classify using industry-specific rules"""
        industry_config = self.config.get(industry, {})
        
        # Check revenue accounts
        for account_code, account_config in industry_config.get('revenue_accounts', {}).items():
            if (str(classification.account_code) == str(account_code) or
                account_code in classification.account_name.lower()):
                classification.account_type = AccountType.REVENUE
                classification.metrics = account_config.get('metrics', [])
                return classification
        
        # Check COGS accounts
        for account_code, account_config in industry_config.get('cogs_accounts', {}).items():
            if (str(classification.account_code) == str(account_code) or
                account_code in classification.account_name.lower()):
                if account_config.get('is_depreciation'):
                    classification.account_type = AccountType.DEPRECIATION
                else:
                    classification.account_type = AccountType.COGS
                    classification.metrics = [account_config.get('sublevel')] if 'sublevel' in account_config else []
                return classification
        
        # Check opex
        for account_code, account_config in industry_config.get('operating_expenses', {}).items():
            if (str(classification.account_code) == str(account_code) or
                account_code in classification.account_name.lower()):
                classification.account_type = AccountType.OPEX
                return classification
        
        return classification
    
    def _classify_by_keywords(self, account_name_lower: str) -> AccountType:
        """Classify account by keyword matching"""
        
        if any(keyword in account_name_lower for keyword in 
               ['revenue', 'sales', 'income', 'subscription']):
            return AccountType.REVENUE
        
        if any(keyword in account_name_lower for keyword in 
               ['return', 'allowance', 'rebate', 'refund']):
            return AccountType.RETURNS
        
        if any(keyword in account_name_lower for keyword in 
               ['cogs', 'cost of goods', 'cost of sales', 'cost of revenue']):
            return AccountType.COGS
        
        if any(keyword in account_name_lower for keyword in 
               ['salary', 'wage', 'rent', 'utilities', 'marketing', 'advertising', 
                'depreciation', 'expense', 'administrative']):
            if 'depreciation' in account_name_lower or 'amortization' in account_name_lower:
                return AccountType.DEPRECIATION
            return AccountType.OPEX
        
        if any(keyword in account_name_lower for keyword in 
               ['interest', 'financing', 'loan']):
            return AccountType.INTEREST
        
        if any(keyword in account_name_lower for keyword in 
               ['gain', 'loss', 'other income', 'other expense', 'fx']):
            return AccountType.OTHER_EXPENSE
        
        if any(keyword in account_name_lower for keyword in 
               ['cash', 'receivable', 'inventory', 'prepaid', 'property', 
                'equipment', 'asset']):
            return AccountType.ASSET
        
        if any(keyword in account_name_lower for keyword in 
               ['payable', 'liability', 'debt', 'accrued']):
            return AccountType.LIABILITY
        
        if any(keyword in account_name_lower for keyword in 
               ['stock', 'equity', 'retained earnings', 'capital']):
            return AccountType.EQUITY
        
        return AccountType.UNKNOWN
    
    def _find_applicable_adjustment(self, account_name_lower: str, 
                                   account_code_lower: str) -> Optional[Tuple[str, Dict]]:
        """Find adjustment rule that applies to this account"""
        
        best_match = None
        max_keywords = 0
        
        if 'adjustments' not in self.config:
            return None
        
        for adj_name, adj_config in self.config['adjustments'].items():
            keywords = adj_config.get('keywords', [])
            match_count = sum(1 for kw in keywords 
                            if kw.lower() in account_name_lower)
            
            if match_count > max_keywords:
                max_keywords = match_count
                best_match = (adj_name, adj_config)
        
        return best_match if max_keywords > 0 else None
    
    def detect_suspicious_patterns(self, 
                                   df: pd.DataFrame,
                                   account_col: str = 'Account_Name',
                                   amount_col: str = 'Amount') -> List[SuspiciousPatternFlag]:
        """
        Detect suspicious accounting patterns in the dataset
        
        Args:
            df: DataFrame with account data
            account_col: Column name for account names
            amount_col: Column name for amounts
        
        Returns:
            List of suspicious pattern flags
        """
        flags = []
        
        # Check for negative revenue
        revenue_rows = df[df[account_col].str.contains('revenue|sales', 
                                                        case=False, 
                                                        na=False)]
        
        negative_revenue = revenue_rows[revenue_rows[amount_col] < 0]
        if not negative_revenue.empty:
            total_negative = negative_revenue[amount_col].sum()
            total_revenue = revenue_rows[amount_col].sum()
            if abs(total_revenue) > 0 and abs(total_negative / total_revenue) > 0.05:
                flags.append(SuspiciousPatternFlag(
                    account_name="Revenue",
                    pattern="negative_revenue",
                    risk_level="medium",
                    reason=f"Negative revenue {total_negative:,.2f} is {abs(total_negative/total_revenue)*100:.1f}% of total",
                    threshold_exceeded=abs(total_negative / total_revenue),
                    recommended_action="Review returns and allowances"
                ))
        
        # Check for round numbers (potential estimates)
        if amount_col in df.columns:
            large_amounts = df[df[amount_col].abs() > 100000].copy()
            large_amounts['is_round'] = (large_amounts[amount_col] % 10000 == 0)
            
            round_count = large_amounts['is_round'].sum()
            if len(large_amounts) > 0 and round_count / len(large_amounts) > 0.3:
                flags.append(SuspiciousPatternFlag(
                    account_name="Various",
                    pattern="large_round_amount",
                    risk_level="low",
                    reason=f"{round_count} out of {len(large_amounts)} large amounts are round numbers",
                    threshold_exceeded=round_count / len(large_amounts),
                    recommended_action="Verify round amounts are not estimates"
                ))
        
        # Check for related party transactions
        related_party_rows = df[df[account_col].str.contains(
            'related|affiliate|intercompany|parent|subsidiary',
            case=False,
            na=False
        )]
        
        if not related_party_rows.empty:
            total_amount = related_party_rows[amount_col].abs().sum()
            flags.append(SuspiciousPatternFlag(
                account_name="Related Party Transactions",
                pattern="related_party_spike",
                risk_level="medium",
                reason=f"Found {len(related_party_rows)} related party entries totaling {total_amount:,.2f}",
                recommended_action="Review related party transactions for arm's length pricing"
            ))
        
        return flags
    
    def classify_dataframe(self, 
                          df: pd.DataFrame,
                          account_code_col: str = 'Account_Code',
                          account_name_col: str = 'Account_Name',
                          industry: str = None) -> pd.DataFrame:
        """
        Classify all accounts in a DataFrame
        
        Returns DataFrame with added classification columns
        """
        classifications = []
        
        for _, row in df.iterrows():
            account_code = row.get(account_code_col)
            account_name = row.get(account_name_col)
            
            if pd.isna(account_code) or pd.isna(account_name):
                continue
            
            classification = self.classify_account(str(account_code), 
                                                   str(account_name),
                                                   industry)
            classifications.append(classification)
        
        # Build result DataFrame
        result = []
        for cls in classifications:
            result.append({
                'Account_Code': cls.account_code,
                'Account_Name': cls.account_name,
                'Account_Type': cls.account_type.value,
                'Adjustment_Type': cls.adjustment_type.value if cls.adjustment_type else None,
                'Adjustment_Name': cls.adjustment_name,
                'Adjustment_Reason': cls.adjustment_reason,
                'Is_Recurring': cls.is_recurring,
            })
        
        result_df = pd.DataFrame(result)
        
        # Merge with original
        if len(result_df) > 0:
            result_df = df.merge(result_df, 
                                left_on=[account_code_col, account_name_col],
                                right_on=['Account_Code', 'Account_Name'],
                                how='left')
        
        return result_df


def classify_transaction_dataset(input_path: str, 
                                 output_path: str,
                                 industry: str = None) -> Tuple[pd.DataFrame, List[SuspiciousPatternFlag]]:
    """
    Classify all accounts in a transaction dataset and detect suspicious patterns
    
    Args:
        input_path: Path to input CSV
        output_path: Path to save classified output
        industry: Optional industry for context
    
    Returns:
        (classified_df, suspicious_flags)
    """
    
    # Load data
    df = pd.read_csv(input_path)
    logger.info(f"Loaded {len(df)} transactions from {input_path}")
    
    # Initialize classifier
    classifier = ClassificationEngine()
    
    # Classify all accounts
    df_classified = classifier.classify_dataframe(df, industry=industry)
    
    # Detect suspicious patterns
    flags = classifier.detect_suspicious_patterns(df)
    
    # Save classified output
    df_classified.to_csv(output_path, index=False)
    logger.info(f"Saved classified transactions to {output_path}")
    
    # Log suspicious patterns
    if flags:
        logger.warning(f"Found {len(flags)} suspicious patterns:")
        for flag in flags:
            logger.warning(f"  - {flag.pattern}: {flag.reason} ({flag.risk_level})")
    
    return df_classified, flags


if __name__ == "__main__":
    # Example usage
    classifier = ClassificationEngine()
    
    # Test classifications
    test_accounts = [
        ("4000", "Product Revenue"),
        ("5000", "Cost of Goods Sold"),
        ("6000", "Salaries & Wages"),
        ("7000", "Interest Expense"),
        ("1100", "Accounts Receivable"),
        ("REV-RETURNS", "Sales Returns & Allowances"),
    ]
    
    print("Sample Classifications:\n")
    for code, name in test_accounts:
        result = classifier.classify_account(code, name)
        print(f"{code} - {name}")
        print(f"  Type: {result.account_type.value}")
        print(f"  Adjustment: {result.adjustment_name} ({result.adjustment_type.value if result.adjustment_type else 'None'})")
        print()
