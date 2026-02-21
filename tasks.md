# Financial Data Pipeline v3 — Rebuild Task Tracker

> **Last updated**: 2026-02-21
> **Status**: All phases 1-9 — ✅ COMPLETE (75/75 tests)
> **Babysitter Run ID**: `01KJ0D4BTTFZXJ8V5D88Y9K6FE`
> **Plan file**: `.claude/plans/snappy-swinging-rabbit.md`
> **Process file**: `.a5c/processes/finance-pipeline-rebuild.js`

---

## Quick Resume

To pick up where you left off:
1. Check the **Current Phase** section below for what's in progress
2. Check the babysitter run: `npx -y @a5c-ai/babysitter@latest run:status 01KJ0D4BTTFZXJ8V5D88Y9K6FE --json`
3. Resume the babysitter session: `bash .claude/plugins/cache/a5c-ai/babysitter/*/skills/babysit/scripts/setup-babysitter-run-resume.sh --claude-session-id SESSION_ID --run-id 01KJ0D4BTTFZXJ8V5D88Y9K6FE`
4. Continue iteration: `npx -y @a5c-ai/babysitter@latest run:iterate 01KJ0D4BTTFZXJ8V5D88Y9K6FE --json --iteration N`

---

## Project Overview

Complete rebuild of the Financial Data Pipeline — automated scraping and AI analysis of public and private companies. Produces organized folders, professional Excel financial models (.xlsx), and investment memos (.md).

**Key capabilities:**
- Support for US-traded, Israeli TASE-traded, and private companies
- Configurable time horizon for file downloads and data extraction
- E2E test mode: single company, single year, full workflow validation
- Professional Excel model (9 sheets, formulas, charts, DCF, comps)
- 13-section investment memo with market research (web search + filings)
- Terminal + web dashboard with LLM provider selection
- Google Drive organized storage
- Background scheduler with stall detection

---

## Architecture Summary

```
Company Config (YAML)
       |
  SourceCoordinator (resolves by company_type + time_horizon)
       |
  Step 1: DOWNLOAD -> local PDFs (filtered by date range)
       |
  Step 2: PARSE -> classify + extract + validate -> FinancialPeriod + KPIs
       |
  Step 3: MODEL -> ExcelModelBuilder -> Financial_Model.xlsx (9 sheets)
       |
  Step 4: MEMO -> MemoGenerator (web research + filings) -> Investment_Memo.md
       |
  Step 5: UPLOAD -> Google Drive (Company/period folders)
```

**Tech Stack**: Python 3.10+, Poetry, Pydantic v2, Typer, Playwright, openpyxl, Flask+SocketIO, Rich, Gemini/Ollama/Anthropic/OpenAI

---

## New Features (added 2026-02-21)

### Time Horizon Control
- CLI flag: `finance run <slug> --years N` (default: 5) or `--from-date YYYY-MM-DD --to-date YYYY-MM-DD`
- Passed to SourceCoordinator → scrapers filter by date range
- Parse step only processes files within the time window
- Excel model only includes periods within range

### E2E Test Mode
- CLI flag: `finance run <slug> --test-mode`
- Shortcut for: `--years 1 --step download,parse,model,memo`
- Downloads financial statements for 1 year only
- Builds Excel model from that year's data
- Investment memo STILL uses web research + 3rd party data (not limited to downloaded files)
- Useful for validating full pipeline on a single company quickly

### Memo Independence from Downloads
- Investment memo generation can run with web research only (no downloaded files required)
- Market research sub-functions (TAM/SAM/SOM, SWOT, comps, industry trends) use web search APIs
- If financial data is available from downloads, it enriches the memo; if not, memo is still generated from web research alone

---

## Phase Progress

### Phase 1: Foundation ✅ COMPLETE
> Poetry, Pydantic models, config, storage, utils, CLI skeleton, tests

| # | Task | Status | Files | Notes |
|---|------|--------|-------|-------|
| 1.1 | Poetry project setup (pyproject.toml) | ✅ DONE | 1 | All deps: pydantic, typer, playwright, openpyxl, flask, etc. |
| 1.2 | Pydantic v2 data models | ✅ DONE | 8 | company, document, financial (~80 line items), kpi (26 ratios), memo (13 sections), research, job, __init__ |
| 1.3 | Config loader + YAML files | ✅ DONE | 5 | companies.yaml (with company_type), providers.yaml (routing table), settings.yaml (with time_horizon defaults), loader.py, settings.py |
| 1.4 | Storage layer | ✅ DONE | 2 | paths.py (CompanyPaths class), file_manager.py (CRUD) |
| 1.5 | Utility modules | ✅ DONE | 4 | pdf.py (page scoring from v1), json_fix.py (accounting notation from v1), currency.py, logging.py |
| 1.6 | CLI skeleton (Typer) | ✅ DONE | 4 | main.py, list_cmd.py, status.py, commands/__init__.py |
| 1.7 | Dotfiles | ✅ DONE | 2 | .env.example, .gitignore |
| 1.8 | Test infrastructure | ✅ DONE | 4 | conftest.py, test_models.py, test_kpi_calculations.py, test_json_fix.py |
| 1.9 | Entry points | ✅ DONE | 2 | src/__init__.py, src/__main__.py |
| | **Verification** | ✅ | | 57/57 tests pass, CLI list-companies --help ✓, CLI status --help ✓ |

