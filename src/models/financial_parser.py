import pdfplumber
import pandas as pd
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import os

@dataclass
class FinancialData:
    """Container for extracted financial data"""
    company: str
    year: int
    period: str
    revenue: Optional[float] = None
    net_income: Optional[float] = None
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    total_equity: Optional[float] = None
    cash: Optional[float] = None
    total_debt: Optional[float] = None
    operating_income: Optional[float] = None
    ebitda: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return {
            'Company': self.company,
            'Year': self.year,
            'Period': self.period,
            'Revenue': self.revenue,
            'Net Income': self.net_income,
            'Total Assets': self.total_assets,
            'Total Liabilities': self.total_liabilities,
            'Total Equity': self.total_equity,
            'Cash': self.cash,
            'Total Debt': self.total_debt,
            'Operating Income': self.operating_income,
            'EBITDA': self.ebitda
        }

@dataclass
class KPIMetrics:
    """Calculated KPI metrics"""
    company: str
    year: int
    period: str
    
    # Profitability ratios
    net_margin: Optional[float] = None  # Net Income / Revenue
    operating_margin: Optional[float] = None  # Operating Income / Revenue
    ebitda_margin: Optional[float] = None  # EBITDA / Revenue
    
    # Leverage ratios
    debt_to_equity: Optional[float] = None  # Total Debt / Total Equity
    debt_to_assets: Optional[float] = None  # Total Debt / Total Assets
    
    # Liquidity
    cash_ratio: Optional[float] = None  # Cash / Total Assets
    
    def to_dict(self) -> Dict:
        return {
            'Company': self.company,
            'Year': self.year,
            'Period': self.period,
            'Net Margin (%)': round(self.net_margin * 100, 2) if self.net_margin else None,
            'Operating Margin (%)': round(self.operating_margin * 100, 2) if self.operating_margin else None,
            'EBITDA Margin (%)': round(self.ebitda_margin * 100, 2) if self.ebitda_margin else None,
            'Debt/Equity': round(self.debt_to_equity, 2) if self.debt_to_equity else None,
            'Debt/Assets': round(self.debt_to_assets, 2) if self.debt_to_assets else None,
            'Cash Ratio': round(self.cash_ratio, 2) if self.cash_ratio else None
        }

