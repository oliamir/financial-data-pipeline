from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import os

class ReportMetadata:
    def __init__(self, company_name: str, year: int, period: str, url: str, source: str, file_type: str = 'pdf', description: str = "", extra_headers: Optional[Dict] = None, attachments: Optional[List] = None):
        self.company_name = company_name
        self.year = year
        self.period = period  # 'Q1', 'Q2', 'Q3', 'Annual'
        self.url = url
        self.source = source  # 'Enlight_IR', 'TASE_Maya'
        self.file_type = file_type
        self.description = description
        self.extra_headers = extra_headers or {}
        self.attachments = attachments or []
        self.local_path: Optional[str] = None
        self.local_paths: List[str] = []
        self.drive_id: Optional[str] = None

    def __repr__(self):
        return f"<Report {self.company_name} {self.year} {self.period} ({self.source})>"

class BaseScraper(ABC):
    def __init__(self, company_name: str, output_dir: str = "downloads"):
        self.company_name = company_name
        self.output_dir = os.path.join(output_dir, company_name)
        os.makedirs(self.output_dir, exist_ok=True)

    @abstractmethod
    def fetch_report_links(self) -> List[ReportMetadata]:
        """
        Scrapes the source website and returns a list of available reports/files.
        """
        pass

    def download_report(self, report: ReportMetadata) -> str:
        """
        Downloads the file from report.url and saves it to local disk.
        Returns the local file path.
        """
        import requests
        
        # Determine filename
        filename = f"{report.year}_{report.period}_{report.source}.{report.file_type}"
        local_path = os.path.join(self.output_dir, filename)
        
        if os.path.exists(local_path):
            print(f"File already exists: {local_path}")
            report.local_path = local_path
            return local_path

        print(f"Downloading {report.url} to {local_path}...")
        try:
            # Add headers to avoid 403 errors
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/pdf,application/octet-stream,*/*',
                'Referer': report.url.rsplit('/', 1)[0] + '/'  # Use the parent URL as referer
            }
            # Merge extra headers from report metadata (e.g. Cookies)
            if report.extra_headers:
                headers.update(report.extra_headers)
            
            response = requests.get(report.url, stream=True, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Verify valid PDF content
            content_type = response.headers.get('Content-Type', '').lower()
            if 'application/pdf' not in content_type and 'application/octet-stream' not in content_type:
                print(f"  ⚠ Skipping: Content-Type is '{content_type}', not a PDF")
                return ""
                
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            report.local_path = local_path
            print(f"✓ Successfully downloaded: {local_path}")
            return local_path
        except Exception as e:
            print(f"Failed to download {report.url}: {e}")
            return ""
