#!/usr/bin/env bash
"""
deploy.sh — Portable shell deploy script for SWARM_CONSOLIDATED.

Usage:
    curl -fsSL https://raw.githubusercontent.com/eltonaguiar/SWARM_CONSOLIDATED/main/deploy.sh | bash
    # or
    bash deploy.sh [--install | --test | --all]
"""
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Deploying SWARM_CONSOLIDATED ==="

# Install Python requirements
echo "[+] Installing Python requirements..."
python3 -m pip install -r "$REPO_ROOT/requirements.txt"

# Copy .env example
if [[ ! -f "$REPO_ROOT/.env" ]] && [[ -f "$REPO_ROOT/.env.example" ]]; then
    cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
    echo "[+] Created .env from .env.example — edit it with your API keys"
fi

# Smoke test
echo "[+] Running smoke test..."
python3 "$REPO_ROOT/swarm_unified.py" "test" --architecture combine --model ULTRA_FREE_CLOUD_FAST --tier free

echo "=== Deploy complete ==="
echo "Next steps:"
echo "  1. Edit .env with your API keys (SUBQ_FREE_API_KEY required)"
echo "  2. Start LiteLLM proxy: python3 tools/start_litellm_proxy.sh"
echo "  3. Run a swarm: python3 swarm_unified.py \"fix this mermaid\" --architecture combine --model ULTRA_FREE_CLOUD_FAST"
