from typing import List
import requests
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper, ReportMetadata
from urllib.parse import urljoin
import re

class EnlightScraper(BaseScraper):
    BASE_URL = "https://enlightenergy.co.il/investors/financial-reports/"
    ARCHIVE_URL = "https://enlightenergy.co.il/earnings-releases/"  # Historical reports
    
    def fetch_report_links(self) -> List[ReportMetadata]:
        reports = []
        
        # Scrape current reports page
        reports.extend(self._scrape_page(self.BASE_URL, "Current Reports"))
        
        # Scrape archive page for historical data
        reports.extend(self._scrape_page(self.ARCHIVE_URL, "Archive"))
        
        return reports
    
    def _scrape_page(self, url: str, page_name: str) -> List[ReportMetadata]:
        """Scrape a single page for reports"""
        reports = []
        
        try:
            print(f"Scraping {page_name}: {url}...")
            
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code != 200:
                print(f"  Failed to access {page_name}: {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for all links that contain PDFs or lead to financial reports
            for link in soup.find_all('a', href=True):
                href = link['href']
                text = link.get_text(strip=True).lower()
                
                # Skip if not a PDF
                if '.pdf' not in href.lower():
                    continue
                
                # Look for financial report indicators
                is_report = any(keyword in text for keyword in [
                    'earnings', 'release', 'financial', '20-f', 'quarterly', 'annual', 'report', 'q1', 'q2', 'q3', 'q4'
                ])
                
                if not is_report:
                    continue
                
                # Extract year from text or href - look for 2020-2025
                year_match = re.search(r'20(2[0-5]|1[0-9])', text + ' ' + href)
                year = int(year_match.group(0)) if year_match else 2024
                
                # Determine period - be more aggressive in detection
                period = "Other"
                text_lower = text.lower()
                href_lower = href.lower()
                combined = text_lower + ' ' + href_lower
                
                # Check for quarterly patterns
                if any(q in combined for q in ['1q', 'q1', 'first quarter', '1st quarter']):
                    period = 'Q1'
                elif any(q in combined for q in ['2q', 'q2', 'second quarter', '2nd quarter']):
                    period = 'Q2'
                elif any(q in combined for q in ['3q', 'q3', 'third quarter', '3rd quarter']):
                    period = 'Q3'
                elif any(q in combined for q in ['4q', 'q4', 'fourth quarter', '4th quarter']):
                    period = 'Q4'
                elif any(a in combined for a in ['annual', '20-f', 'yearly', 'year end']):
                    period = 'Annual'
                
                # Only add if we identified it as a quarterly or annual report
                if period != "Other":
                    full_url = urljoin(url, href)
                    
                    # Avoid duplicates
                    if not any(r.url == full_url for r in reports):
                        reports.append(ReportMetadata(
                            company_name=self.company_name,
                            year=year,
                            period=period,
                            url=full_url,
                            source="Enlight_IR"
                        ))
                        print(f"  Found: {year} {period} - {text[:50]}")
                        
        except Exception as e:
            print(f"Error scraping {page_name}: {e}")
            import traceback
            traceback.print_exc()
            
        return reports
