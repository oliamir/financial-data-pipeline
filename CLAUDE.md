# CLAUDE.md

## Project Overview

Financial Data Pipeline — automated scraping and AI analysis of company reports from the Tel Aviv Stock Exchange (TASE Maya). Produces investment memos and financial models for Israeli public companies (primarily renewable energy sector).

## Tech Stack

- **Language**: Python 3.10+
- **Scraping**: Playwright (headless Chromium), BeautifulSoup, Requests
- **AI Providers**: Google Gemini (primary), Ollama (local), Anthropic, OpenAI (disabled)
- **Data**: pandas, pdfplumber, openpyxl
- **Storage**: Local filesystem + optional Google Drive upload
- **Config**: YAML (`config/companies.yaml`, `config/providers.yaml`), `.env` for API keys

## Project Structure

```
cli/                    # CLI entry point and dashboard
  main.py               # Unified CLI: run, status, list, validate, dashboard
  dashboard.py           # Terminal dashboard with progress bars
config/                 # YAML configuration
  companies.yaml         # Company registry (18 companies, priority tiers)
  providers.yaml         # AI provider config (Gemini, Ollama, Anthropic, OpenAI)
src/                    # Core library
  ai/                    # AI task router + provider abstraction
    router.py            # Ollama-first extraction, Gemini fallback/validation
    providers.py         # GeminiProvider, OllamaProvider (BaseProvider interface)
  models/                # Data models (FinancialMetric, InvestmentMemo, ReportMetadata)
  pipeline/              # Pipeline orchestrator (scrape -> download -> analyze -> store)
    orchestrator.py
  registry/              # Company registry loader + priority tiers
    company.py
    priority.py
  scrapers/              # Web scrapers
    tase.py              # TASE Maya Playwright scraper
    ir_generic.py        # Generic IR website scraper (heuristic + LLM)
    ir_profiles.py       # IR platform profiles (Q4, Notified, WordPress)
    coordinator.py       # Scraping coordinator with retries, health checks
  storage/               # File management + path conventions
    file_manager.py
    paths.py
  utils/
code/                   # Legacy codebase (v1 — has its own bin/, src/, tests/)
deploy/oracle-cloud/    # OCI deployment scripts
data/                   # Runtime data
downloads/              # Downloaded reports (gitignored)
tests/                  # Test files (integration/diagnostic style)
```

## Key Commands

```bash
# Activate venv first
source venv/bin/activate

# Run pipeline for a single company
python -m cli.main run --company sofwave

# Run all high-priority companies
python -m cli.main run --all --priority high

# Check status
python -m cli.main status

# List registered companies
python -m cli.main list

# Terminal dashboard
python -m cli.main dashboard

# Legacy entry points (in code/ directory)
python code/bin/run_pipeline.py --company Sofwave --provider google --model gemini-2.0-flash
python code/bin/robust_monitor.py
```

## Environment Variables

Required in `.env`:
- `GOOGLE_API_KEY` — Google Gemini API key (primary provider)

Optional:
- `ANTHROPIC_API_KEY` — Anthropic Claude (currently disabled)
- `OPENAI_API_KEY` — OpenAI (currently disabled)
- `OLLAMA_HOST` — Ollama endpoint (defaults to `http://localhost:11434`)

## Architecture Notes

- **Two codebases coexist**: `src/` is the v2 modular rewrite; `code/` is the v1 legacy code. New work should target `src/` and `cli/`.
- **AI routing**: The task router (`src/ai/router.py`) tries Ollama first for extraction, falls back to Gemini. Gemini is used for validation.
- **Company priority tiers**: High-priority companies get more thorough analysis. Defined in `config/companies.yaml`.
- **Scraping order**: For dual-listed companies, IR websites are scraped first; TASE Maya is the fallback.
- **Output artifacts per company**: `Investment_Memo.md`, `Financial_Model.csv`, organized report files.

## Common Patterns

- Company lookup by slug (lowercase, e.g., `sofwave`, `apollo`, `enlight`)
- All scrapers extend a base interface and return `ReportMetadata` objects
- AI providers implement `BaseProvider` with `generate()` method
- File paths centralized in `src/storage/paths.py`
- YAML config loaded at startup via registry classes

## Testing

Tests are integration/diagnostic-oriented (endpoint probing, Playwright flows, scraper verification). Not strict unit tests. Located in `tests/` and `code/tests/`.

```bash
# Run from project root
python -m pytest tests/
```

## Important Warnings

- **Never commit `.env`, `credentials.json`, or `token.pickle`** — these contain API keys and OAuth tokens
- `downloads/`, `output/`, and `logs/` are gitignored
- The `code/` directory is legacy; avoid adding new features there
- TASE scraper has intentional ~120s overall timeout (gets 6-8 pages per run)
