"""
Synthetic Trial Balance Generators for Testing Edge Cases
- Multi-entity consolidations
- Different account numbering schemes (4-digit, 5-digit, alphanumeric)
- Foreign currency
- Negative revenue (returns)
- Intercompany eliminations
- Mixed cash/accrual basis
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple
from enum import Enum


class AccountScheme(Enum):
    """Different account numbering schemes"""
    FOUR_DIGIT = "4-digit"  # 1000, 2000, 3000
    FIVE_DIGIT = "5-digit"  # 10000, 20000, 30000
    ALPHANUMERIC = "alphanumeric"  # REV-001, COGS-001, GA-001


class Currency(Enum):
    """Supported currencies for multi-currency trials"""
    USD = ("USD", 1.0)
    EUR = ("EUR", 1.10)
    GBP = ("GBP", 1.27)
    CAD = ("CAD", 0.74)
    MXN = ("MXN", 0.058)


class SyntheticAccountGenerator:
    """Generate realistic trial balance entries with various schemes"""
    
    def __init__(self, account_scheme: AccountScheme = AccountScheme.FOUR_DIGIT):
        self.scheme = account_scheme
        self._setup_chart_of_accounts()
    
    def _setup_chart_of_accounts(self):
        """Setup chart of accounts based on naming scheme"""
        if self.scheme == AccountScheme.FOUR_DIGIT:
            self.coa = {
                # Assets
                "1000": "Cash and Cash Equivalents",
                "1100": "Accounts Receivable",
                "1150": "Allowance for Doubtful Accounts",
                "1200": "Inventory",
                "1300": "Prepaid Expenses",
                "1500": "Property, Plant & Equipment",
                "1600": "Accumulated Depreciation",
                
                # Liabilities
                "2000": "Accounts Payable",
                "2100": "Accrued Expenses",
                "2200": "Short-term Debt",
                "2300": "Current Portion LT Debt",
                "2500": "Long-term Debt",
                
                # Equity
                "3000": "Common Stock",
                "3100": "Additional Paid-in Capital",
                "3200": "Retained Earnings",
                
                # Revenue
                "4000": "Product Revenue",
                "4100": "Service Revenue",
                "4200": "Other Revenue",
                "4900": "Sales Returns & Allowances",
                
                # COGS
                "5000": "Cost of Goods Sold",
                "5100": "Materials",
                "5200": "Direct Labor",
                
                # Operating Expenses
                "6000": "Salaries & Wages",
                "6100": "Sales & Marketing",
                "6200": "Depreciation Expense",
                "6300": "Rent Expense",
                "6400": "Utilities",
                
                # Other
                "7000": "Interest Expense",
                "7100": "Foreign Exchange Gain/Loss",
                "7200": "Gain/Loss on Asset Sales",
            }
        
        elif self.scheme == AccountScheme.FIVE_DIGIT:
            self.coa = {
                "10000": "Cash and Cash Equivalents",
                "11000": "Accounts Receivable",
                "12000": "Inventory",
                "13000": "Prepaid Expenses",
                "15000": "Property, Plant & Equipment",
                "16000": "Accumulated Depreciation",
                "20000": "Accounts Payable",
                "21000": "Accrued Expenses",
                "22000": "Short-term Debt",
                "30000": "Common Stock",
                "31000": "Retained Earnings",
                "40000": "Product Revenue",
                "41000": "Service Revenue",
                "49000": "Sales Returns & Allowances",
                "50000": "Cost of Goods Sold",
                "60000": "Salaries & Wages",
                "61000": "Sales & Marketing",
                "62000": "Depreciation Expense",
                "70000": "Interest Expense",
            }
        
        elif self.scheme == AccountScheme.ALPHANUMERIC:
            self.coa = {
                "BAL-CASH": "Cash and Cash Equivalents",
                "BAL-AR": "Accounts Receivable",
                "BAL-INV": "Inventory",
                "BAL-PPE": "Property, Plant & Equipment",
                "LIA-AP": "Accounts Payable",
                "LIA-ACCRUED": "Accrued Expenses",
                "LIA-DEBT": "Long-term Debt",
                "EQ-STOCK": "Common Stock",
                "EQ-RE": "Retained Earnings",
                "REV-PRODUCT": "Product Revenue",
                "REV-SERVICE": "Service Revenue",
                "REV-RETURNS": "Sales Returns & Allowances",
                "COGS-PROD": "Cost of Goods Sold",
                "OPEX-SALARY": "Salaries & Wages",
                "OPEX-MKT": "Sales & Marketing",
                "OPEX-DEPR": "Depreciation Expense",
                "OTHER-INT": "Interest Expense",
            }
    
    def get_accounts(self) -> Dict[str, str]:
        """Return the chart of accounts"""
        return self.coa


class MultiEntityTrialBalance:
    """Generate multi-entity trial balance with consolidation logic"""
    
    def __init__(self, 
                 num_entities: int = 3,
                 account_scheme: AccountScheme = AccountScheme.FOUR_DIGIT,
                 include_intercompany: bool = True):
        self.num_entities = num_entities
        self.scheme = account_scheme
        self.include_intercompany = include_intercompany
        self.coa_gen = SyntheticAccountGenerator(account_scheme)
        self.coa = self.coa_gen.get_accounts()
        
        self.entities = self._generate_entities()
    
    def _generate_entities(self) -> List[str]:
        """Generate entity names"""
        return [f"Entity_{chr(65 + i)}" for i in range(self.num_entities)]
    
    def generate(self, seed: int = 42) -> pd.DataFrame:
        """Generate multi-entity trial balance"""
        np.random.seed(seed)
        
        rows = []
        entity_sizes = {e: np.random.uniform(1.0, 2.5) for e in self.entities}
        
        for entity in self.entities:
            size_factor = entity_sizes[entity]
            
            for account_code, account_name in self.coa.items():
                # Skip some accounts randomly
                if np.random.random() < 0.15:
                    continue
                
                base_amount = np.random.normal(100000, 50000) * size_factor
                
                # Create more realistic distributions
                if "Revenue" in account_name or "REVENUE" in account_name.upper():
                    base_amount = np.random.uniform(500000, 2000000) * size_factor
                    # Add returns (negative revenue)
                    if np.random.random() < 0.3:
                        base_amount = -abs(base_amount) * 0.05
                
                elif "COGS" in account_name or "Cost" in account_name:
                    base_amount = np.random.uniform(200000, 600000) * size_factor
                    if base_amount < 0:
                        base_amount = abs(base_amount)  # COGS should be positive
                
                elif "Receivable" in account_name:
                    base_amount = abs(np.random.uniform(50000, 300000)) * size_factor
                
                elif "Payable" in account_name or "Expense" in account_name:
                    base_amount = abs(np.random.uniform(30000, 150000)) * size_factor
                
                amount = round(base_amount, 2)
                
                if amount != 0:
                    rows.append({
                        'Entity': entity,
                        'Account_Code': account_code,
                        'Account_Name': account_name,
                        'Amount': amount,
                        'Period': '2024-12-31'
                    })
        
        # Add intercompany transactions if enabled
        if self.include_intercompany and self.num_entities > 1:
            rows.extend(self._generate_intercompany_transactions())
        
        df = pd.DataFrame(rows)
        return df
    
    def _generate_intercompany_transactions(self) -> List[Dict]:
        """Generate intercompany elimination entries"""
        rows = []
        np.random.seed(42)
        
        for i in range(len(self.entities) - 1):
            entity_from = self.entities[i]
            entity_to = self.entities[i + 1]
            
            amount = np.random.uniform(50000, 200000)
            
            # Intercompany receivable
            rows.append({
                'Entity': entity_from,
                'Account_Code': '1100' if self.scheme == AccountScheme.FOUR_DIGIT else '11000',
                'Account_Name': 'Intercompany Receivable',
                'Amount': amount,
                'Period': '2024-12-31'
            })
            
            # Intercompany payable
            rows.append({
                'Entity': entity_to,
                'Account_Code': '2000' if self.scheme == AccountScheme.FOUR_DIGIT else '20000',
                'Account_Name': 'Intercompany Payable',
                'Amount': -amount,
                'Period': '2024-12-31'
            })
        
        return rows


class CurrencyTrialBalance:
    """Generate trial balance with multi-currency transactions"""
    
    def __init__(self, account_scheme: AccountScheme = AccountScheme.FOUR_DIGIT):
        self.scheme = account_scheme
        self.coa_gen = SyntheticAccountGenerator(account_scheme)
        self.coa = self.coa_gen.get_accounts()
    
    def generate(self, seed: int = 42, base_currency: str = "USD") -> pd.DataFrame:
        """Generate trial balance with multi-currency entries"""
        np.random.seed(seed)
        rows = []
        
        # Distribution of currencies (80% base, 20% foreign)
        currencies = [base_currency] * 80 + list(Currency.__members__.keys())[:3]
        
        for account_code, account_name in self.coa.items():
            if np.random.random() < 0.15:
                continue
            
            base_amount = np.random.normal(100000, 50000)
            
            # Randomly select currency
            currency = np.random.choice(currencies)
            
            # Apply exchange rate
            if currency != base_currency:
                exchange_rate = Currency[currency].value[1]
                amount_in_base = base_amount * exchange_rate
            else:
                amount_in_base = base_amount
            
            if amount_in_base != 0:
                rows.append({
                    'Account_Code': account_code,
                    'Account_Name': account_name,
                    'Currency': currency,
                    'Amount_Original': base_amount,
                    'Exchange_Rate': Currency[currency].value[1] if currency != base_currency else 1.0,
                    'Amount_USD': round(amount_in_base, 2),
                    'Period': '2024-12-31'
                })
        
        df = pd.DataFrame(rows)
        return df


class MixedBasisTrialBalance:
    """Generate trial balance mixing cash and accrual basis entries"""
    
    def __init__(self, account_scheme: AccountScheme = AccountScheme.FOUR_DIGIT):
        self.scheme = account_scheme
        self.coa_gen = SyntheticAccountGenerator(account_scheme)
        self.coa = self.coa_gen.get_accounts()
    
    def generate(self, seed: int = 42) -> pd.DataFrame:
        """Generate trial balance with accrual and cash basis entries"""
        np.random.seed(seed)
        rows = []
        
        for account_code, account_name in self.coa.items():
            if np.random.random() < 0.15:
                continue
            
            amount = np.random.normal(100000, 50000)
            
            # Determine basis
            if "Receivable" in account_name or "Payable" in account_name or "Accrued" in account_name:
                basis = "Accrual"
            elif "Cash" in account_name:
                basis = "Cash"
            else:
                basis = np.random.choice(["Cash", "Accrual"], p=[0.3, 0.7])
            
            if amount != 0:
                rows.append({
                    'Account_Code': account_code,
                    'Account_Name': account_name,
                    'Amount': amount,
                    'Basis': basis,
                    'Period': '2024-12-31'
                })
        
        df = pd.DataFrame(rows)
        return df


class AdjustedTrialBalance:
    """Generate trial balance with known adjustments"""
    
    def __init__(self, account_scheme: AccountScheme = AccountScheme.FOUR_DIGIT):
        self.scheme = account_scheme
        self.coa_gen = SyntheticAccountGenerator(account_scheme)
        self.coa = self.coa_gen.get_accounts()
    
    def generate(self, seed: int = 42) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Generate trial balance with adjustments
        Returns: (unadjusted_df, adjustments_df)
        """
        np.random.seed(seed)
        
        # Unadjusted trial balance
        unadj_rows = []
        for account_code, account_name in self.coa.items():
            if np.random.random() < 0.15:
                continue
            amount = np.random.normal(100000, 50000)
            if amount != 0:
                unadj_rows.append({
                    'Account_Code': account_code,
                    'Account_Name': account_name,
                    'Unadjusted_Amount': amount,
                })
        
        unadj_df = pd.DataFrame(unadj_rows)
        
        # Generate adjustments
        adj_rows = []
        
        # Stock-based compensation adjustment
        adj_rows.append({
            'Journal_Entry_ID': 'ADJ-001',
            'Description': 'SBC expense - stock options vested',
            'Account_Code': 'OPEX-SALARY' if self.scheme == AccountScheme.ALPHANUMERIC else '6000',
            'Debit': 50000.0,
            'Credit': 0.0,
            'Adjustment_Type': 'add_back',
            'Reason': 'Non-cash stock-based compensation'
        })
        adj_rows.append({
            'Journal_Entry_ID': 'ADJ-001',
            'Description': 'SBC expense - stock options vested',
            'Account_Code': 'EQ-STOCK' if self.scheme == AccountScheme.ALPHANUMERIC else '3000',
            'Debit': 0.0,
            'Credit': 50000.0,
            'Adjustment_Type': 'add_back',
            'Reason': 'Non-cash stock-based compensation'
        })
        
        # Depreciation add-back
        adj_rows.append({
            'Journal_Entry_ID': 'ADJ-002',
            'Description': 'Reverse depreciation for EBITDA calc',
            'Account_Code': 'OPEX-DEPR' if self.scheme == AccountScheme.ALPHANUMERIC else '6200',
            'Debit': 75000.0,
            'Credit': 0.0,
            'Adjustment_Type': 'add_back',
            'Reason': 'Non-cash expense; add back for EBITDA'
        })
        adj_rows.append({
            'Journal_Entry_ID': 'ADJ-002',
            'Description': 'Reverse depreciation for EBITDA calc',
            'Account_Code': 'OPEX-DEPR' if self.scheme == AccountScheme.ALPHANUMERIC else '6200',
            'Debit': 0.0,
            'Credit': 75000.0,
            'Adjustment_Type': 'add_back',
            'Reason': 'Non-cash expense; add back for EBITDA'
        })
        
        # Related party normalization
        adj_rows.append({
            'Journal_Entry_ID': 'ADJ-003',
            'Description': 'Normalize related party mgmt fees',
            'Account_Code': 'OPEX-MKT' if self.scheme == AccountScheme.ALPHANUMERIC else '6100',
            'Debit': 25000.0,
            'Credit': 0.0,
            'Adjustment_Type': 'normalize',
            'Reason': 'Normalize above-market related party fees'
        })
        adj_rows.append({
            'Journal_Entry_ID': 'ADJ-003',
            'Description': 'Normalize related party mgmt fees',
            'Account_Code': 'LIA-ACCRUED' if self.scheme == AccountScheme.ALPHANUMERIC else '2100',
            'Debit': 0.0,
            'Credit': 25000.0,
            'Adjustment_Type': 'normalize',
            'Reason': 'Normalize above-market related party fees'
        })
        
        adj_df = pd.DataFrame(adj_rows)
        
        return unadj_df, adj_df


