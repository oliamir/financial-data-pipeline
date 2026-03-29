/**
 * @process finance-pipeline-rebuild
 * @description Complete rebuild of the Financial Data Pipeline v3 with quality-gated phases
 * @inputs { projectDir: string, planFile: string }
 * @outputs { success: boolean, phases: object }
 */

import { defineTask } from '@a5c-ai/babysitter-sdk';

/**
 * Financial Data Pipeline v3 — Full Rebuild Process
 *
 * 9-phase quality-gated iterative build:
 * Phase 1: Foundation (Poetry, models, config, storage, utils, CLI skeleton)
 * Phase 2: AI Layer (providers, registry, router)
 * Phase 3: Document Sources (TASE, IR, discovery, manual, coordinator)
 * Phase 4: Pipeline Core (orchestrator, download, parse, events, terminal dashboard)
 * Phase 5: Excel Model Builder (9 sheets, formulas, charts, KPIs)
 * Phase 6: Investment Memo (generator, renderer, market research, 13 sections)
 * Phase 7: Google Drive (upload, folder structure)
 * Phase 8: Web Dashboard (Flask, API, WebSocket, pages)
 * Phase 9: Scheduler & Polish (job queue, stall detection, cron, E2E tests)
 *
 * Each phase follows: Plan → Execute → Verify → Fix (convergence loop)
 */
