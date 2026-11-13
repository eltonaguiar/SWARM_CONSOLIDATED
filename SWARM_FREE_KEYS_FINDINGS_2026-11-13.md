# Swarm-on-Free-Keys Findings — 2026-11-13

## Context
The user runs a LiteLLM rotating proxy on `http://localhost:4000/v1` fronting ~43 free/paid keys in `~/dbpasses.txt` (wired in `litellm_config.yaml`). They tried to route an AI research swarm through it. It crashed under concurrent calls; even raising concurrency didn't match vLLM. Question: how to run a swarm on free keys, and what do successful research swarms (Open Swarm-style) actually do for accuracy?

Source of truth read in this session: `tools/freellm.py`, `tools/asset_class_research_swarm.py`, `litellm_config.yaml`, `tools/start_litellm_proxy.sh`, `.claude/skills/litellm-proxy/SKILL.md`, `.claude/skills/consult-PROXY/SKILL.md`.

## Root cause of the crash
`tools/start_litellm_proxy.sh:435` launches LiteLLM with `--num_workers 1` — a single worker serializes every request. A swarm fan-out (N concurrent model calls) queues behind one worker, timeouts pile up, and the proxy looks "crashed." vLLM wins not because it's smarter but because continuous batching actually handles concurrency.

## How research swarms get accuracy with free keys

### 1. Fan-out + consensus, not "one model is right"
Ask N independent models the same question (CombineTeam), then synthesize via a judge model or majority vote over structured JSON. Accuracy comes from agreement across diverse upstreams, not one premium model. `tools/freellm.py` already implements CombineTeam / DebateTeam / FileTeam; `tools/asset_class_research_swarm.py` is a per-asset-class deep-research swarm that queries a panel, parses JSON, and writes a consensus report.

### 2. Local inference = concurrency workhorse; cloud keys = diversity
Route the swarm fan-out across local vLLM (`:8000`) + Ollama (`:11434`, unlimited/free, continuous batching) PLUS free cloud groups (`ULTRA_FREE_CLOUD`, `ULTRA_FREE_NVIDIA`, `ULTRA_FREE_LOCAL_*`). No single key/rate-limit stalls the swarm. The proxy's `router_settings` already has `num_retries`, `allowed_fails`, `cooldown_time`, and fallbacks between strict-free groups — good, but serialization at `--num_workers 1` negates it under load.

### 3. Ground research with local data (proxy models have no browser)
Never let a proxy model claim to fetch a URL. Pull `audit_dashboard/data/*.json` locally, embed it verbatim in the prompt, and instruct the model it was given the data and must not claim to fetch anything. Validate candidates against the local backtester/CPCV pipeline rather than trusting model output. (`.claude/skills/consult-PROXY/SKILL.md` grounding rule.)

### 4. Tap untapped keys
`dbpasses.txt` holds ~43 keys (SiliconFlow, Kimi, Groq, Cerebras, Gemini, Mistral, DeepInfra, Fireworks, etc.) but `litellm_config.yaml` / `start_litellm_proxy.sh` only wire a subset. Wire the unwired free keys into `ULTRA_FREE_CLOUD` / `ULTRA_FREE_NVIDIA` so the rotation actually uses them.

### 5. Reasoning models need budget
`openrouter-ring-1t` / qwen3 put text in `reasoning_content`, not `content`; with low `max_tokens` they emit only chain-of-thought and truncate. Give them `max_tokens >= 3000` (proxy) / `>= 1024` (local qwen3) or replies come back empty. (`.claude/skills/litellm-proxy/SKILL.md` known issues.)

## Recommended fix (minimal, safe)
1. Bump `--num_workers` in `tools/start_litellm_proxy.sh:435` (or call upstreams directly in parallel for the fan-out leg, bypassing the proxy) so concurrent swarm calls don't serialize.
2. Add unwired free keys from `dbpasses.txt` to `litellm_config.yaml` under strict-free groups; set `ALLOW_PAID_SPILLOVER=0` to keep free groups free-only.
3. Run `freellm.py CombineTeam -n 8` → `DebateTeam` for multi-round critique → a judge step emitting structured JSON → cross-check candidates against local backtest data.
4. Prefer `ULTRA_FREE_LOCAL_MULTI` (vLLM continuous batching, ~54.7 tok/s aggregate across 4 clients) for the high-concurrency leg; use cloud free groups for model diversity.

## Files referenced
- `tools/freellm.py` — CombineTeam/DebateTeam/FileTeam swarm CLI
- `tools/asset_class_research_swarm.py` — per-class deep-research swarm (JSON panel + consensus)
- `tools/start_litellm_proxy.sh` — proxy launcher (`--num_workers 1` at line 435)
- `litellm_config.yaml` — provider chain / model groups
- `~/dbpasses.txt` — key source (gitignored, outside repo)
