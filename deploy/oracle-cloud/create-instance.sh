#!/bin/bash
# ============================================================
# Oracle Cloud Always Free - Infrastructure Setup Guide
# Creates an Ampere A1 ARM instance via OCI CLI
# ============================================================
#
# PREREQUISITES:
#   1. Oracle Cloud account (free): https://cloud.oracle.com/
#   2. OCI CLI installed: brew install oci-cli (macOS)
#   3. API key configured: oci setup config
#
# MANUAL STEPS (via OCI Console - easier for first time):
#   https://cloud.oracle.com/compute/instances/create
#
# ============================================================

set -euo pipefail

# --- Configuration ---
# These will be set during interactive setup
COMPARTMENT_ID=""  # Your tenancy OCID
AVAILABILITY_DOMAIN=""
SUBNET_ID=""
SSH_KEY_FILE="$HOME/.ssh/id_rsa.pub"

echo "============================================================"
echo "Oracle Cloud Free Tier - Ampere A1 Instance Setup"
echo "============================================================"
echo ""
echo "This script helps you create an Always Free ARM instance"
echo "optimized for running Ollama with llama3.1"
echo ""

# --- Check OCI CLI ---
if ! command -v oci &>/dev/null; then
    echo "❌ OCI CLI not found. Install with: brew install oci-cli"
    echo "   Then run: oci setup config"
    exit 1
fi

# --- Get compartment ID ---
echo "📋 Finding your compartment..."
if [ -z "$COMPARTMENT_ID" ]; then
    COMPARTMENT_ID=$(oci iam compartment list --query 'data[0]."compartment-id"' --raw-output 2>/dev/null || true)
    if [ -z "$COMPARTMENT_ID" ]; then
        echo "⚠️  Could not auto-detect compartment. Enter your Tenancy OCID:"
        read -r COMPARTMENT_ID
    fi
fi
echo "  Compartment: $COMPARTMENT_ID"

# --- Get availability domain ---
echo "📍 Finding availability domain..."
if [ -z "$AVAILABILITY_DOMAIN" ]; then
    AVAILABILITY_DOMAIN=$(oci iam availability-domain list \
        --compartment-id "$COMPARTMENT_ID" \
        --query 'data[0].name' --raw-output)
fi
echo "  AD: $AVAILABILITY_DOMAIN"

# --- Find Ubuntu 22.04 ARM image ---
echo "🖼️  Finding Ubuntu 22.04 ARM image..."
IMAGE_ID=$(oci compute image list \
    --compartment-id "$COMPARTMENT_ID" \
    --operating-system "Canonical Ubuntu" \
    --operating-system-version "22.04" \
    --shape "VM.Standard.A1.Flex" \
    --query 'data[0].id' --raw-output \
    --sort-by TIMECREATED --sort-order DESC)
echo "  Image: $IMAGE_ID"

# --- Create VCN and Subnet if needed ---
echo "🌐 Setting up networking..."
VCN_ID=$(oci network vcn create \
    --compartment-id "$COMPARTMENT_ID" \
    --display-name "ollama-vcn" \
    --cidr-blocks '["10.0.0.0/16"]' \
    --query 'data.id' --raw-output 2>/dev/null || true)

if [ -n "$VCN_ID" ]; then
    # Create internet gateway
    IGW_ID=$(oci network internet-gateway create \
        --compartment-id "$COMPARTMENT_ID" \
        --vcn-id "$VCN_ID" \
        --is-enabled true \
        --display-name "ollama-igw" \
        --query 'data.id' --raw-output)
    
    # Create subnet
    SUBNET_ID=$(oci network subnet create \
        --compartment-id "$COMPARTMENT_ID" \
        --vcn-id "$VCN_ID" \
        --cidr-block "10.0.1.0/24" \
        --display-name "ollama-subnet" \
        --query 'data.id' --raw-output)
    
    echo "  VCN: $VCN_ID"
    echo "  Subnet: $SUBNET_ID"
fi

# --- Create the instance ---
echo ""
echo "🖥️  Creating Ampere A1 instance (4 OCPU, 24GB RAM)..."
echo "   This is the maximum Always Free allocation."
echo ""

INSTANCE_ID=$(oci compute instance launch \
    --compartment-id "$COMPARTMENT_ID" \
    --availability-domain "$AVAILABILITY_DOMAIN" \
    --shape "VM.Standard.A1.Flex" \
    --shape-config '{"ocpus": 4, "memoryInGBs": 24}' \
    --image-id "$IMAGE_ID" \
    --subnet-id "$SUBNET_ID" \
    --display-name "ollama-llm-server" \
    --assign-public-ip true \
    --ssh-authorized-keys-file "$SSH_KEY_FILE" \
    --query 'data.id' --raw-output)

echo "✅ Instance created: $INSTANCE_ID"

# --- Wait for instance to be running ---
echo "⏳ Waiting for instance to boot..."
oci compute instance get \
    --instance-id "$INSTANCE_ID" \
    --wait-for-state RUNNING \
    --max-wait-seconds 300

# --- Get public IP ---
VNIC_ID=$(oci compute instance list-vnics \
    --instance-id "$INSTANCE_ID" \
    --query 'data[0]."vnic-id"' --raw-output)

PUBLIC_IP=$(oci network vnic get \
    --vnic-id "$VNIC_ID" \
    --query 'data."public-ip"' --raw-output)

echo ""
echo "============================================================"
echo "✅ INSTANCE READY!"
echo "============================================================"
echo ""
echo "Public IP: $PUBLIC_IP"
echo ""
echo "Connect:   ssh ubuntu@$PUBLIC_IP"
echo ""
echo "Next: Run the setup script on the instance:"
echo "  scp deploy/oracle-cloud/setup.sh ubuntu@$PUBLIC_IP:~/"
echo "  ssh ubuntu@$PUBLIC_IP 'chmod +x setup.sh && ./setup.sh'"
echo ""
echo "Then sync your pipeline code:"
echo "  ./deploy/oracle-cloud/sync.sh $PUBLIC_IP"
echo "  # Or manually:"
echo "  scp -r src/ config/ cli/ ubuntu@$PUBLIC_IP:~/finance-pipeline/"
echo "  scp requirements.txt .env ubuntu@$PUBLIC_IP:~/finance-pipeline/"
echo ""

# Save the IP for later use
echo "$PUBLIC_IP" > deploy/oracle-cloud/.instance_ip
echo "IP saved to deploy/oracle-cloud/.instance_ip"
