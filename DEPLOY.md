# SWARM_CONSOLIDATED — Deployment Guide

# One-command deploy (Linux/macOS):
    curl -fsSL https://raw.githubusercontent.com/eltonaguiar/SWARM_CONSOLIDATED/main/deploy.sh | bash

# Or manual:
    git clone https://github.com/eltonaguiar/SWARM_CONSOLIDATED.git
    cd SWARM_CONSOLIDATED
    python3 -m pip install -r requirements.txt
    cp .env.example .env
    # Edit .env with your API keys (SUBQ_FREE_API_KEY required)
    python3 swarm_unified.py "test" --architecture combine --model ULTRA_FREE_CLOUD_FAST

# Windows (PowerShell):
    git clone https://github.com/eltonaguiar/SWARM_CONSOLIDATED.git
    cd SWARM_CONSOLIDATED
    python -m pip install -r requirements.txt
    copy .env.example .env
    # Edit .env with your API keys
    python swarm_unified.py "test" --architecture combine --model ULTRA_FREE_CLOUD_FAST

# Deploy LiteLLM proxy (required for swarms):
    python3 tools/start_litellm_proxy.sh    # Linux/macOS
    # Windows: run the proxy via litellm directly
    python -m litellm --config litellm_config.runtime.yaml --port 4000

# Run end-to-end mermaid fix swarm:
    python3 swarm_fix_worktree.py

# Run multi-model evaluation:
    python3 swarm_model_eval.py

# Run unified swarm with architecture choice:
    python3 swarm_unified.py "fix this bug" --architecture combine --model ULTRA_FREE_CLOUD_FAST
    python3 swarm_unified.py "review this PR" --architecture debate --model ULTRA_FREE_NVIDIA
    python3 swarm_unified.py "code a feature" --architecture coding --model ULTRA_PAID_MODE

# Swarm architectures available:
    combine   — N-model parallel consensus (fast, cheap, default)
    debate    — Multi-round adversarial debate + synthesizer judge
    coding    — Decompose → generate → test → review → revise → enforce
    pr_review — Impact analyzer + code reviewer + risk controller
    ruflo     — Role-specialized agents (coder, reviewer, security, tester, architect)
    hermes    — Planning root → parallel workers → verifier + synthesizer
