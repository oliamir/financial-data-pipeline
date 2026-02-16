# Financial Data Pipeline — Task Tracker

> Last updated: 2026-02-16

---

## ✅ Completed

### Core Pipeline
- [x] TASE headless Playwright scraper (`tase_playwright_scraper.py`)
- [x] Enlight IR scraper with archive page support (2022–2025)
- [x] Report download pipeline (`download.py`)
- [x] Google Drive upload integration (`drive_uploader.py`)
- [x] Batch processing for all companies (`run_all_companies.py`)
- [x] Sector-wide data collection for TASE renewable energy companies

### AI Analysis
- [x] Multi-provider LLM client (Google Gemini, Anthropic, OpenAI, Ollama)
- [x] Fallback/rotation mechanism across providers
- [x] Document classifier (Financial / Presentation / Immediate / Legal / Other)
- [x] Financial data extractor (Revenue, Net Income, EBITDA → JSON)
- [x] Investment thesis/memo generator (`thesis.py`)
- [x] Watch mode for continuous ingestion (`analyze.py --watch`)
- [x] Agent persona support (`agent_manager.py`)
- [x] Smart model routing (Gemini for financials, lighter models for others)

### Orchestration & Monitoring
- [x] `run_pipeline.py` — CLI entrypoint with company/provider/model flags
- [x] `robust_monitor.py` — watchdog with priority queue & auto-recovery
- [x] `monitor_progress.py` — real-time terminal dashboard
- [x] `check_status.py` — API key & process diagnostics
- [x] `verify_completion.py` — output integrity checks
- [x] `compare_models.py` — model benchmark / throughput comparison

### Companies Processed
- [x] Sofwave Medical — full scrape + AI analysis
- [x] Apollo Power — full scrape + AI analysis
- [x] Enlight Renewable Energy — historical data (52+ reports, 2022–2025)

### Deployment
- [x] Oracle Cloud deployment scripts (`deploy/oracle-cloud/`)
  - [x] `create-instance.sh` — VM provisioning
  - [x] `setup.sh` — environment setup
  - [x] `cron-setup.sh` — scheduled execution
  - [x] `sync.sh` — code sync
  - [x] `retry-create.sh` — retry logic

---

## 🔄 In Progress / Needs Attention

### Scraper Refinements
- [ ] Refine TASE CSS selectors for better report extraction
- [ ] Fix HTTP2 protocol errors (currently disabled HTTP2 as workaround)
- [ ] Improve financial report tagging/detection accuracy
- [ ] Test scraper with all 12 registered companies beyond Sofwave/Apollo/Enlight

### Data Quality
- [ ] Validate downloaded PDFs are actual financial reports (not screenshots)
- [ ] Add data validation and quality checks for extracted financial metrics
- [ ] Resolve mixed path conventions (`output/` vs `downloads/`) across scripts
- [ ] Ensure monitor/verification scripts work for all companies (currently hardcoded for Sofwave/Apollo)

### Company Coverage
- [ ] Run full pipeline for remaining companies:
  - [ ] Energix
  - [ ] Ormat Technologies
  - [ ] Doral Renewable Energy
  - [ ] Ellomay Capital
  - [ ] Augwind Energy
  - [ ] Electreon Wireless
  - [ ] Nofar Energy
  - [ ] Meshek Energy
  - [ ] Sunflower Sustainable Investments
- [ ] Set up IR URLs for companies that have them (currently `None`)

---

## 📋 Planned / Backlog

### Short Term
- [ ] Register for TASE Data Hub API (official API access for reliable data)
- [ ] Implement API-based TASE data collection (replace/supplement scraper)
- [ ] Add automated scheduling (cron on Oracle Cloud or local)
- [ ] Build proper test suite (current tests are integration diagnostics, not CI-ready)

### Medium Term
- [ ] Build web dashboard for data visualization
- [ ] Add email/notification alerts for new reports
- [ ] Implement structured output validation for LLM responses
- [ ] Create company comparison reports across the sector

### Long Term
- [ ] ML-based anomaly detection on financial metrics
- [ ] Expand beyond TASE (SEC, other exchanges)
- [ ] Historical trend and valuation models
- [ ] Real-time market data integration (TASE premium API)

---

## 🐛 Known Issues

| Issue | Status | Notes |
|-------|--------|-------|
| `ERR_HTTP2_PROTOCOL_ERROR` on TASE | Workaround | HTTP2 disabled; works but not ideal |
| Path conventions mixed (`output/` vs `downloads/`) | Open | Monitor scripts may miss artifacts |
| Status utilities hardcoded for Sofwave/Apollo | Open | Need to generalize for all companies |
| Tests are diagnostic, not unit tests | Open | No CI/CD coverage |
| Gemini API rate limits during bulk analysis | Known | Ollama fallback in place |

---

## 📁 Key Files Reference

| Area | File |
|------|------|
| Pipeline entry | `code/bin/run_pipeline.py` |
| Watchdog | `code/bin/robust_monitor.py` |
| Downloader | `code/src/download.py` |
| TASE Scraper | `code/src/scrapers/tase_playwright_scraper.py` |
| Analyzer | `code/src/analyze.py` |
| LLM client | `code/src/intelligence/llm_client.py` |
| Company registry | `code/src/config/companies.py` |
| Deployment | `deploy/oracle-cloud/` |
