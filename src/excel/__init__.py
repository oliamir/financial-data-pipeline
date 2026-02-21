"""Excel financial model builder.

Generates a professional 9-sheet Excel workbook from financial data
with formatted tables, charts, and dashboards.
"""

import json
from pathlib import Path
from typing import List, Optional, Tuple

from ..models.financial import FinancialPeriod
from ..models.kpi import KPIMetrics
from ..storage.file_manager import FileManager
from ..utils.logging import get_logger

logger = get_logger(__name__)

# Sheet configuration
SHEETS = [
    "Dashboard",
    "Income Statement",
    "Balance Sheet",
    "Cash Flow",
    "KPI Ratios",
    "Growth Analysis",
    "Valuation",
    "Peer Comparison",
    "Notes",
]


class ExcelModelBuilder:
    """Builds a professional financial model Excel workbook."""

    def __init__(self, slug: str):
        self.slug = slug
        self.storage = FileManager(slug)

    def build(self, output_path: Optional[str] = None) -> str:
        """Build the complete Excel model.

        Args:
            output_path: Override output file path.

        Returns:
            Path to the generated Excel file.
        """
        if output_path is None:
            output_path = str(self.storage.paths.model_xlsx)

        # Load data
        periods = self.storage.load_financials()
        kpi = self.storage.load_kpis()

        if not periods:
            logger.warning(f"No financial data for {self.slug}, generating empty model")

        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.chart import BarChart, Reference, LineChart
            from openpyxl.utils import get_column_letter

            wb = openpyxl.Workbook()

            # Create sheets
            for i, sheet_name in enumerate(SHEETS):
                if i == 0:
                    ws = wb.active
                    ws.title = sheet_name
                else:
                    wb.create_sheet(sheet_name)

            # Populate sheets
            self._build_dashboard(wb["Dashboard"], periods, kpi)
            self._build_income_statement(wb["Income Statement"], periods)
            self._build_balance_sheet(wb["Balance Sheet"], periods)
            self._build_cash_flow(wb["Cash Flow"], periods)
            self._build_kpi_ratios(wb["KPI Ratios"], periods, kpi)
            self._build_growth_analysis(wb["Growth Analysis"], periods)
            self._build_valuation(wb["Valuation"], periods, kpi)
            self._build_notes(wb["Notes"])

            # Save
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            wb.save(output_path)
            logger.info(f"Excel model saved: {output_path}")
            return output_path

        except ImportError:
            logger.error("openpyxl not installed. Run: pip install openpyxl")
            raise

    def _header_style(self):
        from openpyxl.styles import Font, PatternFill, Alignment
        return {
            "font": Font(bold=True, color="FFFFFF", size=11),
            "fill": PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid"),
            "alignment": Alignment(horizontal="center"),
        }

    def _number_format(self, value, is_pct=False):
        if is_pct:
            return "#,##0.0%"
        if isinstance(value, float) and abs(value) < 100:
            return "#,##0.00"
        return "#,##0"

    def _build_dashboard(self, ws, periods: List[FinancialPeriod], kpi: Optional[KPIMetrics]):
        """Build the Dashboard summary sheet."""
        ws.column_dimensions["A"].width = 25
        ws.column_dimensions["B"].width = 18

        # Title
        ws["A1"] = f"Financial Dashboard: {self.slug.upper()}"
        ws["A1"].font = Font(bold=True, size=16, color="1F4E79")

        row = 3
        if periods:
            latest = periods[-1]
            ws[f"A{row}"] = "Latest Period"
            ws[f"B{row}"] = f"{latest.period_type} {latest.fiscal_year}"
            row += 1
            ws[f"A{row}"] = "Currency"
            ws[f"B{row}"] = latest.currency
            row += 1

            if latest.income_statement.revenue:
                ws[f"A{row}"] = "Revenue"
                ws[f"B{row}"] = latest.income_statement.revenue
                ws[f"B{row}"].number_format = "#,##0"
                row += 1

            if latest.income_statement.net_income:
                ws[f"A{row}"] = "Net Income"
                ws[f"B{row}"] = latest.income_statement.net_income
                ws[f"B{row}"].number_format = "#,##0"
                row += 1

        if kpi:
            row += 1
            ws[f"A{row}"] = "Key Ratios"
            ws[f"A{row}"].font = Font(bold=True, size=12)
            row += 1
            for label, value in [
                ("Gross Margin", kpi.gross_margin),
                ("Operating Margin", kpi.operating_margin),
                ("Net Margin", kpi.net_margin),
                ("Revenue Growth", kpi.revenue_growth),
                ("ROE", kpi.roe),
                ("Debt/Equity", kpi.debt_to_equity),
            ]:
                if value is not None:
                    ws[f"A{row}"] = label
                    ws[f"B{row}"] = value
                    ws[f"B{row}"].number_format = "0.0%"
                    row += 1

    def _build_income_statement(self, ws, periods: List[FinancialPeriod]):
        """Build Income Statement sheet with multi-period columns."""
        headers = ["Line Item"] + [f"{p.period_type} {p.fiscal_year}" for p in periods]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            for k, v in self._header_style().items():
                setattr(cell, k, v)
            ws.column_dimensions[chr(64 + col)].width = 18

        fields = [
            ("Revenue", "revenue"), ("Cost of Revenue", "cost_of_revenue"),
            ("Gross Profit", "gross_profit"), ("R&D Expense", "rd_expense"),
            ("SG&A Expense", "sga_expense"), ("Operating Income", "operating_income"),
            ("Interest Expense", "interest_expense"), ("Pretax Income", "pretax_income"),
            ("Income Tax", "income_tax"), ("Net Income", "net_income"),
            ("EBITDA", "ebitda"), ("EPS (Diluted)", "eps_diluted"),
        ]

        for row_idx, (label, field) in enumerate(fields, 2):
            ws.cell(row=row_idx, column=1, value=label)
            for col_idx, period in enumerate(periods, 2):
                val = getattr(period.income_statement, field, None)
                if val is not None:
                    cell = ws.cell(row=row_idx, column=col_idx, value=val)
                    cell.number_format = "#,##0"

    def _build_balance_sheet(self, ws, periods: List[FinancialPeriod]):
        """Build Balance Sheet sheet."""
        headers = ["Line Item"] + [f"{p.period_type} {p.fiscal_year}" for p in periods]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            for k, v in self._header_style().items():
                setattr(cell, k, v)
            ws.column_dimensions[chr(64 + col)].width = 18

        fields = [
            ("Cash & Equivalents", "cash_and_equivalents"),
            ("Accounts Receivable", "accounts_receivable"),
            ("Inventory", "inventory"),
            ("Total Current Assets", "total_current_assets"),
            ("PP&E Net", "ppe_net"),
            ("Total Assets", "total_assets"),
            ("Accounts Payable", "accounts_payable"),
            ("Total Current Liabilities", "total_current_liabilities"),
            ("Long-term Debt", "long_term_debt"),
            ("Total Liabilities", "total_liabilities"),
            ("Total Equity", "total_equity"),
        ]

        for row_idx, (label, field) in enumerate(fields, 2):
            ws.cell(row=row_idx, column=1, value=label)
            for col_idx, period in enumerate(periods, 2):
                val = getattr(period.balance_sheet, field, None) if period.balance_sheet else None
                if val is not None:
                    cell = ws.cell(row=row_idx, column=col_idx, value=val)
                    cell.number_format = "#,##0"

    def _build_cash_flow(self, ws, periods: List[FinancialPeriod]):
        """Build Cash Flow sheet."""
        headers = ["Line Item"] + [f"{p.period_type} {p.fiscal_year}" for p in periods]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            for k, v in self._header_style().items():
                setattr(cell, k, v)
            ws.column_dimensions[chr(64 + col)].width = 18

        fields = [
            ("Cash from Operations", "cash_from_operations"),
            ("CapEx", "capex"),
            ("Free Cash Flow", "free_cash_flow"),
            ("Cash from Investing", "cash_from_investing"),
            ("Cash from Financing", "cash_from_financing"),
            ("Net Change in Cash", "net_change_in_cash"),
        ]

        for row_idx, (label, field) in enumerate(fields, 2):
            ws.cell(row=row_idx, column=1, value=label)
            for col_idx, period in enumerate(periods, 2):
                val = getattr(period.cash_flow, field, None) if period.cash_flow else None
                if val is not None:
                    cell = ws.cell(row=row_idx, column=col_idx, value=val)
                    cell.number_format = "#,##0"

    def _build_kpi_ratios(self, ws, periods: List[FinancialPeriod], kpi: Optional[KPIMetrics]):
        """Build KPI Ratios sheet."""
        ws.column_dimensions["A"].width = 25
        ws.column_dimensions["B"].width = 15

        ws.cell(row=1, column=1, value="KPI Ratio").font = Font(bold=True)
        ws.cell(row=1, column=2, value="Value").font = Font(bold=True)

        if not kpi:
            ws.cell(row=2, column=1, value="No KPI data available")
            return

        ratios = [
            ("Gross Margin", kpi.gross_margin),
            ("Operating Margin", kpi.operating_margin),
            ("EBITDA Margin", kpi.ebitda_margin),
            ("Net Margin", kpi.net_margin),
            ("R&D % Revenue", kpi.rd_pct_revenue),
            ("SG&A % Revenue", kpi.sga_pct_revenue),
            ("Revenue Growth", kpi.revenue_growth),
            ("ROE", kpi.roe),
            ("ROA", kpi.roa),
            ("Debt/Equity", kpi.debt_to_equity),
            ("Current Ratio", kpi.current_ratio),
            ("Interest Coverage", kpi.interest_coverage),
            ("P/E Ratio", kpi.pe_ratio),
            ("EV/EBITDA", kpi.ev_to_ebitda),
        ]

        for row_idx, (label, value) in enumerate(ratios, 2):
            ws.cell(row=row_idx, column=1, value=label)
            if value is not None:
                cell = ws.cell(row=row_idx, column=2, value=value)
                if any(kw in label for kw in ["Margin", "Growth", "ROE", "ROA", "%"]):
                    cell.number_format = "0.0%"
                else:
                    cell.number_format = "#,##0.00"

    def _build_growth_analysis(self, ws, periods: List[FinancialPeriod]):
        """Build Growth Analysis sheet with period-over-period changes."""
        ws.column_dimensions["A"].width = 20

        ws.cell(row=1, column=1, value="Growth Analysis").font = Font(bold=True, size=14)

        if len(periods) < 2:
            ws.cell(row=3, column=1, value="Need at least 2 periods for growth analysis")
            return

        headers = ["Metric"] + [f"{p.period_type} {p.fiscal_year}" for p in periods[1:]]
        for col, h in enumerate(headers, 1):
            ws.cell(row=3, column=col, value=h).font = Font(bold=True)
            ws.column_dimensions[chr(64 + col)].width = 15

        metrics = ["revenue", "gross_profit", "operating_income", "net_income", "ebitda"]
        labels = ["Revenue", "Gross Profit", "Operating Income", "Net Income", "EBITDA"]

        for row_idx, (label, field) in enumerate(zip(labels, metrics), 4):
            ws.cell(row=row_idx, column=1, value=f"{label} Growth")
            for col_idx, i in enumerate(range(1, len(periods)), 2):
                curr_val = getattr(periods[i].income_statement, field, None)
                prev_val = getattr(periods[i - 1].income_statement, field, None)
                if curr_val and prev_val and prev_val != 0:
                    growth = (curr_val - prev_val) / abs(prev_val)
                    cell = ws.cell(row=row_idx, column=col_idx, value=growth)
                    cell.number_format = "0.0%"

    def _build_valuation(self, ws, periods: List[FinancialPeriod], kpi: Optional[KPIMetrics]):
        """Build Valuation sheet."""
        ws.column_dimensions["A"].width = 25
        ws.column_dimensions["B"].width = 15

        ws.cell(row=1, column=1, value="Valuation Metrics").font = Font(bold=True, size=14)

        if not kpi:
            ws.cell(row=3, column=1, value="No valuation data available")
            return

        row = 3
        for label, value in [
            ("P/E Ratio", kpi.pe_ratio),
            ("EV/EBITDA", kpi.ev_to_ebitda),
            ("Price/Book", kpi.price_to_book),
            ("Price/Sales", kpi.price_to_sales),
            ("Price/FCF", kpi.price_to_fcf),
            ("Dividend Yield", kpi.dividend_yield),
        ]:
            ws.cell(row=row, column=1, value=label)
            if value is not None:
                cell = ws.cell(row=row, column=2, value=value)
                cell.number_format = "#,##0.00" if "Yield" not in label else "0.0%"
            row += 1

    def _build_notes(self, ws):
        """Build Notes sheet with metadata."""
        from datetime import datetime

        ws.column_dimensions["A"].width = 35
        ws.cell(row=1, column=1, value="Model Notes").font = Font(bold=True, size=14)
        ws.cell(row=3, column=1, value=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        ws.cell(row=4, column=1, value=f"Company: {self.slug}")
        ws.cell(row=5, column=1, value="Source: Financial Data Pipeline v3")
        ws.cell(row=7, column=1, value="Disclaimer: This model is auto-generated from parsed financial reports.")
        ws.cell(row=8, column=1, value="All data should be verified against original source documents.")
