# CLAUDE.md

## Project Overview

Financial Data Pipeline — automated scraping and AI analysis of company reports from the Tel Aviv Stock Exchange (TASE Maya). Produces investment memos and financial models for Israeli public companies (primarily renewable energy sector).

## Tech Stack

- **Language**: Python 3.10+
- **Scraping**: Playwright (headless Chromium), BeautifulSoup, Requests
- **AI Providers**: Google Gemini (primary), Ollama (local), Anthropic, OpenAI (disabled)
- **Data**: pandas, pdfplumber, openpyxl
- **Storage**: Local filesystem on Google Drive (auto-synced)
- **Config**: YAML (`config/companies.yaml`, `config/providers.yaml`), `.env` for API keys

## Project Structure

```
cli/                    # CLI entry point and dashboard
  main.py               # Unified CLI: run, status, list, validate, dashboard, web
  dashboard.py           # Terminal dashboard with progress bars
  commands/              # CLI command implementations
config/                 # YAML configuration
  companies.yaml         # Company registry (18 companies, priority tiers)
  providers.yaml         # AI provider config (Gemini, Ollama, Anthropic, OpenAI)
src/                    # Core library
  ai/                    # AI task router + provider abstraction
    registry.py          # ProviderRegistry — multi-provider manager
    task_router.py       # Ollama-first extraction, Gemini fallback/validation
    ollama_provider.py   # OllamaProvider (local LLM)
    gemini_provider.py   # GeminiProvider (Google API)
  config/                # Config loaders
  excel/                 # Excel financial model builder
  memo/                  # Investment memo renderer
  models/                # Pydantic data models (FinancialPeriod, InvestmentMemo, PipelineJob)
  pipeline/              # Pipeline orchestrator + step implementations
    runner.py            # Main orchestrator (scrape → parse → model → memo)
    steps/               # Individual pipeline steps (classify, extract, kpi, memo)
  progress/              # Real-time progress tracking via EventBus
  scheduler/             # Cron-style pipeline scheduler
  sources/               # Source coordinator (TASE + IR website discovery)
  storage/               # File management + path conventions
    file_manager.py      # CRUD for company artifacts
    paths.py             # Centralized path conventions
  tase_maya/             # TASE Maya headless scraper + downloader
  universe/              # TASE company universe management
  web/                   # Flask web dashboard (two-tab: Dashboard + Priority List)
  utils/                 # Logging, helpers
data/                   # Runtime data (gitignored, lives on Google Drive)
  companies/             # Per-company data: reports, financials, memos, models
  universe.json          # Full TASE company universe
  priority_list.json     # Priority company list
deploy/                 # Deployment scripts
tests/                  # Test files (integration/diagnostic style)
```

## Data Layout (per company)

All company data lives in `data/companies/<slug>/`:

```
data/companies/sofwave/
├── meta.json              # Scraping inventory & processed file tracker
├── financials.json        # Extracted financial periods
├── Financial_Model.xlsx   # Excel model
├── Investment_Memo.md     # Rendered markdown memo
├── memo.json              # Structured memo data
├── kpi.json               # Calculated KPI metrics
├── research.json          # Market research data
└── reports/               # Downloaded PDF reports
```

## Key Commands

```bash
# Activate venv first
source venv/bin/activate

# Run pipeline for a single company
python -m cli.main run sofwave

# Run all high-priority companies
python -m cli.main run-all --priority high

# Run specific pipeline steps
python -m cli.main run sofwave --step download,parse,model

# Check status
python -m cli.main status

# List registered companies
python -m cli.main list

# Web dashboard
python -m cli.main web

# Terminal dashboard
python -m cli.main dashboard

# TASE Maya standalone fetch
python -m cli.main tase-fetch --companies sofwave,enlight --years 3
```

## Environment Variables

Required in `.env`:
- `GOOGLE_API_KEY` — Google Gemini API key (primary provider)

Optional:
- `ANTHROPIC_API_KEY` — Anthropic Claude (currently disabled)
- `OPENAI_API_KEY` — OpenAI (currently disabled)
- `OLLAMA_HOST` — Ollama endpoint (defaults to `http://localhost:11434`)

## Architecture Notes

- **Single codebase**: `src/` is the active codebase; `cli/` is the entry point.
- **AI routing**: The task router (`src/ai/task_router.py`) tries Ollama first for extraction, falls back to Gemini. Gemini is used for validation and deep research.
- **Company priority tiers**: High-priority companies get more thorough analysis. Defined in `config/companies.yaml`.
- **Scraping order**: For dual-listed companies, IR websites are scraped first; TASE Maya is the fallback.
- **Output artifacts per company**: `Investment_Memo.md`, `Financial_Model.xlsx`, organized report files.
- **Storage on Google Drive**: The entire project folder is synced via Google Drive — no separate upload step needed.

## Pipeline Steps

1. `initial_research` — Web-based strategic research (Gemini deep thinking)
2. `download` — Discover & fetch reports from TASE Maya / IR websites
3. `parse` — Classify documents, extract financials, calculate KPIs (per PDF)
4. `model` — Build Excel financial model from extracted data
5. `memo` — Generate/update investment memo

## Common Patterns

- Company lookup by slug (lowercase, e.g., `sofwave`, `apollo`, `enlight`)
- All scrapers extend a base interface and return `ReportMetadata` objects
- AI providers implement `BaseProvider` with `generate()` method
- File paths centralized in `src/storage/paths.py`
- YAML config loaded at startup via registry classes

## Testing

```bash
python -m pytest tests/
```

## Important Warnings

- **Never commit `.env`** — contains API keys
- `data/` and `logs/` are gitignored
- TASE scraper has intentional ~120s overall timeout (gets 6-8 pages per run)