export async function process(inputs, ctx) {
  const {
    projectDir = '/Users/amiroliker/Library/CloudStorage/GoogleDrive-oliamir@gmail.com/My Drive/Apps/finance',
    planFile = '/Users/amiroliker/.claude/plans/snappy-swinging-rabbit.md'
  } = inputs;

  const phases = [
    {
      id: 'phase-1-foundation',
      name: 'Foundation',
      description: 'Poetry project setup, Pydantic models, config loader, storage layer, utils, CLI skeleton, test infrastructure',
      tasks: [
        'Initialize Poetry project with pyproject.toml and all dependencies (pydantic, typer, playwright, google-generativeai, ollama, anthropic, openai, openpyxl, flask, flask-socketio, rich, pdfplumber, pandas, etc.)',
        'Create all Pydantic v2 data models in src/models/: company.py (Company, CompanyType enum), document.py (DocumentMetadata, DocumentType), financial.py (FinancialPeriod, IncomeStatement ~25 items, BalanceSheet ~30 items, CashFlow ~25 items, PerShareData), kpi.py (KPIMetrics with .calculate() classmethod for margins, ratios, growth, valuation multiples), memo.py (InvestmentMemo with 13 sections, Scenario, Risk, Catalyst), research.py (MarketResearch, SWOT, CompSet, IndustryTrend), job.py (PipelineJob, StepResult, StepName enum)',
        'Create config/ directory with companies.yaml (with company_type: us_traded|tase_traded|private), providers.yaml (with routing table), settings.yaml. Create src/config/loader.py and settings.py for YAML loading + validation',
        'Create src/storage/paths.py (centralized path conventions for data/companies/<slug>/) and file_manager.py (CRUD for company artifacts)',
        'Create src/utils/: pdf.py (PDF text extraction + financial page scoring heuristic from v1), json_fix.py (accounting notation + comma number fixing from v1), currency.py (conversion helpers), logging.py (structured logging)',
        'Create CLI skeleton with Typer: cli/main.py, cli/commands/list_cmd.py, cli/commands/status.py. Wire up finance list and finance status commands',
        'Create .env.example, .gitignore (include venv/, .env, downloads/, output/, logs/, __pycache__/, *.pyc, token.pickle, credentials.json)',
        'Set up tests/ with conftest.py, tests/unit/test_models.py, tests/unit/test_kpi_calculations.py, tests/unit/test_json_fix.py',
        'Create src/__init__.py and src/__main__.py entry point'
      ],
      verification: 'Run: cd projectDir && poetry install && poetry run python -m pytest tests/unit/ -v && poetry run python -m cli.main list --help && poetry run python -m cli.main status --help. All must pass. Verify all model files exist and import correctly.',
      maxIterations: 3
    },
    {
      id: 'phase-2-ai-layer',
      name: 'AI Layer',
      description: 'AI provider abstraction with Gemini, Ollama, Anthropic, OpenAI + task router with dynamic override',
      tasks: [
        'Create src/ai/base.py with BaseProvider ABC: async generate_text(), async generate_with_document(), async generate_with_search(), async health_check(), async list_models()',
        'Create src/ai/gemini.py: GeminiProvider using google.generativeai SDK. Supports PDF upload via genai.upload_file(), search grounding, retries with backoff for 429 errors',
        'Create src/ai/ollama.py: OllamaProvider using ollama.Client. Auto-detect installed models via ollama.list(), preconfigured model list (qwen2.5, llama3.1, mistral), pdfplumber text extraction for documents',
        'Create src/ai/anthropic.py: AnthropicProvider using anthropic SDK. Native PDF support via base64-encoded documents. Port from code/src/intelligence/llm_client.py._call_anthropic()',
        'Create src/ai/openai.py: OpenAIProvider using openai SDK. pdfplumber text extraction fallback. Port from code/src/intelligence/llm_client.py._call_openai()',
        'Create src/ai/registry.py: ProviderRegistry - loads from providers.yaml, health checks, model listing, provider lookup by name',
        'Create src/ai/router.py: TaskRouter with AITaskType enum (CLASSIFY, EXTRACT, VALIDATE, MEMO, MARKET_RESEARCH, WEB_RESEARCH), configurable routing table (task -> provider chain), fallback chains, runtime override_provider() method for dashboard',
        'Create tests/unit/test_router.py with mock providers testing routing logic, fallback, override'
      ],
      verification: 'Run: poetry run python -c "from src.ai.base import BaseProvider; from src.ai.gemini import GeminiProvider; from src.ai.ollama import OllamaProvider; from src.ai.anthropic import AnthropicProvider; from src.ai.openai import OpenAIProvider; from src.ai.registry import ProviderRegistry; from src.ai.router import TaskRouter, AITaskType; print(\'All AI imports OK\')" && poetry run python -m pytest tests/unit/test_router.py -v',
      maxIterations: 3
    },
    {
      id: 'phase-3-sources',
      name: 'Document Sources',
      description: 'TASE scraper, IR website scraper, IR auto-discovery, manual source, coordinator',
      tasks: [
        'Create src/sources/base.py with BaseSource ABC: async discover(company, years_back) -> list[DocumentMetadata], async download(doc, output_dir) -> str|None',
        'Create src/sources/tase.py: TASESource - port from src/scrapers/tase.py. Playwright headless Chromium, paginated TASE Maya scraping, Hebrew keyword matching, PDF download with validation, 120s timeout',
        'Create src/sources/ir_website.py: IRWebsiteSource - port from src/scrapers/ir_generic.py. Two-phase discovery (heuristic CSS + LLM fallback), scoring system, pagination handling',
        'Create src/sources/ir_profiles.py: Platform CSS profiles - port from src/scrapers/ir_profiles.py (Q4, Notified, WordPress, generic)',
        'Create src/sources/ir_discovery.py: IRDiscoverySource - NEW. Use Gemini with search grounding to find company IR website URL given company name + ticker. Return discovered URL for use by IRWebsiteSource',
        'Create src/sources/manual.py: ManualSource - NEW. Import files from a local directory (manual_files_dir in company config). Copy PDFs to data/companies/<slug>/reports/. For private companies',
        'Create src/sources/coordinator.py: SourceCoordinator - resolve sources by company_type (US->IRDiscovery+IRWebsite, TASE->TASESource+IRWebsite, Private->ManualSource), retry logic, cross-source dedup, health checks'
      ],
      verification: 'Run: poetry run python -c "from src.sources.base import BaseSource; from src.sources.tase import TASESource; from src.sources.ir_website import IRWebsiteSource; from src.sources.ir_discovery import IRDiscoverySource; from src.sources.manual import ManualSource; from src.sources.coordinator import SourceCoordinator; print(\'All source imports OK\')"',
      maxIterations: 3
    },
    {
      id: 'phase-4-pipeline',
      name: 'Pipeline Core',
      description: 'Pipeline orchestrator, download + parse steps, progress events, CLI run command, terminal dashboard',
      tasks: [
        'Create src/progress/events.py: EventBus with pub/sub (publish, subscribe), PipelineEvent model (event_type, job_id, company_slug, step, message, progress_pct, timestamp, data)',
        'Create src/progress/tracker.py: ProgressTracker (per-company, per-step progress tracking)',
        'Create src/tasks/classify.py: Document classification task with prompt template. 5 categories: FINANCIAL_REPORT, PRESENTATION, IMMEDIATE_REPORT, LEGAL_DOCUMENT, OTHER',
        'Create src/tasks/extract.py: Financial data extraction task. Expanded extraction prompt covering full ~25 Income Statement + ~30 Balance Sheet + ~25 Cash Flow line items. JSON response parsing with json_fix utilities. Heuristic quality check',
        'Create src/tasks/validate.py: Extraction validation task. Cross-check extraction against source document using second provider. Correction logging',
        'Create src/pipeline/steps/download.py: Step 1 - wraps SourceCoordinator.discover_and_download(). Emits progress events per document',
        'Create src/pipeline/steps/parse.py: Step 2 - for each unprocessed doc: classify -> if financial: extract -> validate -> produce FinancialPeriod + KPIMetrics. Emits progress events',
        'Create src/pipeline/orchestrator.py: PipelineOrchestrator - runs steps in sequence, supports running subset of steps, emits events, creates PipelineJob',
        'Create cli/commands/run.py: finance run <slug> --step X --provider Y --batch high --reprocess --dry-run --years N',
        'Create cli/dashboard.py: Rich terminal dashboard with per-company progress bars, status table (company, type, priority, download count, parse progress, metrics, memo), auto-refresh watch mode, --tier and --company filters'
      ],
      verification: 'Run: poetry run python -m cli.main run --help && poetry run python -m cli.main dashboard --help && poetry run python -c "from src.pipeline.orchestrator import PipelineOrchestrator; from src.pipeline.steps.download import execute as dl; from src.pipeline.steps.parse import execute as parse; from src.progress.events import EventBus; print(\'Pipeline imports OK\')"',
      maxIterations: 3
    },
    {
      id: 'phase-5-excel',
      name: 'Excel Model Builder',
      description: 'Professional multi-sheet Excel financial model with formulas, charts, and formatting',
      tasks: [
        'Create src/excel/styles.py: All openpyxl style definitions - INPUT_FONT (blue), FORMULA_FONT (black), LINK_FONT (green), named styles for headers, section headers, subtotals, grand totals. Number formats: currency (negatives in parens, zeros as dashes), percentages, multiples, per-share',
        'Create src/excel/formulas.py: Excel formula generation helpers - cell reference builders, cross-sheet references, growth rate formulas, margin formulas, ratio formulas',
        'Create src/excel/sheets/cover.py: Cover sheet - company name, ticker, exchange, analyst, date, version',
        'Create src/excel/sheets/assumptions.py: Assumptions sheet - all hard-coded inputs (growth rates, margins, tax rates, WACC inputs), yellow-highlighted input cells',
        'Create src/excel/sheets/income_statement.py: Income Statement sheet - ~25 line items, historical periods as columns, blue font for inputs, calculated margins below, growth rates, freeze panes, proper formatting',
        'Create src/excel/sheets/balance_sheet.py: Balance Sheet sheet - ~30 line items (Current/Non-Current Assets, Current/Non-Current Liabilities, Equity), proper indentation and section headers',
        'Create src/excel/sheets/cash_flow.py: Cash Flow Statement sheet - ~25 line items (CFO indirect method, CFI, CFF), FCF calculated at bottom',
        'Create src/excel/sheets/ratios.py: Ratios & KPIs sheet - profitability (margins, ROE, ROA, ROIC), leverage (D/E, Net Debt/EBITDA, interest coverage), liquidity (current, quick), working capital (DSO, DIO, DPO, CCC), valuation multiples',
        'Create src/excel/sheets/dcf.py: DCF Valuation sheet - UFCF build, WACC calculation, terminal value (Gordon Growth + Exit Multiple), enterprise value bridge, implied share price, sensitivity table (WACC vs terminal growth)',
        'Create src/excel/sheets/comps.py: Comparable Companies sheet - company rows with market data + operating metrics + valuation multiples, summary statistics (mean, median, high, low), implied valuation row',
        'Create src/excel/sheets/dashboard.py: Summary Dashboard sheet with charts (revenue trend combo, margin evolution, EPS trend, FCF, capital structure pie)',
        'Create src/excel/charts.py: Chart creation helpers using openpyxl BarChart, LineChart, PieChart',
        'Create src/excel/builder.py: ExcelModelBuilder orchestrator - takes Company + list[FinancialPeriod] + list[KPIMetrics] + CompSet, calls each sheet builder, saves workbook',
        'Create src/pipeline/steps/model.py: Step 3 - builds Excel model from extracted data, emits progress events',
        'Create tests/unit/test_excel_builder.py: Test cell references, formula strings, style application, workbook structure'
      ],
      verification: 'Run: poetry run python -m pytest tests/unit/test_excel_builder.py -v && poetry run python -c "from src.excel.builder import ExcelModelBuilder; print(\'Excel builder imports OK\')" && verify a test .xlsx can be generated with sample data',
      maxIterations: 4
    },
    {
      id: 'phase-6-memo',
      name: 'Investment Memo',
      description: 'AI-generated investment memo with market research and 13 professional sections',
      tasks: [
        'Create src/tasks/market_research.py: Market research AI tasks - market_sizing (TAM/SAM/SOM), competitor_positioning (comparison table), industry_trends (tailwinds/headwinds), swot_analysis (actionable, data-backed), comparable_company_analysis (trading comps). Each returns structured data',
        'Create src/tasks/web_research.py: Web search research task - uses Gemini search grounding to find real-time market data, news, competitor info. Returns structured research results',
        'Create src/tasks/memo_writer.py: Investment memo generation task. Per-section AI prompts: executive_summary, company_overview, industry_analysis, competitive_positioning, management_governance, financial_analysis, valuation, scenario_analysis (bull 25%/base 50%/bear 25%), risks_mitigants, catalysts_timeline, open_questions. Senior Investment Analyst role. Uses extracted financials + market research',
        'Create src/memo/generator.py: MemoGenerator - orchestrates AI calls: first market research, then web research, then per-section memo generation. Assembles InvestmentMemo model',
        'Create src/memo/renderer.py: MemoRenderer - converts InvestmentMemo to professional Markdown. Header with recommendation badge, tables for scenarios/risks/financials, callout boxes for key insights, properly formatted sections',
        'Create src/memo/sections/: Individual section renderers (header.py, executive_summary.py, company_overview.py, industry_analysis.py, competitive.py, management.py, financial_analysis.py, valuation.py, scenarios.py, risks.py, catalysts.py, open_questions.py, appendix.py)',
        'Create src/pipeline/steps/memo.py: Step 4 - generates memo from extracted data + research, renders to Markdown, saves to data/companies/<slug>/Investment_Memo.md',
        'Create tests/unit/test_memo_renderer.py: Test Markdown output contains all 13 sections, tables are properly formatted, scenario probabilities sum to ~100%'
      ],
      verification: 'Run: poetry run python -m pytest tests/unit/test_memo_renderer.py -v && poetry run python -c "from src.memo.generator import MemoGenerator; from src.memo.renderer import MemoRenderer; print(\'Memo imports OK\')"',
      maxIterations: 3
    },
    {
      id: 'phase-7-drive',
      name: 'Google Drive',
      description: 'Google Drive upload with OAuth 2.0 and organized folder structure',
      tasks: [
        'Create src/storage/drive.py: DriveUploader - port from code/src/drive_integration/drive_uploader.py. OAuth 2.0 authentication (credentials.json + token.pickle), folder hierarchy creation: Company Name/Financial_Model.xlsx, Company Name/Investment_Memo.md, Company Name/2025-Q1/*.pdf. Folder caching to avoid duplicate API calls',
        'Create src/pipeline/steps/upload.py: Step 5 - upload all artifacts to Google Drive. Financial_Model.xlsx and Investment_Memo.md go in company root folder, downloaded PDFs go in period subfolders (e.g., 2025-Q1/)',
        'Add finance run --skip-upload flag to cli/commands/run.py'
      ],
      verification: 'Run: poetry run python -c "from src.storage.drive import DriveUploader; from src.pipeline.steps.upload import execute; print(\'Drive imports OK\')"',
      maxIterations: 2
    },
    {
      id: 'phase-8-web-dashboard',
      name: 'Web Dashboard',
      description: 'Flask + SocketIO web dashboard with real-time progress and provider selection',
      tasks: [
        'Create web/app.py: Flask + SocketIO app. Mount API routes and WebSocket handlers. Serve static files and Jinja2 templates',
        'Create web/api/routes.py: REST API endpoints - GET /api/companies (list with status), GET /api/companies/<slug> (detail), GET /api/companies/<slug>/model (download xlsx), GET /api/companies/<slug>/memo (render md), POST /api/run (start job with steps + provider overrides), POST /api/run/batch (batch job), GET /api/jobs (running/recent), GET /api/providers (status + health), GET /api/providers/ollama/models (available models), POST /api/providers/<name>/test (test connectivity)',
        'Create web/api/websocket.py: WebSocket handler for real-time progress events. Subscribe to EventBus, emit PipelineEvent to connected clients',
        'Create web/templates/dashboard.html: Main dashboard page - summary cards (total companies, docs downloaded, models generated, memos completed), company table with live progress bars (htmx + WebSocket), action buttons per row (Run, View), batch run controls',
        'Create web/templates/company.html: Company detail page - metadata, pipeline step statuses, downloaded documents list, financial data preview, links to download .xlsx and view .md',
        'Create web/templates/run.html: Run controls page - company selector, step checkboxes, provider override dropdowns per task type (extract, validate, memo, research), Run/Run Batch buttons, live output console',
        'Create web/templates/settings.html: Settings page - provider configuration, default routing table, health check buttons, Ollama model detection',
        'Create web/static/css/ and web/static/js/ with basic styling',
        'Add cli/commands/web.py: finance web command to start the web server'
      ],
      verification: 'Run: poetry run python -c "from web.app import create_app; app = create_app(); print(\'Web app created OK\')" && poetry run python -m cli.main web --help',
      maxIterations: 3
    },
    {
      id: 'phase-9-scheduler-polish',
      name: 'Scheduler & Polish',
      description: 'Job queue, stall detection, cron scheduling, E2E tests, error hardening, documentation',
      tasks: [
        'Create src/scheduler/job_queue.py: Priority job queue - insert jobs with priority, pop highest priority, persistent queue state (JSON file)',
        'Create src/scheduler/monitor.py: Process monitor - stall detection (configurable timeout), auto-restart failed jobs, sequential completion enforcement, periodic health checks',
        'Create src/scheduler/cron.py: Cron scheduling support - schedule runs by priority tier (high=daily, low=weekly), start/stop daemon',
        'Add cli/commands/scheduler.py: finance scheduler start|status|stop commands',
        'Create cli/commands/validate.py: finance validate [slug] --all - check Financial_Model.xlsx exists and has data, Investment_Memo.md exists and has all 13 sections, meta.json is valid',
        'Create cli/commands/company.py: finance company add (interactive), finance company edit <slug>, finance company remove <slug>',
        'Create cli/commands/provider.py: finance provider status (health check all), finance provider models ollama (list available models)',
        'Create tests/integration/test_pipeline_e2e.py: End-to-end test - run full pipeline for a test company in dry-run mode, verify job model populated correctly',
        'Update CLAUDE.md with new project structure, commands, architecture',
        'Final error handling review: ensure all providers handle timeouts, rate limits, network errors gracefully'
      ],
      verification: 'Run: poetry run python -m pytest tests/ -v && poetry run python -m cli.main --help && poetry run python -m cli.main list && poetry run python -m cli.main provider status 2>&1. All CLI commands should show help text. All tests should pass.',
      maxIterations: 3
    }
  ];

  const phaseResults = [];

  // ============================================================================
  // SEQUENTIAL PHASE EXECUTION
  // ============================================================================

  for (let i = 0; i < phases.length; i++) {
    const phase = phases[i];

    // ----- PLAN -----
    const planResult = await ctx.task(planPhaseTask, {
      phase,
      projectDir,
      planFile,
      previousPhases: phaseResults,
      phaseIndex: i + 1,
      totalPhases: phases.length
    });

    // Breakpoint: Review plan before execution
    await ctx.breakpoint({
      question: `Review plan for Phase ${i + 1}/${phases.length}: "${phase.name}". Approve to proceed with implementation?`,
      title: `Phase ${i + 1} Plan Review: ${phase.name}`,
      context: {
        runId: ctx.runId,
        files: [
          { path: `artifacts/${phase.id}-PLAN.md`, format: 'markdown', label: 'Phase Plan' }
        ]
      }
    });

    // ----- EXECUTE WITH CONVERGENCE LOOP -----
    let iteration = 0;
    let phaseCompleted = false;
    let lastExecutionResult = null;
    let lastVerificationResult = null;

    while (!phaseCompleted && iteration < phase.maxIterations) {
      iteration++;

      // Execute
      const executeResult = await ctx.task(executePhaseTask, {
        phase,
        projectDir,
        planResult,
        iteration,
        previousFeedback: lastVerificationResult?.feedback || null,
        phaseIndex: i + 1,
        totalPhases: phases.length
      });
      lastExecutionResult = executeResult;

      // Verify
      const verifyResult = await ctx.task(verifyPhaseTask, {
        phase,
        projectDir,
        executeResult,
        iteration,
        phaseIndex: i + 1,
        totalPhases: phases.length
      });
      lastVerificationResult = verifyResult;

      if (verifyResult.passed) {
        phaseCompleted = true;
      } else if (iteration < phase.maxIterations) {
        // Breakpoint: Decide whether to continue iterating
        await ctx.breakpoint({
          question: `Phase ${i + 1} "${phase.name}" iteration ${iteration} verification failed. Issues: ${verifyResult.issues?.join(', ') || 'see report'}. Continue to iteration ${iteration + 1}?`,
          title: `Phase ${i + 1} Verification Failed (iter ${iteration})`,
          context: {
            runId: ctx.runId,
            files: [
              { path: `artifacts/${phase.id}-VERIFY-${iteration}.md`, format: 'markdown', label: 'Verification Report' }
            ]
          }
        });
      }
    }

    // Store result
    phaseResults.push({
      phase: phase.id,
      name: phase.name,
      completed: phaseCompleted,
      iterations: iteration,
      execution: lastExecutionResult,
      verification: lastVerificationResult
    });

    // Commit after successful phase
    if (phaseCompleted) {
      await ctx.task(commitPhaseTask, {
        phase,
        projectDir,
        phaseIndex: i + 1
      });
    }
  }

  // ============================================================================
  // FINAL REVIEW
  // ============================================================================

  const allPassed = phaseResults.every(r => r.completed);

  await ctx.breakpoint({
    question: `All ${phases.length} phases complete. ${allPassed ? 'All passed!' : 'Some phases had issues.'} Review final state?`,
    title: 'Rebuild Complete',
    context: {
      runId: ctx.runId,
      files: [
        { path: 'artifacts/FINAL-REPORT.md', format: 'markdown', label: 'Final Report' }
      ]
    }
  });

  return {
    success: allPassed,
    phases: phaseResults,
    artifacts: {
      finalReport: 'artifacts/FINAL-REPORT.md'
    },
    metadata: {
      processId: 'finance-pipeline-rebuild',
      timestamp: ctx.now()
    }
  };
}

