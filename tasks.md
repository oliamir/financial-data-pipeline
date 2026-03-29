# Financial Data Pipeline v3 — Task Tracker

> **Last updated**: 2026-02-21
> **Status**: All 14 critical gaps RESOLVED | Phases 1-12 COMPLETE | 4 minor partial items remaining (P4-P7)
> **Plan file**: `.claude/plans/snappy-swinging-rabbit.md`
> **Repo**: `github.com/oliamir/financial-data-pipeline` (main branch)

---

## Quick Resume

To pick up where you left off:
1. Check **Phase 10: Post-Rebuild** and **Gap Analysis** sections below
2. Pipeline background run may still be active: `pgrep -f "cli.main run sofwave"`
3. Ollama must be running: `ollama serve` (model: qwen2.5:7b)
4. Dashboard: `python3 -m cli.main dashboard sofwave --watch 2`

---

## Project Overview

Complete rebuild of the Financial Data Pipeline — automated scraping and AI analysis of public and private companies. Produces organized folders, professional Excel financial models (.xlsx), and investment memos (.md).

**Key capabilities:**
- Support for US-traded, Israeli TASE-traded, and private companies
- Configurable time horizon for file downloads and data extraction
- Professional Excel model (9 sheets, formulas, charts, DCF, comps)
- 13-section investment memo with market research (web search + filings)
- Terminal + web dashboard
- Google Drive organized storage
- Background scheduler
- Ollama local LLM support (qwen2.5:7b) with Gemini fallback

**Tech Stack**: Python 3.10+, Pydantic v2, Typer, Playwright, openpyxl, Flask, Rich, Gemini/Ollama/Anthropic/OpenAI

---

## Phase Progress

### Phase 1: Foundation ✅ COMPLETE
> Poetry, Pydantic models, config, storage, utils, CLI skeleton, tests

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.1 | Poetry project setup (pyproject.toml) | ✅ DONE | All deps |
| 1.2 | Pydantic v2 data models | ✅ DONE | company, document, financial (~80 line items), kpi (26 ratios), memo (13 sections), research, job |
| 1.3 | Config loader + YAML files | ✅ DONE | companies.yaml, providers.yaml, settings.yaml, loader.py, settings.py |
| 1.4 | Storage layer | ✅ DONE | paths.py (CompanyPaths + module helpers), file_manager.py |
| 1.5 | Utility modules | ✅ DONE | pdf.py, json_fix.py, currency.py, logging.py |
| 1.6 | CLI skeleton (Typer) | ✅ DONE | main.py, list_cmd.py, status.py |
| 1.7 | Dotfiles | ✅ DONE | .env.example, .gitignore |
| 1.8 | Test infrastructure | ✅ DONE | conftest.py, test_models.py, test_kpi_calculations.py, test_json_fix.py |
| | **Verification** | ✅ | 57/57 tests pass |

---

### Phase 2: AI Layer ✅ COMPLETE
> Providers, registry, task router with dynamic override

| # | Task | Status | Notes |
|---|------|--------|-------|
| 2.1 | BaseProvider ABC | ✅ DONE | generate_text, generate_with_document, generate_with_search, health_check, list_models |
| 2.2 | GeminiProvider | ✅ DONE | PDF upload via genai, search grounding, retries + backoff |
| 2.3 | OllamaProvider | ✅ DONE | Auto-detect models, pdfplumber text extraction, fallback model |
| 2.4 | AnthropicProvider | ✅ DONE | Native PDF via base64 |
| 2.5 | OpenAIProvider | ✅ DONE | pdfplumber text fallback |
| 2.6 | ProviderRegistry | ✅ DONE | Load from YAML, health checks, model listing |
| 2.7 | TaskRouter | ✅ DONE | AITaskType enum, routing table, fallback chains |
| 2.8 | Unit tests | ✅ DONE | 18/18 tests pass |

---

### Phase 3: Document Sources ✅ COMPLETE

