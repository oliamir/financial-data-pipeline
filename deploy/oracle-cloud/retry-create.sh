#!/bin/bash
# Auto-retry instance creation until capacity is available
# Usage: ./retry-create.sh [max_attempts] [delay_seconds]
set -euo pipefail

TENANCY="ocid1.tenancy.oc1..aaaaaaaagkpoyj37qyrw3kmrqlunvsnd5og5vys6qxb377c5ddn6e7hk2nsq"
SUBNET_ID="ocid1.subnet.oc1.il-jerusalem-1.aaaaaaaat2ivqyrhu4u4tijsxpgxv67hmethyv3gtjtwevr2yze4mslxpxsa"
AD="kDvM:IL-JERUSALEM-1-AD-1"
IMAGE_ID="ocid1.image.oc1.il-jerusalem-1.aaaaaaaayggbhett53rwzj74mssjflbshpeveuyacb7aav64ayhamgr5jnja"
SSH_KEY_FILE="$HOME/.ssh/id_ed25519.pub"

MAX_ATTEMPTS=${1:-120}
DELAY=${2:-300}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Retrying instance creation (max $MAX_ATTEMPTS attempts, ${DELAY}s between)"
echo "Region: il-jerusalem-1 | Shape: VM.Standard.A1.Flex (4 OCPU, 24GB)"
echo ""

for i in $(seq 1 "$MAX_ATTEMPTS"); do
    echo "[$(date '+%H:%M:%S')] Attempt $i/$MAX_ATTEMPTS..."

    RESULT=$(oci compute instance launch \
        --compartment-id "$TENANCY" \
        --availability-domain "$AD" \
        --shape "VM.Standard.A1.Flex" \
        --shape-config '{"ocpus": 4, "memoryInGBs": 24}' \
        --image-id "$IMAGE_ID" \
        --subnet-id "$SUBNET_ID" \
        --display-name "ollama-llm-server" \
        --assign-public-ip true \
        --ssh-authorized-keys-file "$SSH_KEY_FILE" 2>&1) || true

    if echo "$RESULT" | grep -q '"lifecycle-state"'; then
        INSTANCE_ID=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
        echo ""
        echo "SUCCESS! Instance created: $INSTANCE_ID"
        echo ""

        # Wait for running state
        echo "Waiting for instance to boot..."
        oci compute instance get --instance-id "$INSTANCE_ID" \
            --wait-for-state RUNNING --max-wait-seconds 300 2>/dev/null || true

        # Get public IP
        VNIC_ID=$(oci compute instance list-vnics \
            --instance-id "$INSTANCE_ID" \
            --query 'data[0]."vnic-id"' --raw-output 2>/dev/null)
        PUBLIC_IP=$(oci network vnic get \
            --vnic-id "$VNIC_ID" \
            --query 'data."public-ip"' --raw-output 2>/dev/null)

        echo "$PUBLIC_IP" > "$SCRIPT_DIR/.instance_ip"
        echo ""
        echo "============================================"
        echo "Instance ready!"
        echo "Public IP: $PUBLIC_IP"
        echo "IP saved to: $SCRIPT_DIR/.instance_ip"
        echo ""
        echo "Next steps:"
        echo "  ssh ubuntu@$PUBLIC_IP"
        echo "============================================"
        exit 0
    fi

    if echo "$RESULT" | grep -q "Out of host capacity"; then
        echo "  Out of capacity. Retrying in ${DELAY}s..."
    else
        echo "  Error: $(echo "$RESULT" | grep '"message"' | head -1)"
        echo "  Retrying in ${DELAY}s..."
    fi

    sleep "$DELAY"
done

echo "Max attempts reached. Try again later or try a different region."
exit 1
