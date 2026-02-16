# Oracle Cloud Always Free -- Financial Pipeline Deployment

## Overview

Deploy the financial data pipeline on an **Oracle Cloud Always Free Ampere A1** instance:
- **4 ARM OCPUs** + **24 GB RAM** -- enough for Qwen 2.5 7B via Ollama
- **Always free** -- no credit card charges, runs 24/7
- **Automated scraping** -- TASE reports via Playwright + Ollama analysis
- **~9 tokens/sec** CPU-only inference (slower than local M2, but persistent and free)

## Quick Setup (5 steps)

### 1. Create Oracle Cloud Account
1. Go to [cloud.oracle.com](https://cloud.oracle.com/)
2. Sign up for a free account (requires credit card for identity verification -- never charged)
3. Choose your **Home Region** (pick closest: e.g., `me-jeddah-1` or `eu-frankfurt-1`)

> **NOTE:**
> The Always Free Ampere A1 shape is in HIGH DEMAND. If you can't create one, try:
> - Different availability domain in your region
> - Trying at off-peak hours (early morning UTC)
> - Using the [OCI Instance Pool trick](https://github.com/hitrov/oci-arm-host-capacity) to auto-retry

### 2. Create the ARM Instance
**Via Console (recommended for first time):**
1. Go to **Compute > Instances > Create Instance**
2. Set:
   - **Name:** `ollama-llm-server`
   - **Image:** Ubuntu 22.04 (aarch64)
   - **Shape:** `VM.Standard.A1.Flex` > **4 OCPUs, 24 GB RAM**
   - **Networking:** Create new VCN + subnet, assign public IP
   - **SSH key:** Upload your `~/.ssh/id_rsa.pub`
3. Click **Create**

**Via CLI:**
```bash
chmod +x deploy/oracle-cloud/create-instance.sh
./deploy/oracle-cloud/create-instance.sh
```

### 3. SSH In and Install Dependencies
```bash
# Get the IP from OCI Console or .instance_ip file
export OCI_IP=$(cat deploy/oracle-cloud/.instance_ip 2>/dev/null || echo "<your-instance-ip>")

# Copy setup script
scp deploy/oracle-cloud/setup.sh ubuntu@$OCI_IP:~/

# Run setup (installs Ollama + qwen2.5:7b + Python deps + Playwright)
ssh ubuntu@$OCI_IP 'chmod +x setup.sh && ./setup.sh'
```

### 4. Deploy Pipeline Code
```bash
# Option A: Use the sync script (recommended)
chmod +x deploy/oracle-cloud/sync.sh
./deploy/oracle-cloud/sync.sh

# Option B: Manual copy
scp -r src/ config/ cli/ ubuntu@$OCI_IP:~/finance-pipeline/
scp requirements.txt .env ubuntu@$OCI_IP:~/finance-pipeline/
```

### 5. Run the Pipeline
```bash
ssh ubuntu@$OCI_IP
cd ~/finance-pipeline && source venv/bin/activate

# Run all high-priority companies
python3 -m cli.main run --tier high

# Run a single company
python3 -m cli.main run sofwave

# Check status
python3 -m cli.main status

# List all companies
python3 -m cli.main list

# Validate outputs
python3 -m cli.main validate
```

## File Structure on Oracle
```
~/finance-pipeline/
├── venv/                        # Python virtual environment
├── cli/
│   └── main.py                  # CLI entry point
├── src/
│   ├── pipeline/
│   │   └── orchestrator.py      # Main pipeline orchestrator
│   ├── ai/
│   │   ├── providers.py         # LLM provider registry
│   │   └── router.py            # Task routing (classify/extract/memo)
│   ├── scrapers/
│   │   ├── coordinator.py       # Scraping coordinator
│   │   └── tase.py              # TASE scraper (Playwright)
│   ├── storage/
│   │   ├── file_manager.py      # File I/O for reports/financials
│   │   └── paths.py             # Path conventions
│   ├── registry/
│   │   └── company.py           # Company registry (reads companies.yaml)
│   └── models/
│       └── revision.py          # Revision tracking
├── config/
│   ├── providers.yaml           # LLM provider config (Ollama, Gemini, etc.)
│   └── companies.yaml           # Company registry (slugs, TASE IDs, priority)
├── data/                        # Downloaded reports (PDFs, CSVs)
└── .env                         # API keys (GOOGLE_API_KEY, etc.)
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `python3 -m cli.main run --tier high` | Run pipeline for all high-priority companies |
| `python3 -m cli.main run --tier low` | Run pipeline for all low-priority companies |
| `python3 -m cli.main run sofwave` | Run pipeline for a single company |
| `python3 -m cli.main run sofwave --skip-scrape` | Analyze only (no scraping) |
| `python3 -m cli.main run sofwave --skip-analyze` | Scrape only (no LLM analysis) |
| `python3 -m cli.main run sofwave --dry-run` | Preview what would happen |
| `python3 -m cli.main status` | Show status of all companies |
| `python3 -m cli.main list --tier high` | List companies by priority |
| `python3 -m cli.main validate` | Validate pipeline outputs |

## Cron Jobs (Automated Scheduling)

Use the provided script to install cron jobs on the Oracle instance:

```bash
# Copy and run on the Oracle instance
scp deploy/oracle-cloud/cron-setup.sh ubuntu@$OCI_IP:~/
ssh ubuntu@$OCI_IP 'chmod +x cron-setup.sh && ./cron-setup.sh'
```

This sets up:
- **Daily 6:00 AM** -- Scrape and analyze high-priority companies
- **Weekly Sunday 2:00 AM** -- Scrape and analyze low-priority companies
- **Log rotation** -- Keeps logs from growing unbounded

Manual cron setup (if you prefer):
```bash
crontab -e
# Daily 6AM: high-priority companies
0 6 * * * cd /home/ubuntu/finance-pipeline && source venv/bin/activate && python3 -m cli.main run --tier high >> /var/log/finance-pipeline/daily.log 2>&1
# Weekly Sunday 2AM: low-priority companies
0 2 * * 0 cd /home/ubuntu/finance-pipeline && source venv/bin/activate && python3 -m cli.main run --tier low >> /var/log/finance-pipeline/weekly.log 2>&1
```

## Configuring Ollama as a Remote Endpoint

When running the pipeline from your **local machine** against the Oracle instance's Ollama
server (instead of running the pipeline on the instance itself), you need to configure
the Ollama host in `config/providers.yaml`:

```yaml
providers:
  ollama:
    type: ollama
    model: qwen2.5:7b
    host_env: OLLAMA_HOST
    host_default: "http://<ORACLE_IP>:11434"
    fallback_model: llama3.1
```

Or set the environment variable:

```bash
export OLLAMA_HOST=http://<ORACLE_IP>:11434
python3 -m cli.main run sofwave
```

**Firewall setup** (on the Oracle instance, to allow remote Ollama access):

```bash
# Open port 11434 in iptables
sudo iptables -I INPUT -p tcp --dport 11434 -j ACCEPT

# Also add an ingress rule in OCI Console:
#   Networking > VCN > Security List > Add Ingress Rule
#   Source CIDR: your IP/32 (do NOT use 0.0.0.0/0)
#   Destination Port: 11434
#   Protocol: TCP
```

**Configure Ollama to listen on all interfaces** (on the Oracle instance):

```bash
sudo systemctl edit ollama
# Add:
# [Service]
# Environment="OLLAMA_HOST=0.0.0.0:11434"

sudo systemctl restart ollama
```

## Performance Notes

| Metric | Local M2 | Oracle A1 (Free) |
|--------|----------|-----------------|
| Inference speed | ~25 tok/s | ~9 tok/s |
| Time per PDF | 1-4 min | 3-10 min |
| 5 PDFs batch | ~15 min | ~40 min |
| RAM available | 16 GB (shared) | 24 GB (dedicated) |
| Availability | When laptop on | 24/7 |

## Syncing Code Updates

After making local changes, sync to Oracle:

```bash
# Uses rsync to efficiently update only changed files
./deploy/oracle-cloud/sync.sh

# Or manually:
rsync -avz --exclude='venv/' --exclude='data/' --exclude='node_modules/' --exclude='.git/' \
    src/ config/ cli/ requirements.txt .env \
    ubuntu@$OCI_IP:~/finance-pipeline/
```