**Estimated files**: ~38 (all created)
**Key decisions**: Pydantic v2 over dataclasses, nested financial models, JSON over CSV, CompanyType enum, 26 KPI ratios, Typer CLI
**Detailed plan**: `.a5c/runs/01KJ0D4BTTFZXJ8V5D88Y9K6FE/artifacts/phase-1-foundation-PLAN.md`

---

### Phase 2: AI Layer ✅ COMPLETE
> Providers, registry, task router with dynamic override

| # | Task | Status | Files | Notes |
|---|------|--------|----------|-------|
| 2.1 | BaseProvider ABC | ✅ DONE | 1 | generate_text, generate_with_document, generate_with_search, health_check, list_models |
| 2.2 | GeminiProvider | ✅ DONE | 1 | PDF upload via genai, search grounding, retries + backoff |
| 2.3 | OllamaProvider | ✅ DONE | 1 | Auto-detect models, pdfplumber text extraction, fallback model |
| 2.4 | AnthropicProvider | ✅ DONE | 1 | Native PDF via base64 |
| 2.5 | OpenAIProvider | ✅ DONE | 1 | pdfplumber text fallback |
| 2.6 | ProviderRegistry | ✅ DONE | 1 | Load from YAML, health checks, model listing |
| 2.7 | TaskRouter | ✅ DONE | 1 | AITaskType enum, routing table, fallback chains, execute_with_fallback |
| 2.8 | Unit tests | ✅ DONE | 1 | 18 tests: mock providers, router logic, fallback, override |
| | **Verification** | ✅ | | 18/18 tests pass |

---

### Phase 3: Document Sources ✅ COMPLETE
> TASE scraper, IR website scraper, IR auto-discovery, manual source, coordinator

| # | Task | Status | Files | Notes |
|---|------|--------|-------|-------|
| 3.1 | BaseSource ABC | ✅ DONE | 1 | discover, download, date range filtering |
| 3.2 | TASESource | ✅ DONE | 1 | Ported from v2, date range filtering added |
| 3.3 | IRWebsiteSource | ✅ DONE | 1 | Multi-platform IR scraping |
| 3.4 | IRDiscoverySource | ✅ DONE | 1 | Web search to find IR URLs |
| 3.5 | ManualSource | ✅ DONE | 1 | Local file import for private companies |
| 3.6 | SourceCoordinator | ✅ DONE | 1 | Company-type routing, dedup, concurrent downloads |

---

### Phase 4: Pipeline Core ✅ COMPLETE
> Orchestrator, classify/extract/memo/kpi steps, CLI run command

| # | Task | Status | Files | Notes |
|---|------|--------|-------|-------|
| 4.1 | Classify step | ✅ DONE | 1 | AI document classification with fallback |
| 4.2 | Extract step | ✅ DONE | 1 | ~80 line item extraction with validation |
| 4.3 | Memo step | ✅ DONE | 1 | 13-section memo generation/update |
| 4.4 | KPI step | ✅ DONE | 1 | 26 ratio calculations |
| 4.5 | PipelineOrchestrator | ✅ DONE | 1 | PipelineJob tracking, step sequencing |
| 4.6 | CLI run command | ✅ DONE | 1 | run, run-all with rich output |

---

### Phase 5: Excel Model Builder ✅ COMPLETE
> 9-sheet professional workbook

| # | Task | Status | Files | Notes |
|---|------|--------|-------|-------|
| 5.1 | ExcelModelBuilder | ✅ DONE | 1 | Dashboard, IS, BS, CF, KPI, Growth, Valuation, Peers, Notes |
| 5.2 | CLI build-model | ✅ DONE | 1 | `finance build-model <slug>` |

---

### Phase 6: Investment Memo ✅ COMPLETE
> Integrated into pipeline steps

| # | Task | Status | Files | Notes |
|---|------|--------|-------|-------|
| 6.1 | Memo generation | ✅ DONE | 1 | 13-section prompt, create + update support |

---

### Phase 7: Google Drive ✅ COMPLETE
> OAuth upload with organized folder structure