| # | Task | Status | Notes |
|---|------|--------|-------|
| 3.1 | BaseSource ABC | ✅ DONE | discover, download, date range filtering |
| 3.2 | TASESource | ✅ DONE | Playwright pagination, Hebrew keywords |
| 3.3 | IRWebsiteSource | ✅ DONE | Multi-platform IR scraping |
| 3.4 | IRDiscoverySource | ✅ DONE | Web search to find IR URLs |
| 3.5 | ManualSource | ✅ DONE | Local file import for private companies |
| 3.6 | SourceCoordinator | ✅ DONE | Company-type routing, dedup |

---

### Phase 4: Pipeline Core ✅ COMPLETE

| # | Task | Status | Notes |
|---|------|--------|-------|
| 4.1 | Classify step | ✅ DONE | AI classification with Hebrew keyword support |
| 4.2 | Extract step | ✅ DONE | ~80 line item extraction |
| 4.3 | Memo step | ✅ DONE | 13-section memo generation |
| 4.4 | KPI step | ✅ DONE | 26 ratio calculations |
| 4.5 | PipelineOrchestrator | ✅ DONE | PipelineJob tracking, step sequencing |
| 4.6 | CLI run command | ✅ DONE | run, run-all |

---

### Phase 5: Excel Model Builder ✅ COMPLETE

| # | Task | Status | Notes |
|---|------|--------|-------|
| 5.1 | ExcelModelBuilder | ✅ DONE | 9 sheets: Dashboard, IS, BS, CF, KPI, Growth, Valuation, Peers, Notes |
| 5.2 | CLI build-model | ✅ DONE | `finance build-model <slug>` |

---

### Phase 6: Investment Memo ✅ COMPLETE

| # | Task | Status | Notes |
|---|------|--------|-------|
| 6.1 | Memo generation | ✅ DONE | 13-section prompt, create + update |
| 6.2 | MemoRenderer | ✅ DONE | Markdown output, badges, tables, revision history |
| 6.3 | Initial Research | ✅ DONE | 5 strategic prompts: competitors, TAM/SAM/SOM, SWOT, market intel |

---

### Phase 7: Google Drive ✅ COMPLETE

| # | Task | Status | Notes |
|---|------|--------|-------|
| 7.1 | DriveUploader | ✅ DONE | OAuth2, folder management, file upsert |

---

### Phase 8: Web Dashboard ✅ COMPLETE

| # | Task | Status | Notes |
|---|------|--------|-------|
| 8.1 | Flask dashboard | ✅ DONE | REST API, dark theme, pipeline trigger |
| 8.2 | CLI web command | ✅ DONE | `finance web --port 8050` |
| 8.3 | WebSocket (SocketIO) | ✅ DONE | Real-time event forwarding via EventBus bridge |
| 8.4 | Provider selector UI | ✅ DONE | Per-company provider + step dropdowns |
| 8.5 | Run controls | ✅ DONE | Start pipeline from dashboard with provider/step selection |
| 8.6 | Live events tab | ✅ DONE | Real-time event log with type, slug, message |
| 8.7 | Provider status tab | ✅ DONE | Provider health + task routing display |
| 8.8 | Progress API | ✅ DONE | `/api/progress`, `/api/events`, `/api/scheduler/status` |
| 8.9 | Dashboard UI buttons | ✅ DONE | Per-company Download and AI Scrape simple action buttons |
| 8.10 | Live UI Progress | ✅ DONE | Real-time progress bars for tracked companies |

---

### Phase 9: Scheduler ✅ COMPLETE

| # | Task | Status | Notes |
|---|------|--------|-------|
| 9.1 | PipelineScheduler | ✅ DONE | Priority job queue, stall detection, cron |
| 9.2 | CLI scheduler | ✅ DONE | `finance scheduler start\|status` |
| 9.3 | JobQueue | ✅ DONE | Priority-ordered, thread-safe enqueue/dequeue |
| 9.4 | StallDetector | ✅ DONE | Configurable timeout, auto-restart, max retries |
| 9.5 | CronSchedule | ✅ DONE | 5-field cron expressions, next_run() calculation |
| 9.6 | EventBus integration | ✅ DONE | Scheduler events published to EventBus |

