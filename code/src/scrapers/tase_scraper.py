from typing import List
import requests
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper, ReportMetadata
import re

class TaseScraper(BaseScraper):
    # Direct Maya TASE website URL for company page
    MAYA_BASE_URL = "https://maya.tase.co.il/company/"
    
    def __init__(self, company_name: str, company_id: str):
        super().__init__(company_name)
        self.company_id = company_id # TASE Company ID (e.g., 720 for Enlight)

    def fetch_report_links(self) -> List[ReportMetadata]:
        reports = []
        try:
            # Construct the company page URL
            company_url = f"{self.MAYA_BASE_URL}{self.company_id}"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,he;q=0.8"
            }
            
            print(f"Scraping TASE Maya for Company {self.company_id} at {company_url}...")
            response = requests.get(company_url, headers=headers, timeout=15)
            
            if response.status_code != 200:
                print(f"Failed to access TASE Maya: {response.status_code}")
                # Try alternative approach - search for reports directly
                return self._search_maya_reports()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for links to financial reports
            # Maya typically has links with specific patterns or in tables
            for link in soup.find_all('a', href=True):
                href = link['href']
                text = link.get_text(strip=True)
                
                # Look for financial report indicators (Hebrew and English)
                is_financial = any(keyword in text.lower() for keyword in [
                    'financial', 'דוח כספי', 'quarterly', 'רבעון', 'annual', 'שנתי',
                    'q1', 'q2', 'q3', 'q4', 'תקופתי', 'periodic'
                ])
                
                if is_financial and ('.pdf' in href.lower() or 'report' in href.lower()):
                    # Extract year
                    year_match = re.search(r'20(2[0-9]|1[0-9])', text + ' ' + href)
                    year = int(year_match.group(0)) if year_match else 2024
                    
                    # Determine period
                    period = self._extract_period(text)
                    
                    if period != "Other":
                        # Construct full URL
                        if href.startswith('http'):
                            full_url = href
                        else:
                            full_url = f"https://maya.tase.co.il{href}" if href.startswith('/') else f"https://maya.tase.co.il/{href}"
                        
                        # Avoid duplicates
                        if not any(r.url == full_url for r in reports):
                            reports.append(ReportMetadata(
                                company_name=self.company_name,
                                year=year,
                                period=period,
                                url=full_url,
                                source="TASE_Maya",
                                file_type="pdf"
                            ))
                            print(f"  Found: {year} {period} - {text[:50]}")

        except Exception as e:
            print(f"Error scraping TASE: {e}")
            import traceback
            traceback.print_exc()
            
        return reports
    
    def _extract_period(self, text: str) -> str:
        """Extract period (Q1, Q2, Q3, Q4, Annual) from text"""
        text_lower = text.lower()
        
        # Check for quarterly reports
        if 'q1' in text_lower or 'רבעון ראשון' in text or 'רבעון 1' in text or 'first quarter' in text_lower:
            return 'Q1'
        elif 'q2' in text_lower or 'רבעון שני' in text or 'רבעון 2' in text or 'second quarter' in text_lower:
            return 'Q2'
        elif 'q3' in text_lower or 'רבעון שלישי' in text or 'רבעון 3' in text or 'third quarter' in text_lower:
            return 'Q3'
        elif 'q4' in text_lower or 'רבעון רביעי' in text or 'רבעון 4' in text or 'fourth quarter' in text_lower:
            return 'Q4'
        elif 'annual' in text_lower or 'שנתי' in text or 'yearly' in text_lower:
            return 'Annual'
        
        return "Other"
    
    def _search_maya_reports(self) -> List[ReportMetadata]:
        """Alternative method to search for reports if direct company page fails"""
        print("Attempting alternative TASE search method...")
        # This would require more complex scraping or API reverse engineering
        # For now, return empty list
        return []

