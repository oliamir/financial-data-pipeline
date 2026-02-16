#!/bin/bash
# ============================================================
# Oracle Cloud Always Free - Financial Pipeline Server Setup
# For: Ampere A1 ARM instance (4 OCPU, 24GB RAM)
#
# Architecture (new):
#   cli/main.py              - CLI entry point
#   src/pipeline/             - Orchestrator, AI providers, scrapers
#   src/scrapers/             - TASE + IR site scrapers (Playwright)
#   src/ai/                   - LLM providers (Ollama, Gemini, etc.)
#   src/storage/              - File manager, paths
#   src/registry/             - Company registry, priority policies
#   config/providers.yaml     - Provider configuration
#   config/companies.yaml     - Company registry
# ============================================================
set -euo pipefail

echo "Setting up Financial Pipeline Server on Oracle Cloud ARM"
echo "========================================================"

# --- System Update ---
echo "[1/7] Updating system packages..."
sudo apt-get update -y && sudo apt-get upgrade -y

# --- Install essential tools ---
echo "[2/7] Installing system dependencies..."
sudo apt-get install -y \
    curl wget git \
    python3 python3-pip python3-venv \
    poppler-utils \
    cron \
    libnss3 libatk-bridge2.0-0 libdrm2 libxcomposite1 \
    libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libxshmfence1  # Playwright system deps

# --- Install Ollama ---
echo "[3/7] Installing Ollama..."
curl -fsSL https://ollama.ai/install.sh | sh

# --- Start Ollama service ---
echo "[4/7] Starting Ollama service..."
sudo systemctl enable ollama
sudo systemctl start ollama

# Wait for Ollama to be ready
echo "  Waiting for Ollama to start..."
sleep 5
until curl -s http://localhost:11434/api/tags >/dev/null 2>&1; do
    echo "  Waiting..."
    sleep 2
done
echo "  Ollama is running"

# --- Pull qwen2.5:7b model (matches config/providers.yaml) ---
echo "[5/7] Pulling qwen2.5:7b model (this takes 5-10 minutes on ARM)..."
ollama pull qwen2.5:7b

echo "  Model pulled successfully"

# --- Setup Python environment ---
echo "[6/7] Setting up Python environment..."
cd /home/ubuntu
mkdir -p finance-pipeline
cd finance-pipeline

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip

# Install all project dependencies
pip install \
    requests beautifulsoup4 pandas openpyxl pdfplumber \
    google-api-python-client google-auth-httplib2 google-auth-oauthlib \
    google-generativeai \
    playwright python-dotenv \
    openai ollama \
    pyyaml

# Install Playwright browsers (needed for TASE scraping)
echo "  Installing Playwright Chromium browser..."
playwright install chromium
playwright install-deps chromium 2>/dev/null || true

echo "  Python environment ready"

# --- Create pipeline systemd service ---
echo "[7/7] Creating pipeline systemd service..."
sudo tee /etc/systemd/system/finance-pipeline.service > /dev/null << 'EOF'
[Unit]
Description=Financial Data Pipeline
After=network.target ollama.service
Requires=ollama.service

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=/home/ubuntu/finance-pipeline
ExecStart=/home/ubuntu/finance-pipeline/venv/bin/python3 -m cli.main run --tier high
Environment=OLLAMA_HOST=http://localhost:11434
EnvironmentFile=-/home/ubuntu/finance-pipeline/.env

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload

echo ""
echo "========================================================"
echo "SETUP COMPLETE"
echo "========================================================"
echo ""
echo "Next steps:"
echo "  1. Sync your code:"
echo "     ./deploy/oracle-cloud/sync.sh"
echo ""
echo "  2. Or manually copy:"
echo "     scp -r src/ config/ cli/ ubuntu@<IP>:~/finance-pipeline/"
echo "     scp requirements.txt .env ubuntu@<IP>:~/finance-pipeline/"
echo ""
echo "  3. Run the pipeline:"
echo "     cd ~/finance-pipeline && source venv/bin/activate"
echo "     python3 -m cli.main run --tier high"
echo ""
echo "  4. Or run a single company:"
echo "     python3 -m cli.main run sofwave"
echo ""
echo "  5. Install cron jobs:"
echo "     ./deploy/oracle-cloud/cron-setup.sh"
echo ""