---

### Phase 10: Post-Rebuild Hardening ✅ COMPLETE
> Ollama setup, Pydantic fixes, Rich dashboard, TASE Maya downloader

| # | Task | Status | Notes |
|---|------|--------|-------|
| 10.1 | Install Ollama + pull qwen2.5:7b | ✅ DONE | Local LLM on M2 MacBook Air 16GB |
| 10.2 | Switch to Ollama-only config | ✅ DONE | No Google API key required for extraction |
| 10.3 | Download 66 Sofwave PDFs (3yr) | ✅ DONE | TASE Maya headless scrape |
| 10.4 | Fix Pydantic models for 7B output | ✅ DONE | memo.py: optional fields, dict→string coercion, probability alias |
| 10.5 | Fix FinancialPeriod validators | ✅ DONE | Handle None currency/units/period_type from LLM |
| 10.6 | Tune extraction prompts for Hebrew | ✅ DONE | Simplified prompt, Hebrew keywords for IS/BS/CF |
| 10.7 | Tune classify prompts for Hebrew | ✅ DONE | Hebrew doc type keywords, better guidance |
| 10.8 | Build Rich terminal dashboard | ✅ DONE | 4-panel layout, activity log, auto-refresh, filesystem polling |
| 10.9 | Wire dashboard into Typer CLI | ✅ DONE | `finance dashboard [slug] --watch N --tier high` |
| 10.10 | Add module-level path helpers | ✅ DONE | company_dir(), reports_dir(), meta_json(), etc. in paths.py |
| 10.11 | TASE Maya headless downloader | ✅ DONE | `finance tase-fetch` with incremental, date range, headless |
| 10.12 | MemoRenderer + versioning | ✅ DONE | Revision history, thesis impact tracking |
| 10.13 | Initial Research step (Gemini) | ✅ DONE | Deep strategic research via Gemini 3.1 Pro |
| 10.14 | Install gh CLI | ✅ DONE | ~/bin/gh, authenticated |
| 10.15 | Push all code to GitHub | ✅ DONE | 4 commits on main |

---

### Phase 11: AI Parsing Run 🔄 IN PROGRESS
> Running Sofwave 66 PDFs through Ollama qwen2.5:7b

| # | Task | Status | Notes |
|---|------|--------|-------|
| 11.1 | Classify + extract 66 PDFs | 🔄 ~30% | 18/66 processed, pipeline running in background |
| 11.2 | Financial periods extracted | 🔄 | 5 periods so far: FY 2024, Q1 2023, H1 2024, Q3 2024, FY 2022 |
| 11.3 | Investment Memo generated | ✅ DONE | 38KB markdown, buy recommendation |
| 11.4 | Build Excel model from extracted data | ⬜ TODO | After parsing completes |
| 11.5 | Validate extraction quality | ⬜ TODO | Cross-check numbers, identify parsing errors |

---

## Gap Analysis: Plan vs Implementation

### All Critical Gaps — RESOLVED ✅

