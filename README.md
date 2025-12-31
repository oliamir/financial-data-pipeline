# Financial Data Application

Automated system to scrape financial reports from company IR websites and TASE, upload to Google Drive, and extract KPIs.

## Features

- 📊 **Multi-Source Scraping**: Company IR websites + TASE Maya
- ☁️ **Google Drive Integration**: Automated folder structure and uploads
- 📈 **KPI Extraction**: Parse PDFs and calculate financial metrics
- 🔄 **Automated Pipeline**: End-to-end data collection and processing

## Setup

### 1. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Google Drive Setup (Optional but Recommended)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable **Google Drive API**
4. Create **OAuth 2.0 credentials** (Desktop app type)
5. Download credentials and save as `credentials.json`
6. Run authentication:

```bash
./venv/bin/python3 setup_drive.py
```

## Usage

### Basic Scraping Demo

```bash
./venv/bin/python3 src/demo.py
```

### Full Pipeline (with Drive Upload)

```bash
./venv/bin/python3 src/main.py --company Enlight
```

## Project Structure

```
financial_data_app/
├── src/
│   ├── scrapers/          # Web scrapers for IR sites and TASE
│   ├── drive_integration/ # Google Drive upload logic
│   ├── models/            # Data models and KPI calculations
│   └── utils/             # Helper functions
├── downloads/             # Local PDF storage
├── credentials.json       # Google OAuth credentials (not in git)
└── token.pickle          # Saved auth token (not in git)
```

## Supported Companies

- ✅ Enlight Renewable Energy
- 🔄 More coming soon...

## Google Drive Folder Structure

```
Drive Root/
└── [Company Name]/
    └── [Year]/
        └── [Period]/
            └── [Report PDFs]
```

Example:
```
Enlight_Renewable_Energy/
├── 2024/
│   ├── Q1/
│   │   └── Q1_2024_Earnings_Release.pdf
│   ├── Q2/
│   └── Annual/
└── 2025/
    └── Q1/
```
