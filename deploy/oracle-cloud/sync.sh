#!/bin/bash
# ============================================================
# Sync local code to Oracle Cloud instance
# Usage: ./deploy/oracle-cloud/sync.sh [oracle-ip]
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REMOTE_DIR="/home/ubuntu/finance-pipeline"
REMOTE_USER="ubuntu"

# --- Resolve Oracle IP ---
if [ $# -ge 1 ]; then
    OCI_IP="$1"
elif [ -n "${OCI_IP:-}" ]; then
    # Use env var
    :
elif [ -f "$SCRIPT_DIR/.instance_ip" ]; then
    OCI_IP=$(cat "$SCRIPT_DIR/.instance_ip" | tr -d '[:space:]')
else
    echo "ERROR: Oracle instance IP not found."
    echo ""
    echo "Provide it via one of:"
    echo "  1. Argument:    ./sync.sh 129.213.x.x"
    echo "  2. Env var:     export OCI_IP=129.213.x.x"
    echo "  3. File:        echo '129.213.x.x' > deploy/oracle-cloud/.instance_ip"
    exit 1
fi

echo "Syncing to $REMOTE_USER@$OCI_IP:$REMOTE_DIR"
echo "Source: $PROJECT_ROOT"
echo ""

# --- Ensure remote directories exist ---
ssh "$REMOTE_USER@$OCI_IP" "mkdir -p $REMOTE_DIR/{src,config,cli}"

# --- Sync source code ---
echo "[1/4] Syncing src/..."
rsync -avz --delete \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    "$PROJECT_ROOT/src/" "$REMOTE_USER@$OCI_IP:$REMOTE_DIR/src/"

echo "[2/4] Syncing config/..."
rsync -avz --delete \
    "$PROJECT_ROOT/config/" "$REMOTE_USER@$OCI_IP:$REMOTE_DIR/config/"

echo "[3/4] Syncing cli/..."
rsync -avz --delete \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    "$PROJECT_ROOT/cli/" "$REMOTE_USER@$OCI_IP:$REMOTE_DIR/cli/"

echo "[4/4] Syncing config files..."
rsync -avz \
    "$PROJECT_ROOT/requirements.txt" "$REMOTE_USER@$OCI_IP:$REMOTE_DIR/"

# Sync .env only if it exists locally
if [ -f "$PROJECT_ROOT/.env" ]; then
    rsync -avz "$PROJECT_ROOT/.env" "$REMOTE_USER@$OCI_IP:$REMOTE_DIR/"
    echo "  .env synced"
fi

echo ""
echo "Sync complete."
echo ""
echo "To install new dependencies on the instance:"
echo "  ssh $REMOTE_USER@$OCI_IP 'cd $REMOTE_DIR && source venv/bin/activate && pip install -r requirements.txt'"
echo ""
echo "To run the pipeline:"
echo "  ssh $REMOTE_USER@$OCI_IP 'cd $REMOTE_DIR && source venv/bin/activate && python3 -m cli.main run --tier high'"