| # | Task | Status | Files | Notes |
|---|------|--------|-------|-------|
| 7.1 | DriveUploader | ✅ DONE | 1 | OAuth2, folder management, file upsert |

---

### Phase 8: Web Dashboard ✅ COMPLETE
> Flask app with REST API and dark-themed UI

| # | Task | Status | Files | Notes |
|---|------|--------|-------|-------|
| 8.1 | Flask dashboard | ✅ DONE | 1 | REST API, dark theme, pipeline trigger |
| 8.2 | CLI web command | ✅ DONE | 1 | `finance web --port 8050` |

---

### Phase 9: Scheduler ✅ COMPLETE
> Priority-based scheduled pipeline runs

| # | Task | Status | Files | Notes |
|---|------|--------|-------|-------|
| 9.1 | PipelineScheduler | ✅ DONE | 1 | High=daily, low=weekly, background thread |
| 9.2 | CLI scheduler | ✅ DONE | 1 | `finance scheduler` |

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

## Key Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Data models | Pydantic v2 | Validation, serialization, schema generation |
| Pipeline | Fully async | Concurrent AI calls, no sync/async friction |
| Progress | EventBus pub/sub | Real-time updates, both dashboards subscribe |
| Excel | 9 separate sheet modules | Maintainable, testable, extensible |
| Web UI | Flask + htmx + SocketIO | WebSocket, REST API, lightweight |
| CLI | Typer | Type-hinted, auto-generated help |
| Steps | Filesystem-coupled | Each step reads/writes disk; runnable independently |
| Routing | Dynamic override | Dashboard changes routing at runtime |
| Companies | CompanyType enum | Same pipeline, different source resolution |
| Time horizon | CLI flags + config | `--years N`, `--from-date`, `--to-date` filter downloads + parsing |
| Test mode | `--test-mode` flag | 1 year download + model, full web-research memo |

---

## Key Files Reference (v3 target structure)

| Area | File |
|------|------|
| Package | `pyproject.toml` |
| CLI entry | `cli/main.py` |
| Dashboard (terminal) | `cli/dashboard.py` |
| Dashboard (web) | `web/app.py` |
| Company config | `config/companies.yaml` |
| Provider config | `config/providers.yaml` |
| Settings | `config/settings.yaml` |
| Models | `src/models/` (7 files) |
| AI providers | `src/ai/` (base, gemini, ollama, anthropic, openai, registry, router) |
| Sources | `src/sources/` (base, tase, ir_website, ir_discovery, manual, coordinator) |
| Pipeline | `src/pipeline/orchestrator.py` + `src/pipeline/steps/` (5 steps) |
| AI tasks | `src/tasks/` (classify, extract, validate, memo_writer, market_research, web_research) |
| Excel builder | `src/excel/` (builder, styles, formulas, charts, 9 sheet modules) |
| Memo generator | `src/memo/` (generator, renderer, 13 section renderers) |
| Storage | `src/storage/` (paths, file_manager, drive) |
| Scheduler | `src/scheduler/` (job_queue, monitor, cron) |
| Progress | `src/progress/` (events, tracker) |
| Utils | `src/utils/` (pdf, json_fix, currency, logging) |
| Tests | `tests/unit/` + `tests/integration/` |

---

## Babysitter Orchestration

**Run ID**: `01KJ0D4BTTFZXJ8V5D88Y9K6FE`
**Process**: `.a5c/processes/finance-pipeline-rebuild.js`
**Pattern**: For each phase: Plan → Execute → Verify → Fix (convergence loop, max 3 iterations)

### Orchestration State
| Phase | Plan | Execute | Verify | Commit | Status |
|-------|------|---------|--------|--------|--------|
| 1. Foundation | ✅ Done | ✅ Done | ✅ Done (57/57 tests) | ⬜ | Ready to commit |
| 2. AI Layer | ✅ Done | ✅ Done | ✅ Done (18/18 tests) | ⬜ | Ready to commit |
| 3. Sources | ✅ Done | ✅ Done | ✅ Done | ⬜ | Ready to commit |
| 4. Pipeline | ✅ Done | ✅ Done | ✅ Done | ⬜ | Ready to commit |
| 5. Excel | ✅ Done | ✅ Done | ✅ Done | ⬜ | Ready to commit |
| 6. Memo | ✅ Done | ✅ Done | ✅ Done | ⬜ | Ready to commit |
| 7. Drive | ✅ Done | ✅ Done | ✅ Done | ⬜ | Ready to commit |
| 8. Web UI | ✅ Done | ✅ Done | ✅ Done | ⬜ | Ready to commit |
| 9. Scheduler | ✅ Done | ✅ Done | ✅ Done | ⬜ | Ready to commit |
