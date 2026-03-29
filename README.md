# Financial Data Pipeline 🚀

An autonomous AI agent ensuring sequential, robust processing of financial reports from the Tel Aviv Stock Exchange (TASE).

## Features
*   **Multi-Provider AI**: Supports Google Gemini, Anthropic Claude, OpenAI, and local Ollama (Llama/DeepSeek).
*   **Robust Monitoring**: Auto-restarts stalled jobs and enforces priority queuing.
*   **Smart Scraper**: Headless browser scraping of TASE Maya reports.
*   **Financial Analysis**: Automatically generates Investment Memos and Financial Models (CSV).

## Setup

1.  **Prerequisites**:
    *   Python 3.10+
    *   Chrome/Chromium (for Playwright)
    *   [Optional] Ollama (for local AI)

2.  **Installation**:
    ```bash
    # Clone repo
    git clone https://github.com/oliamir/financial-data-pipeline
    cd financial-data-pipeline

    # Create venv
    python3 -m venv venv
    source venv/bin/activate

    # Install dependencies
    pip install -r requirements.txt
    playwright install chromium
    ```

3.  **Configuration**:
    *   Create a `.env` file with your API keys:
        ```env
        GOOGLE_API_KEY=your_key
        ANTHROPIC_API_KEY=your_key
        ```

## Usage

### TASE Maya Event Downloader (Headless)
Fetch financial/immediate reports directly from Maya event pages.
```bash
# Priority pilot list (apollo, brainsway, sofwave, azrieli, ludan)
./venv/bin/python -m cli.main tase-fetch --years 1

# Manual backfill window (up to 10 years)
./venv/bin/python -m cli.main tase-fetch --companies apollo --years 5 --no-incremental

# Incremental manual update (default behavior)
./venv/bin/python -m cli.main tase-fetch --companies apollo --incremental

# All configured TASE companies
./venv/bin/python -m cli.main tase-fetch --all-companies --years 1
```
Output is versioned under `downloads/tase_maya/<company>/<YYYY-Q#>/` with `.json` metadata sidecars.

### 1. The Robust Monitor (Recommended) 🛡️
The best way to run the system. It manages the queue, handles crashes, and enforces priority (Sofwave > Apollo).
```bash
nohup python3 bin/robust_monitor.py > logs/monitor.log 2>&1 &
```

### 2. Manual Run
To run a specific pipeline manually:
```bash
# Run with Google Gemini
./venv/bin/python3 bin/run_pipeline.py --company Sofwave --provider google --model gemini-2.0-flash

# Run with Local Ollama (DeepSeek)
./venv/bin/python3 bin/run_pipeline.py --company Sofwave --provider ollama --model deepseek-r1:8b --no-fallback
```

### 3. Monitoring Progress 📊
See real-time status in your terminal:
```bash
python3 bin/monitor_progress.py
```

### 4. Comparison & Stats 📈
Compare model speeds or verify output:
```bash
# Benchmark Llama vs DeepSeek
python3 bin/compare_models.py

# Verify Data Integrity
python3 bin/verify_completion.py
```

## Project Structure
```
├── bin/          # CLI tools & entry points
├── src/          # Core library code
├── tests/        # Test files
├── logs/         # Log files (gitignored)
├── downloads/    # Data files (gitignored)
└── archive/      # Deprecated files
```

## Documentation
See [system_architecture.md](system_architecture.md) for a deep dive into the code structure and logic.