def generate_sample_trials(output_dir: str = "/workspaces/Personal-Model-Development/financial-normalizer/data/output"):
    """Generate all sample trial balances and save to CSV"""
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # 1. Multi-entity consolidation (4-digit scheme)
    print("Generating multi-entity consolidation (4-digit)...")
    me_gen = MultiEntityTrialBalance(num_entities=3, 
                                      account_scheme=AccountScheme.FOUR_DIGIT,
                                      include_intercompany=True)
    me_df = me_gen.generate()
    me_df.to_csv(f"{output_dir}/multi_entity_consolidation_4digit.csv", index=False)
    print(f"  → Saved {len(me_df)} rows")
    
    # 2. Multi-entity consolidation (5-digit scheme)
    print("Generating multi-entity consolidation (5-digit)...")
    me_gen = MultiEntityTrialBalance(num_entities=2, 
                                      account_scheme=AccountScheme.FIVE_DIGIT,
                                      include_intercompany=False)
    me_df = me_gen.generate(seed=43)
    me_df.to_csv(f"{output_dir}/multi_entity_5digit.csv", index=False)
    print(f"  → Saved {len(me_df)} rows")
    
    # 3. Alphanumeric accounts
    print("Generating trial balance (alphanumeric accounts)...")
    me_gen = MultiEntityTrialBalance(num_entities=1, 
                                      account_scheme=AccountScheme.ALPHANUMERIC)
    me_df = me_gen.generate(seed=44)
    me_df.to_csv(f"{output_dir}/alphanumeric_accounts.csv", index=False)
    print(f"  → Saved {len(me_df)} rows")
    
    # 4. Multi-currency
    print("Generating multi-currency trial balance...")
    cur_gen = CurrencyTrialBalance(account_scheme=AccountScheme.FOUR_DIGIT)
    cur_df = cur_gen.generate()
    cur_df.to_csv(f"{output_dir}/multi_currency_trial.csv", index=False)
    print(f"  → Saved {len(cur_df)} rows")
    
    # 5. Mixed basis (cash/accrual)
    print("Generating mixed basis trial balance...")
    mb_gen = MixedBasisTrialBalance(account_scheme=AccountScheme.FOUR_DIGIT)
    mb_df = mb_gen.generate()
    mb_df.to_csv(f"{output_dir}/mixed_basis_trial.csv", index=False)
    print(f"  → Saved {len(mb_df)} rows")
    
    # 6. With adjustments
    print("Generating trial balance with adjustments...")
    adj_gen = AdjustedTrialBalance(account_scheme=AccountScheme.FOUR_DIGIT)
    unadj_df, adj_df = adj_gen.generate()
    unadj_df.to_csv(f"{output_dir}/unadjusted_trial_balance.csv", index=False)
    adj_df.to_csv(f"{output_dir}/adjustments.csv", index=False)
    print(f"  → Saved {len(unadj_df)} rows (unadjusted), {len(adj_df)} adjustment entries")
    
    print(f"\n✓ All synthetic trial balances generated in {output_dir}/")


if __name__ == "__main__":
    generate_sample_trials()
