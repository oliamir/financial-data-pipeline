# Project Map: Financial Data Pipeline

## 1) What This Project Does

This project automates collection and AI analysis of company reports from the Tel Aviv Stock Exchange (TASE Maya), then produces:

- A living investment memo (`Investment_Memo.md`)
- A structured financial model (`Financial_Model.csv`)
- Organized local report archives (by company/year/period)
- Optional Google Drive uploads of downloaded files

Primary target companies are defined in `code/src/config/companies.py` and include firms like Sofwave and Apollo.

## 2) Core Workflow (End-to-End)

The operational pipeline is orchestrated by `code/bin/run_pipeline.py`:

1. Resolve company metadata from `RENEWABLE_COMPANIES`.
2. Decide whether to skip download based on recency marker (`.last_download_success`) unless forced.
3. Run download step: `code/src/download.py`.
4. Run analysis step: `code/src/analyze.py`.
5. Exit with non-zero code if any required stage fails.

## 3) Main Runtime Components

### 3.1 Orchestration Layer

- `code/bin/run_pipeline.py`
  - CLI entrypoint for single-company runs.
  - Supports flags for company, years, provider/model, fallback behavior, and agent persona.
  - Implements a 7-day download skip optimization using marker file.

- `code/bin/robust_monitor.py`
  - Long-running watchdog/queue manager.
  - Priority queue currently favors Sofwave over Apollo.
  - Detects stalls (no log update for 10+ minutes), kills/restarts jobs.
  - Enforces one active analysis process at a time.

- `code/run_all_companies.py`
  - Batch loop over all configured companies for download + upload.
  - Runs `src/download.py` directly per company.

### 3.2 Data Acquisition Layer

- `code/src/download.py`
  - Resolves company config (`tase_id`, optional `company_id`, optional IR URL).
  - Uses:
    - `EnlightScraper` for Enlight IR pages
    - `TasePlaywrightScraper` for TASE Maya company feed
  - Filters to a target year if a concrete year is passed.
  - Filters down to financial reports (`"FINANCIAL"` marker in period).
  - Downloads report files, then optionally uploads to Google Drive.

- `code/src/scrapers/tase_playwright_scraper.py`
  - Headless Playwright scraper for JS-rendered TASE pages.
  - Builds paginated URL requests with date range filters.
  - Extracts report card fields from `.feed-item-report`.
  - Uses keyword + link heuristics to flag financial reports.
  - Converts raw cards into `ReportMetadata`.
  - Downloads attachments with `expect_download`; has fallback logic for details-page PDF buttons.

- `code/src/scrapers/enlight_scraper.py`
  - Static HTML scraping of Enlight IR pages for PDF links.
  - Heuristic extraction for report year/period from text + URL.

- `code/src/scrapers/base_scraper.py`
  - Shared report model (`ReportMetadata`).
  - Generic direct HTTP download fallback with request headers.

### 3.3 AI Analysis Layer

- `code/src/analyze.py`
  - Scans downloaded files under company output directory.
  - For each file:
    - Classify document type.
    - If financial: extract structured metrics.
    - Update investment thesis memo.
    - Move file to `Financials/` or `Others/`.
  - Writes/updates:
    - `Investment_Memo.md`
    - `Financial_Model.csv`
  - Supports watch mode for continuous ingestion.

- `code/src/intelligence/llm_client.py`
  - Provider abstraction across Google, Anthropic, OpenAI, and Ollama.
  - Maintains provider key availability from env vars.
  - Supports fallback rotation when enabled.
  - Handles provider-specific file handling:
    - Google: native file upload
    - Anthropic: base64 document payload
    - OpenAI/Ollama: PDF text extraction path (via `pdfplumber`)

- `code/src/intelligence/classifier.py`
  - LLM-driven classification into:
    - Financial report
    - Presentation
    - Immediate report
    - Legal document
    - Other

- `code/src/intelligence/extractor.py`
  - LLM prompt for normalized JSON financial statement extraction.
  - Parses response JSON and returns parsed dict or error payload.

- `code/src/intelligence/thesis.py`
  - LLM prompt to update a full investment memo from current state + new document.
  - Enforces memo section structure in prompt.