| # | Feature | Status | Resolution |
|---|---------|--------|------------|
| ~~G1~~ | Market Research Task System | ✅ EXISTS | In `src/pipeline/steps/` (classify, extract, memo, kpi, initial_research) |
| G2 | Progress/Events System | ✅ DONE | `src/progress/__init__.py`: EventBus (singleton pub/sub), ProgressTracker (per-company), PipelineEvent |
| G3 | CLI: company add/edit/remove | ✅ DONE | `finance company add\|edit\|remove` with YAML config updates |
| G4 | CLI: provider status/models | ✅ DONE | `finance provider status\|models` with health checks + Ollama auto-detect |
| G5 | CLI: validate [slug] | ✅ DONE | `finance validate [slug]` — checks reports, financials, KPIs, memo, model |
| G6 | CLI: --test-mode | ✅ DONE | `finance run <slug> --test-mode` — 1yr download + model + full memo |
| G7 | CLI: --step | ✅ DONE | `finance run <slug> --step download,parse,model,memo` |
| G8 | CLI: --reprocess | ✅ DONE | `finance run <slug> --reprocess` — re-analyzes processed files |
| G9 | Web Dashboard: WebSocket | ✅ DONE | Flask-SocketIO with EventBus bridge for real-time updates |
| G10 | Web Dashboard: Provider selector | ✅ DONE | Per-company provider dropdown in dashboard |
| G11 | Web Dashboard: Run controls | ✅ DONE | Start pipeline with provider/step selection from dashboard |
| G12 | Scheduler: Job queue | ✅ DONE | Priority-ordered JobQueue with thread-safe operations |
| G13 | Scheduler: Stall detection | ✅ DONE | StallDetector with timeout, auto-restart, max retries |
| G14 | Scheduler: Cron expressions | ✅ DONE | CronSchedule with 5-field expressions, per-tier scheduling |

### Remaining Partial Implementations

| # | Feature | What Exists | What's Missing |
|---|---------|-------------|----------------|
| ~~P1~~ | ~~Excel charts~~ | ✅ DONE | Revenue trend bar + margin evolution line charts on Dashboard |
| ~~P2~~ | ~~Excel peer comparison~~ | ✅ DONE | Structured comp table with headers, placeholder peers, summary stats |
| ~~P3~~ | ~~Excel color coding~~ | ✅ DONE | Blue=inputs, black=formulas, green=crossref, yellow=assumptions |
| P4 | **Excel DCF sheet** | "Valuation" sheet exists | Full DCF with sensitivity table not yet implemented |
| P5 | **Memo per-section generators** | Single prompt generates full memo | Plan called for per-section AI calls with separate prompts |
| P6 | **Drive retry logic** | Upload works | No exponential backoff on failure |
| P7 | **Source health checks** | Coordinator routes by type | No per-source availability probing |

---

### Phase 12: Gap Resolution ✅ COMPLETE
> All 14 critical gaps from plan audit resolved

| # | Task | Status | Notes |
|---|------|--------|-------|
| 12.1 | EventBus pub/sub system | ✅ DONE | `src/progress/__init__.py` — singleton, typed events, history |
| 12.2 | ProgressTracker per-company | ✅ DONE | Step lifecycle tracking, progress %, active registry |
| 12.3 | Pipeline runner: --step filter | ✅ DONE | `VALID_STEPS` set, `_should_run_step()` gating |
| 12.4 | Pipeline runner: --reprocess | ✅ DONE | Re-reads all PDFs, not just unprocessed |
| 12.5 | Pipeline runner: ProgressTracker integration | ✅ DONE | Emits events during all pipeline stages |
| 12.6 | CLI --step, --test-mode, --reprocess flags | ✅ DONE | Full argument parsing + run_pipeline() wiring |
| 12.7 | CLI `provider status\|models` | ✅ DONE | Health checks, routing table, Ollama model listing |
| 12.8 | CLI `validate [slug]` | ✅ DONE | Reports, financials, KPIs, memo, model validation |
| 12.9 | CLI `company add\|edit\|remove` | ✅ DONE | YAML config CRUD operations |
| 12.10 | CLI `scheduler start\|status` | ✅ DONE | Job queue display, cron schedule display |
| 12.11 | Scheduler: JobQueue | ✅ DONE | Priority-ordered, cancel, clear_completed |
| 12.12 | Scheduler: StallDetector | ✅ DONE | Configurable timeout, restart counter, auto-recovery |
| 12.13 | Scheduler: CronSchedule | ✅ DONE | 5-field parser, next_run() calculation |
| 12.14 | Web: WebSocket (SocketIO) | ✅ DONE | EventBus bridge, real-time event forwarding |
| 12.15 | Web: Provider selector + run controls | ✅ DONE | Per-company dropdown, step selector, background run |
| 12.16 | Web: Live events tab | ✅ DONE | Real-time event log with filtering |
| 12.17 | Web: Progress/Events/Scheduler API | ✅ DONE | `/api/progress`, `/api/events`, `/api/scheduler/status` |
| 12.18 | Excel: Dashboard charts | ✅ DONE | Revenue trend bar + margin evolution line charts |
| 12.19 | Excel: Color coding applied | ✅ DONE | Blue/black/green/yellow convention throughout |
| | **Verification** | ✅ | 102/103 tests pass (1 pre-existing universe search bug) |