// ============================================================================
// TASK DEFINITIONS
// ============================================================================

export const planPhaseTask = defineTask('plan-phase', (args, taskCtx) => ({
  kind: 'agent',
  title: `Plan: ${args.phase.name} (Phase ${args.phaseIndex}/${args.totalPhases})`,
  description: `Plan implementation for phase: ${args.phase.description}`,

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python architect planning implementation of a financial data pipeline',
      task: `Plan the detailed implementation for Phase ${args.phaseIndex}: ${args.phase.name}`,
      context: {
        phase: args.phase,
        projectDir: args.projectDir,
        planFile: args.planFile,
        previousPhases: args.previousPhases
      },
      instructions: [
        `Read the master plan at ${args.planFile} for full architecture context`,
        `Research the project directory at ${args.projectDir} to understand current state`,
        `This is Phase ${args.phaseIndex}/${args.totalPhases}: ${args.phase.name}`,
        `Phase description: ${args.phase.description}`,
        `Tasks to implement: ${JSON.stringify(args.phase.tasks)}`,
        'For each task, plan exact file paths, class/function signatures, and key implementation details',
        'Reference existing code to port from the legacy codebase where applicable',
        'Consider dependencies on previously completed phases',
        'Write the plan to artifacts/' + args.phase.id + '-PLAN.md',
        'Return a summary of the plan'
      ],
      outputFormat: 'JSON with summary (string), fileCount (number), keyDecisions (array of strings)'
    },
    outputSchema: {
      type: 'object',
      required: ['summary'],
      properties: {
        summary: { type: 'string' },
        fileCount: { type: 'number' },
        keyDecisions: { type: 'array', items: { type: 'string' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['planning', args.phase.id]
}));

export const executePhaseTask = defineTask('execute-phase', (args, taskCtx) => ({
  kind: 'agent',
  title: `Execute: ${args.phase.name} (Phase ${args.phaseIndex}/${args.totalPhases}, iter ${args.iteration})`,
  description: `Implement phase: ${args.phase.description}`,

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python developer implementing a financial data pipeline rebuild',
      task: `Implement Phase ${args.phaseIndex}: ${args.phase.name} (iteration ${args.iteration})`,
      context: {
        phase: args.phase,
        projectDir: args.projectDir,
        planResult: args.planResult,
        iteration: args.iteration,
        previousFeedback: args.previousFeedback
      },
      instructions: [
        `Working directory: ${args.projectDir}`,
        `Implement all tasks for Phase ${args.phaseIndex}: ${args.phase.name}`,
        args.iteration > 1 ? `IMPORTANT: This is iteration ${args.iteration}. Fix issues from previous verification: ${args.previousFeedback}` : 'This is the first implementation attempt.',
        `Phase tasks: ${JSON.stringify(args.phase.tasks)}`,
        'Write clean, well-structured Python code following the project architecture',
        'Use Pydantic v2 for all data models',
        'Use async/await for all IO-bound operations',
        'Follow the patterns and conventions defined in the master plan',
        'Ensure all imports are correct and modules are properly connected',
        'Create __init__.py files for all packages',
        'Write unit tests for key functionality',
        'Return a summary of files created and modified'
      ],
      outputFormat: 'JSON with filesCreated (array), filesModified (array), summary (string), testsCreated (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['filesCreated', 'summary'],
      properties: {
        filesCreated: { type: 'array', items: { type: 'string' } },
        filesModified: { type: 'array', items: { type: 'string' } },
        summary: { type: 'string' },
        testsCreated: { type: 'array', items: { type: 'string' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['execution', args.phase.id, `iteration-${args.iteration}`]
}));

export const verifyPhaseTask = defineTask('verify-phase', (args, taskCtx) => ({
  kind: 'agent',
  title: `Verify: ${args.phase.name} (Phase ${args.phaseIndex}/${args.totalPhases}, iter ${args.iteration})`,
  description: `Verify phase implementation: ${args.phase.verification}`,

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior QA engineer verifying implementation of a financial data pipeline',
      task: `Verify Phase ${args.phaseIndex}: ${args.phase.name} (iteration ${args.iteration})`,
      context: {
        phase: args.phase,
        projectDir: args.projectDir,
        executeResult: args.executeResult,
        iteration: args.iteration
      },
      instructions: [
        `Working directory: ${args.projectDir}`,
        `Run the verification command: ${args.phase.verification}`,
        'Check that all specified files exist and have correct content',
        'Verify imports work correctly',
        'Run any unit tests and check they pass',
        'Check code quality: proper typing, docstrings, error handling',
        'If issues are found, document them clearly for the next iteration',
        `Write verification report to artifacts/${args.phase.id}-VERIFY-${args.iteration}.md`,
        'Return whether the phase passed and any issues found'
      ],
      outputFormat: 'JSON with passed (boolean), issues (array of strings), feedback (string), testsRun (number), testsPassed (number)'
    },
    outputSchema: {
      type: 'object',
      required: ['passed'],
      properties: {
        passed: { type: 'boolean' },
        issues: { type: 'array', items: { type: 'string' } },
        feedback: { type: 'string' },
        testsRun: { type: 'number' },
        testsPassed: { type: 'number' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['verification', args.phase.id, `iteration-${args.iteration}`]
}));

export const commitPhaseTask = defineTask('commit-phase', (args, taskCtx) => ({
  kind: 'agent',
  title: `Commit: ${args.phase.name} (Phase ${args.phaseIndex})`,
  description: 'Create git commit for completed phase',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Developer committing completed work',
      task: `Create a git commit for completed Phase ${args.phaseIndex}: ${args.phase.name}`,
      context: {
        phase: args.phase,
        projectDir: args.projectDir
      },
      instructions: [
        `Working directory: ${args.projectDir}`,
        'Stage all new and modified files for this phase (exclude .env, credentials.json, token.pickle, __pycache__, venv/)',
        `Create a commit with message: "Phase ${args.phaseIndex}: ${args.phase.name}\\n\\n${args.phase.description}"`,
        'Return the commit hash'
      ],
      outputFormat: 'JSON with commitHash (string), filesCommitted (number)'
    },
    outputSchema: {
      type: 'object',
      required: ['commitHash'],
      properties: {
        commitHash: { type: 'string' },
        filesCommitted: { type: 'number' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },

  labels: ['commit', args.phase.id]
}));