- `code/src/intelligence/agent_manager.py`
  - Loads optional persona prompts from `.claude/agents/*.md`.
  - Used by `analyze.py` when `--agent` is provided.

### 3.4 External Storage Integration

- `code/src/drive_integration/drive_uploader.py`
  - Google OAuth authentication (`credentials.json`, `token.pickle`).
  - Creates nested folders and uploads files.
  - Includes folder-ID caching to reduce duplicate API lookups.

### 3.5 Operations / Observability Tools

- `code/bin/monitor_progress.py`: terminal dashboard for running status + file counts.
- `code/bin/check_status.py`: one-shot status snapshot (keys, processes, file stats).
- `code/bin/verify_completion.py`: checks final memo/model presence and size.
- `code/bin/compare_models.py`: rough throughput estimate from log files.

## 4) Data Model and Artifacts

### 4.1 In-Memory Model

`ReportMetadata` (`code/src/scrapers/base_scraper.py`) contains:

- company info (`company_name`, `year`, `period`)
- source + URL metadata
- optional HTTP headers / attachment descriptors
- local storage references (`local_path`, `local_paths`)
- optional Drive ID

### 4.2 Output Artifacts

For each company directory:

- `Investment_Memo.md`: narrative thesis that evolves report-by-report.
- `Financial_Model.csv`: appended tabular extraction output.
- Year/period folders containing downloaded files.
- Post-analysis routing:
  - `Financials/` for financial reports
  - `Others/` for non-financial files

## 5) Configuration and Dependencies

### 5.1 Company Registry

- `code/src/config/companies.py` maps friendly company names to:
  - `tase_id`
  - optional `company_id` (needed for web feed URLs)
  - `english_name`
  - optional IR URL

### 5.2 Environment Variables

Loaded via `.env` in analysis stage:

- `GOOGLE_API_KEY`
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`

### 5.3 Runtime Dependencies

Declared in `requirements.txt`:

- scraping/parsing: `playwright`, `requests`, `beautifulsoup4`, `pdfplumber`
- data: `pandas`, `openpyxl`
- LLM/API clients: `openai`, `ollama`, `google-api-python-client`, auth libs
- utility: `python-dotenv`

## 6) Test and Diagnostics Coverage

`code/tests/` is focused mainly on scraper/API behavior and TASE search/pagination experiments:

- endpoint probing
- date input/URL parameter behavior
- pagination and deep-page checks
- Playwright flow tests
- direct historical scrape verification

These files function more like integration diagnostics than isolated unit tests.

## 7) Effective Execution Paths

### Recommended

- Run with orchestrator monitor:
  - `python3 code/bin/robust_monitor.py`

### Manual single-company

- `python3 code/bin/run_pipeline.py --company Sofwave --provider google --model gemini-2.0-flash`

### One-off diagnostics

- `python3 code/bin/check_status.py`
- `python3 code/bin/verify_completion.py`

## 8) Current Design Notes / Caveats

- Path conventions are mixed in code (`output/...` and `downloads/...` both appear in different scripts), so monitor/verification scripts may not always observe artifacts produced by the latest pipeline path.
- Several status utilities are hardcoded for Sofwave/Apollo naming conventions.
- Report classification + extraction rely heavily on prompt outputs and heuristic filename/keyword logic.
- Test suite appears oriented to debugging real endpoints and browser flows, not strict CI-style deterministic unit coverage.

## 9) Quick File Map

- Orchestration: `code/bin/run_pipeline.py`, `code/bin/robust_monitor.py`
- Downloading: `code/src/download.py`
- Scrapers: `code/src/scrapers/*.py`
- Analysis: `code/src/analyze.py`
- LLM abstraction: `code/src/intelligence/llm_client.py`
- AI tasks: `code/src/intelligence/classifier.py`, `code/src/intelligence/extractor.py`, `code/src/intelligence/thesis.py`
- Personas: `code/src/intelligence/agent_manager.py`
- Drive upload: `code/src/drive_integration/drive_uploader.py`
- Tests/diagnostics: `code/tests/*.py`, `code/bin/*.py`
