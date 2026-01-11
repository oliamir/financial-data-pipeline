# System Architecture - Financial Data Pipeline

## Overview
The **Financial Data Pipeline** is an automated system designed to scrape, download, analyze, and archive financial reports from renewable energy companies (specifically focusing on TASE-listed companies like Apollo Power). It combines robust web scraping with Generative AI to turn raw PDF reports into structured financial models and investment theses.

## High-Level Architecture

The system is composed of two main independent workflows:
1.  **Download Pipeline**: Scrapes web sources, downloads files, and syncs to Google Drive.
2.  **Analysis Pipeline**: Processes downloaded files using LLMs to extract data and generate insights.

### Architecture Diagram

```mermaid
graph TD
    subgraph Data Sources
        TASE[TASE Maya Website]
        IR[Company IR Sites]
    end

    subgraph "Download Pipeline (src/download.py)"
        Scraper[TasePlaywrightScraper]
        Downloader[File Downloader]
        Drive[DriveUploader]
    end

    subgraph Storage
        LocalFS[Local Filesystem<br/>(downloads/)]
        GDrive[Google Drive]
    end

    subgraph "Analysis Pipeline (src/analyze.py)"
        Classifier[DocumentClassifier]
        Extractor[FinancialExtractor]
        ThesisGen[ThesisGenerator]
        LLM[LLM Client<br/>(Gemini / Claude)]
    end

    subgraph Outputs
        CSV[Financial_Model.csv]
        Memo[Investment_Memo.md]
    end

    %% Data Flow
    TASE --> Scraper
    IR --> Scraper
    Scraper --> Downloader
    Downloader --> LocalFS
    Downloader --> Drive --> GDrive
    LocalFS --> Classifier
    Classifier --> Extractor
    Classifier --> ThesisGen
    Extractor --> LLM
    ThesisGen --> LLM
    Extractor --> CSV
    ThesisGen --> Memo
```

## Directory Structure

```text
financial_data_app/
├── src/
│   ├── download.py                  # Entry point for scraping & downloading
│   ├── analyze.py                   # Entry point for AI analysis
│   ├── scrapers/
│   │   ├── base_scraper.py          # Abstract base class
│   │   ├── tase_playwright_scraper.py # Robust TASE scraper (Playwright)
│   │   └── enlight_scraper.py       # Legacy IR scraper
│   ├── intelligence/
│   │   ├── llm_client.py            # Wrapper for Gemini & Anthropic APIs
│   │   ├── classifier.py            # Classifies docs (Financial Report vs Other)
│   │   ├── extractor.py             # Extracts structured financial data
│   │   └── thesis.py                # Generates/Updates investment memos
│   ├── drive_integration/
│   │   └── drive_uploader.py        # Google Drive API client
│   └── config/
│       └── companies.py             # Company registry (IDs, URLs)
├── downloads/                       # Staging area for downloaded files
├── venv/                            # Python Virtual Environment
├── requirements.txt                 # Dependencies
└── README.md                        # Documentation
```

## core Components

### 1. Download Pipeline (`src/download.py`)
Responsible for acquiring data. It supports:
*   **Argument Parsing**: Filters by company (`--company`) and history depth (`--years`).
*   **Scraper Orchestration**: Selects the appropriate scraper based on company config.
*   **File Organization**: Saves files to `downloads/{Company}/{Year}/{Period}/`.
*   **Drive Sync**: Optionally uploads mirrored structure to Google Drive.

#### TASE Scraper (`src/scrapers/tase_playwright_scraper.py`)
A robust, headless browser scraper designed for the TASE Maya platform.
*   **Pagination**: Iterates through historical report pages (1-100+) to retrieve 5+ years of data.
*   **Deduplication**: Intelligent grouping of report links (HTML, PDF, Hebrew/English versions) by TASE Report ID.
*   **Reliability**: Uses `page.expect_download()` to handle complex redirect chains and cross-origin file hosting.
*   **Asset Logic**: Prioritizes PDF downloads over HTML/other formats.

### 2. Analysis Pipeline (`src/analyze.py`)
Responsible for turning files into intelligence.
*   **Scanning**: Walks the `downloads/` directory.
*   **Classification**: Uses a "Cheap" LLM call to determine if a file is a financial report, presentation, or irrelevant.
*   **Extraction**: For financial reports, sends the file content to a "Reasoning" LLM (e.g., Gemini Flash 2.0 or Claude 3.5 Sonnet) to extract revenue, net income, cash flow, etc.
*   **Thesis Generation**: Aggregates insights to build an evolving `Investment_Memo.md`.
*   **Structured Output**: Appends extracted metrics to `Financial_Model.csv`.

### 3. Intelligence Layer (`src/intelligence/`)
A unified interface for LLM interactions.
*   **LLM Client**: seamless switching between Google Gemini and Anthropic Claude. Handles:
    *   **Google**: File API uploads (`genai.upload_file`).
    *   **Anthropic**: Base64 image/PDF encoding for API requests.
    *   **Rate Limiting**: Automatic backoff and retry logic.

## Data Flow Lifecycle

1.  **User triggers download**: `python src/download.py --company Apollo --years 5 --upload`
2.  **Scraper Execution**: Browser launches, scans pages, finds 100+ reports.
3.  **Download**: Files are saved locally (e.g., `downloads/Apollo/2024/Q1/123456.pdf`).
4.  **Upload (Optional)**: Files are pushed to `Apps/finance/Apollo/2024/Q1/` in Google Drive.
5.  **User triggers analysis**: `python src/analyze.py --company Apollo`
6.  **AI Classification**: "Is `123456.pdf` a financial report?" -> YES.
7.  **AI Extraction**: "Extract Revenue and Net Profit found in `123456.pdf`" -> `{Rev: 50M, Net: 2M}`.
8.  **Output**: Data added to CSV; file moved to `Financials/` subfolder.
