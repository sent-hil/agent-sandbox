#!/bin/bash
# Quick test script to rebuild and test sandbox
# Usage: ./test-sandbox.sh [sandbox-name]

set -e

SANDBOX_NAME="${1:-test}"

echo "==> Cleaning uv cache and reinstalling agent-sandbox..."
uv cache clean
uv tool install . --force

echo ""
echo "==> Removing sandbox '$SANDBOX_NAME'..."
agent-sandbox rm "$SANDBOX_NAME" 2>/dev/null || true

echo ""
echo "==> Connecting to sandbox '$SANDBOX_NAME'..."
agent-sandbox connect "$SANDBOX_NAME" -y
