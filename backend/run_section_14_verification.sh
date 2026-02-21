#!/bin/bash
# Section 14 Verification - Production Test Runner
# Automatically uses .venv or venv depending on what exists

set -e

cd "$(dirname "$0")"

# Find virtual environment
if [ -d "../.venv" ]; then
    VENV="../.venv"
elif [ -d "../venv" ]; then
    VENV="../venv"
else
    echo "❌ No virtual environment found (.venv or venv)"
    echo "Create one with: python3 -m venv .venv"
    exit 1
fi

echo "Using virtual environment: $VENV"

# Activate and run
source "$VENV/bin/activate"

# Check for MONGO_URI
if [ -z "$MONGO_URI" ] && [ -z "$AUDIT_MONGO_URI" ]; then
    echo "⚠️  No MONGO_URI or AUDIT_MONGO_URI in environment"
    echo "Using default: mongodb://159.203.122.145:27017/"
    export MONGO_URI="mongodb://159.203.122.145:27017/"
fi

python3 verify_section_14.py