---

## Company Registry (18 companies)

| Company | Slug | Type | Priority | TASE ID | US Ticker | Sector |
|---------|------|------|----------|---------|-----------|--------|
| Enlight Renewable Energy | enlight | tase_traded | high | 720 | ENLT (NASDAQ) | renewable_energy |
| Energix | energix | tase_traded | high | 1581 | - | renewable_energy |
| Apollo Power | apollo | tase_traded | high | 1074 | - | renewable_energy |
| Sofwave Medical | sofwave | tase_traded | high | 1886 | SOFW (NASDAQ) | medical_devices |
| Brainsway | brainsway | tase_traded | high | 1386 | BWAY (NASDAQ) | medical_devices |
| Rimoni Industries | rimoni | tase_traded | high | 76 | - | industrial |
| Azrieli Group | azrieli | tase_traded | high | 1420 | - | real_estate |
| Cellcom Israel | cellcom | tase_traded | high | 2066 | - | telecom |
| Ludan Engineering | ludan | tase_traded | high | 1050 | - | engineering |
| TLSYS | tlsys | tase_traded | high | 354 | - | technology |
| Ormat Technologies | ormat | tase_traded | low | 2250 | ORA (NYSE) | renewable_energy |
| Doral Renewable Energy | doral | tase_traded | low | 1801 | - | renewable_energy |
| Ellomay Capital | ellomay | tase_traded | low | 2101 | ELLO (NYSE) | renewable_energy |
| Augwind Energy Tech | augwind | tase_traded | low | 1473 | - | renewable_energy |
| Electreon Wireless | electreon | tase_traded | low | 368 | - | renewable_energy |
| Nofar Energy | nofar | tase_traded | low | 1831 | - | renewable_energy |
| Meshek Energy | meshek | tase_traded | low | 1803 | - | renewable_energy |
| Sunflower Sustainable | sunflower | tase_traded | low | 1062 | - | renewable_energy |

---

## Key Files Reference

| Area | File |
|------|------|
| Package | `pyproject.toml` |
| CLI entry | `cli/main.py` |
| Dashboard (terminal) | `cli/dashboard.py` |
| Dashboard (web) | `src/web/__init__.py` |
| Company config | `config/companies.yaml` |
| Provider config | `config/providers.yaml` |
| Settings | `config/settings.yaml` |
| Models | `src/models/` (company, document, financial, kpi, memo, research, job) |
| AI providers | `src/ai/` (base, gemini, ollama_provider, anthropic_provider, openai_provider, registry, task_router, router) |
| Sources | `src/sources/` (base, tase, ir_website, ir_discovery, manual, coordinator) |
| Pipeline | `src/pipeline/runner.py` + `src/pipeline/steps/` (classify, extract, memo, initial_research) |
| Memo renderer | `src/memo/renderer.py` |
| Excel builder | `src/excel/__init__.py` |
| Storage | `src/storage/` (paths, file_manager) |
| Drive | `src/drive/__init__.py` |
| Scheduler | `src/scheduler/__init__.py` (JobQueue, StallDetector, CronSchedule) |
| Progress/Events | `src/progress/__init__.py` (EventBus, ProgressTracker, PipelineEvent) |
| TASE downloader | `src/tase_maya/downloader.py` |
| Tests | `tests/unit/` + `tests/live/` |