class PDFFinancialParser:
    """Parse financial PDFs and extract key metrics"""
    
    def __init__(self):
        # Keywords to identify financial line items (English and Hebrew)
        self.revenue_keywords = ['revenue', 'revenues', 'sales', 'הכנסות', 'total revenue']
        self.net_income_keywords = ['net income', 'net profit', 'net loss', 'רווח נקי', 'הפסד נקי']
        self.assets_keywords = ['total assets', 'סך נכסים', 'total current assets']
        self.liabilities_keywords = ['total liabilities', 'סך התחייבויות']
        self.equity_keywords = ['total equity', 'shareholders equity', 'הון עצמי', 'stockholders equity']
        self.cash_keywords = ['cash and cash equivalents', 'cash', 'מזומנים']
        self.debt_keywords = ['total debt', 'long-term debt', 'borrowings', 'הלוואות']
        self.operating_income_keywords = ['operating income', 'operating profit', 'רווח תפעולי']
        self.ebitda_keywords = ['ebitda', 'adjusted ebitda']
    
    def extract_number(self, text: str) -> Optional[float]:
        """Extract numerical value from text, handling thousands/millions notation"""
        if not text:
            return None
        
        # Remove common non-numeric characters
        text = text.replace(',', '').replace('$', '').replace('(', '-').replace(')', '')
        text = text.strip()
        
        # Try to extract number
        match = re.search(r'-?\d+\.?\d*', text)
        if match:
            try:
                value = float(match.group())
                # Check if value is in thousands (common in financial reports)
                # This is a heuristic - may need adjustment based on actual reports
                return value
            except:
                return None
        return None
    
    def find_value_in_table(self, table: List[List], keywords: List[str]) -> Optional[float]:
        """Search for a value in a table based on keywords"""
        for row in table:
            if not row or len(row) < 2:
                continue
            
            # Get the first cell (usually the label)
            label = str(row[0]).lower() if row[0] else ""
            
            # Check if any keyword matches
            for keyword in keywords:
                if keyword.lower() in label:
                    # Try to extract number from subsequent cells
                    for cell in row[1:]:
                        value = self.extract_number(str(cell))
                        if value is not None:
                            return value
        return None
    
    def parse_pdf(self, pdf_path: str, company: str, year: int, period: str) -> FinancialData:
        """
        Parse a financial PDF and extract key metrics.
        
        Args:
            pdf_path: Path to the PDF file
            company: Company name
            year: Year
            period: Period (Q1, Q2, Q3, Q4, Annual)
            
        Returns:
            FinancialData object with extracted values
        """
        financial_data = FinancialData(company=company, year=year, period=period)
        
        if not os.path.exists(pdf_path):
            print(f"PDF not found: {pdf_path}")
            return financial_data
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                print(f"Parsing {pdf_path} ({len(pdf.pages)} pages)...")
                
                # Extract tables from all pages
                all_tables = []
                for page_num, page in enumerate(pdf.pages):
                    tables = page.extract_tables()
                    if tables:
                        all_tables.extend(tables)
                        print(f"  Page {page_num + 1}: Found {len(tables)} tables")
                
                # Search for financial metrics in all tables
                for table in all_tables:
                    if not table:
                        continue
                    
                    # Try to find each metric
                    if financial_data.revenue is None:
                        financial_data.revenue = self.find_value_in_table(table, self.revenue_keywords)
                    
                    if financial_data.net_income is None:
                        financial_data.net_income = self.find_value_in_table(table, self.net_income_keywords)
                    
                    if financial_data.total_assets is None:
                        financial_data.total_assets = self.find_value_in_table(table, self.assets_keywords)
                    
                    if financial_data.total_liabilities is None:
                        financial_data.total_liabilities = self.find_value_in_table(table, self.liabilities_keywords)
                    
                    if financial_data.total_equity is None:
                        financial_data.total_equity = self.find_value_in_table(table, self.equity_keywords)
                    
                    if financial_data.cash is None:
                        financial_data.cash = self.find_value_in_table(table, self.cash_keywords)
                    
                    if financial_data.total_debt is None:
                        financial_data.total_debt = self.find_value_in_table(table, self.debt_keywords)
                    
                    if financial_data.operating_income is None:
                        financial_data.operating_income = self.find_value_in_table(table, self.operating_income_keywords)
                    
                    if financial_data.ebitda is None:
                        financial_data.ebitda = self.find_value_in_table(table, self.ebitda_keywords)
                
                print(f"  ✓ Extraction complete")
                
        except Exception as e:
            print(f"Error parsing PDF: {e}")
            import traceback
            traceback.print_exc()
        
        return financial_data
    
    def calculate_kpis(self, financial_data: FinancialData) -> KPIMetrics:
        """Calculate KPI metrics from financial data"""
        kpis = KPIMetrics(
            company=financial_data.company,
            year=financial_data.year,
            period=financial_data.period
        )
        
        # Profitability ratios
        if financial_data.revenue and financial_data.revenue > 0:
            if financial_data.net_income is not None:
                kpis.net_margin = financial_data.net_income / financial_data.revenue
            
            if financial_data.operating_income is not None:
                kpis.operating_margin = financial_data.operating_income / financial_data.revenue
            
            if financial_data.ebitda is not None:
                kpis.ebitda_margin = financial_data.ebitda / financial_data.revenue
        
        # Leverage ratios
        if financial_data.total_equity and financial_data.total_equity > 0:
            if financial_data.total_debt is not None:
                kpis.debt_to_equity = financial_data.total_debt / financial_data.total_equity
        
        if financial_data.total_assets and financial_data.total_assets > 0:
            if financial_data.total_debt is not None:
                kpis.debt_to_assets = financial_data.total_debt / financial_data.total_assets
            
            if financial_data.cash is not None:
                kpis.cash_ratio = financial_data.cash / financial_data.total_assets
        
        return kpis
