# Financial Data Pipeline

An automated intelligence system for scraping, archiving, and analyzing financial reports from renewable energy companies (e.g., Apollo Power, Enlight). It combines robust historical web scraping with Generative AI (Gemini/Claude) to turn raw PDFs into structured financial models and investment theses.

## 📚 Documentation
- **[System Architecture](system_architecture.md)**: Detailed design, components, and data flow.
- **[Diagnosis Report](diagnosis_report.md)**: Troubleshooting history for TASE scraping issues.
- **[Walkthrough](walkthrough.md)**: Guide to recent verification tests.

## Features

- **Robust Scraping**: Retrieves 5+ years of historical data from TASE Maya and IR websites.
- **Smart Deduplication**: Aggregates HTML, PDF, and Title links to prevent duplicate reports.
- **Google Drive Sync**: Automatically mirrors local downloads to a structured Google Drive folder (`Apps/finance/{Company}/{Year}/{Period}`).
- **AI Analysis**:
    - **Classification**: Sorts files into "Financial Reports" vs "Others".
    - **Extraction**: Uses LLMs (Gemini Pro/Flash, Claude 3.5 Sonnet) to extract key financial metrics (Revenue, Net Income, etc.).
    - **Thesis Generation**: Automatically updates an `Investment_Memo.md` with insights from each new report.

## Prerequisites

- Python 3.10+
- Google Cloud Project with Drive API enabled (for Drive Sync)
- API Keys for AI features:
    - `GOOGLE_API_KEY` (Gemini)
    - `ANTHROPIC_API_KEY` (Claude)

## Installation

1.  **Clone & Setup Environment**
    ```bash
    git clone https://github.com/oliamir/financial-data-pipeline.git
    cd financial-data-pipeline
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

2.  **Install Playwright Browsers**
    ```bash
    playwright install chromium
    ```

3.  **Configure Credentials**
    - Place `credentials.json` (Google OAuth) in the project root.
    - Set environment variables:
      ```bash
      export GOOGLE_API_KEY="your_key_here"
      export ANTHROPIC_API_KEY="your_key_here"
      ```

4.  ** Authenticate Drive (Optional)**
    ```bash
    python setup_drive.py
    ```

## Usage

### 1. Download Data
Scrape historical reports and sync to Drive.
```bash
# Download 5 years of Apollo Power reports and upload to Drive
python src/download.py --company Apollo --years 5 --upload
```

### 2. Analyze Data
Run AI analysis on downloaded files to extract financials and update the thesis.
```bash
# Use Google Gemini (Default)
python src/analyze.py --company Apollo --provider google --model gemini-2.0-flash

# Use Anthropic Claude
python src/analyze.py --company Apollo --provider anthropic --model claude-3-5-sonnet-20241022
```

## Project Structure

```text
src/
├── download.py             # Scraping & Downloading CLI
├── analyze.py              # AI Analysis CLI
├── scrapers/               # TASE & IR Scrapers
├── intelligence/           # LLM Client, Classifier, Extractor
└── drive_integration/      # Google Drive Uploader
downloads/                  # Local storage for reports
```
