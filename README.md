# SWARM_CONSOLIDATED — Swarm Architecture Comparison & Performance Analysis

> **Last Updated:** 2026-11-14  
> **Source Repo:** https://github.com/eltonaguiar/SWARM_CONSOLIDATED  
> **Purpose:** Document the two independent swarm systems, their architectures, performance benchmarks, and integration recommendations.

---

## Executive Summary

This repository contains **two independent swarm systems** that complement each other:

| Dimension | **tools/swarm** (Multi-Engine) | **ruflo swarm** (Hermes-based) |
|-----------|-------------------------------|--------------------------------|
| **Architecture** | Python CLI → Direct API calls via `api_consult.py` | Hermes Agent (`hermes chat -q`) via Python orchestrator |
| **Transport** | Direct OpenRouter API with env-based API keys | Hermes internal OpenRouter routing via `~/.hermes/config.toml` |
| **Agent Model** | 16+ engine adapters (claude, deepseek, xai, cerebras, ollama, kilo, etc.) | 5 specialized agents (researcher, quant, github, bug_hunter, strategist) |
| **Free Tier** | ❌ Needs API keys (~$0.001/run) | ✅ Yes (via Hermes + OpenRouter free models) |
| **Paid Tier** | ✅ DeepSeek, Cerebras, xAI, Ollama Cloud, Claude | ⚠️ Not wired — requires `~/.hermes/config.toml` setup |
| **Memory** | ✅ SQLite sessions (`swarm_runs/_sessions.db`) with `--persist-sessions` | ❌ Ephemeral (each run fresh, data from live files) |
| **Multi-Model Consensus** | ✅ N models in parallel → ranked synthesis | ❌ Single model per agent |
| **Setup** | Python + API keys | Hermes binary + WSL |
| **Output** | `swarm_runs/run_<TS>/` + `_summary.json` | `swarm_runs/ruflo-insights/COMPILED_latest.json` |
| **Windows Native** | ✅ Yes | ❌ Requires WSL bridge |
| **Failover** | ❌ Single engine call | ✅ 3-attempt model rotation |

---

## Performance Benchmark Results (Live Test: 2026-05-05)

### Test 1: PR Review (4 open PRs)

| System | Status | Latency | Cost | Output Quality |
|--------|--------|---------|------|----------------|
| **tools/swarm (deepseek)** | ✅ SUCCESS | 10.91s | $0.0016 | Structured JSON with per-PR risk classification & recommendations |
| **ruflo swarm (github_hygiene)** | ❌ FAILED | N/A | $0.00 | HTTP 404: No endpoints found |

### Test 2: GitHub Actions Failure Analysis

| System | Status | Latency | Cost | Output Quality |
|--------|--------|---------|------|----------------|
| **tools/swarm (deepseek)** | ✅ SUCCESS | 13.24s | $0.0016 | Structured JSON: 3 failed workflows classified, 9 cancellations analyzed, pattern detection |
| **ruflo swarm (bug_hunter)** | ❌ FAILED | N/A | $0.00 | HTTP 404: No endpoints found |

### Test 3: Audit Dashboard Performance Evaluation

| System | Status |
|--------|--------|
| **tools/swarm** | Ready (prompt created at `tools/swarm/prompts/audit_perf_review.md`) |
| **ruflo swarm** | ❌ Both audit_researcher + audit_quant failed (HTTP 404) |

### Key Finding

> **tools/swarm WINS on reliability** — completed both tasks successfully with deepseek engine.  
> **ruflo swarm FAILED 100%** — all 5 agents returned "HTTP 404: No endpoints found" from OpenRouter free tier.

---

## Architecture Details

### tools/swarm (Production-Battle-Tested)

```
User → swarm_run.py → worker_runner.py → api_consult.py → OpenRouter API
                          ↓
                     Prompt files (.md)
                          ↓
                     JSON output → _summary.json
```

**Strengths:**
- ✅ Direct API access — no intermediary agent
- ✅ Multiple engine support (deepseek, cerebras, xai, ollama_cloud, claude)
- ✅ Paid model keys wired via environment variables
- ✅ Fast (sub-30s for deepseek/cerebras)
- ✅ Reliable JSON output with `_swarm_meta` (model fingerprint, tokens, retry count)
- ✅ Native Windows execution (no WSL bridge)
- ✅ Cost tracking per run ($0.0016 for PR review)
- ✅ Presets (`fast-cheap`, `safe-default`, `red-team`)
- ✅ Post-run inspect/follow-up tools

**Weaknesses:**
- ❌ Single-engine per run (no multi-model consensus in one invocation)
- ❌ Cerebras engine requires `cerebras-cloud-sdk` pip package (fragile)
- ❌ No agent persona system (flat prompt → output)
- ❌ No YAML-based agent configuration
- ❌ No swarm orchestration (parallel agents with different roles)
- ❌ CLI only — no interactive wizard
- ❌ No model failover/retry

### ruflo swarm (New, Experimental)

```
User → orchestrator.py → hermes chat -q -Q --source tool --yolo → OpenRouter (via Hermes)
                              ↓
                         YAML agent definitions
                              ↓
                         Agent output → COMPILED_latest.json
```

**Strengths:**
- ✅ Multi-agent design (5 specialized roles: researcher, coder, reviewer, security, architect)
- ✅ YAML-based agent configuration with `goal`, `swarm`, `dataSources`, `checks` fields
- ✅ Runtime model failover (3-attempt retry with exponential backoff + model rotation)
- ✅ `FAILOVER_MODELS` chain (gemini → deepseek → mistral → hy3)
- ✅ `should_failover()` detects rate limits, timeouts, provider errors
- ✅ Agent persona differentiation (different roles, models, capabilities)
- ✅ Inspired by ruvnet/ruflo's agent swarm pattern
- ✅ `--list-agents` for discovery, `--help` for docs

**Weaknesses:**
- ❌ **100% failure rate on first live test** — all agents returned HTTP 404
- ❌ Requires WSL (Windows ↔ WSL path translation fragility)
- ❌ Hermes binary dependency (`hermes chat -q` must be callable)
- ❌ OpenRouter free-tier models unreliable (404 errors)
- ❌ No paid model keys wired into Hermes config
- ❌ Slower (hermes startup + model loading overhead)
- ❌ No cost tracking
- ❌ No post-run inspection tools
- ❌ `hermes chat -q` prompt passing is fragile (special characters risk)
- ❌ Git operations timeout (119k+ commit repo)

---

## SWARM_CONSOLIDATED v2 Architecture (core/v2/)

The repo also contains a **third, next-generation swarm architecture** in `core/v2/`:

### Swarm Engines (core/v2/engines/)
- `coding_swarm.py` — Decompose → generate → test → review → revise → enforce
- `debate_team.py` — Multi-round adversarial debate + synthesizer judge
- `ensemble_swarm.py` — N-model parallel consensus with quality scoring
- `hierarchical_swarm.py` — Role-based hierarchical orchestration
- `pr_review_swarm.py` — Impact analyzer + code reviewer + risk controller (weighted approval)
- `research_swarm.py` — Plan → decompose → parallel retrieve → filter → synthesize → critique
- `github_actions_swarm.py` — GitHub Actions failure analysis + remediation

### Meta-Orchestrator (core/v2/meta_orchestrator.py)
Self-improving orchestrator with:
- Quality scoring across 4 dimensions (prediction_accuracy, code_correctness, review_thoroughness, actionability)
- A/B testing of prompt/persona variants via Thompson sampling
- Weak persona identification and targeted improvement recommendations
- Skill export for downstream consumption
- Persistent JSON memory store

### Key v2 Features
- **Proxy-First Pattern**: No swarm reads keys directly; launcher owns key loading, proxy holds keys
- **Health Gate**: Group is "live" if status=200 AND (content OR reasoning_content non-empty)
- **Runtime Alias Resolution**: Resolve aliases from `GET /v1/models` at runtime — never hardcode
- **Memory Pattern**: Agents write local `.md` working memory after every turn
- **Cost Ceiling**: Hard `cost_cap_usd` aborts if exceeded

---

## When to Use Which System

| Task | Recommended System | Reason |
|------|-------------------|--------|
| **Second opinion** on PR/code | `tools/swarm` with `--preset consensus-3` | Multi-engine consensus, reliable |
| **PR review** before push | `tools/swarm` (brainstorm_review) | 6 models parallel → synthesis |
| **GitHub Actions monitor** | `.ruflo/orchestrator.py --swarm github` | Fast (1-3 min), single agent, uses `gh` CLI |
| **Performance audit** (daily) | `.ruflo/orchestrator.py --continuous` | Periodic loop, compiles insights |
| **Bug hunt** (one-shot) | `.ruflo/orchestrator.py --swarm bugs` | Specialized security agent |
| **Strategy ideation** | `.ruflo/orchestrator.py --swarm strategy` | Architect role with market data |
| **Repeated identical tasks** | `tools/swarm --persist-sessions` | Persistent SQLite memory |
| **Latency-sensitive** | `tools/swarm` with paid models | Sub-30s, direct API |
| **Zero-cost background** | `.ruflo --tier free` | OpenRouter free models |

---

## Integration Roadmap (Hybrid Architecture)

The ideal architecture combines the strengths of both:

```
User → Interactive Wizard (FREE / PAID / HYBRID)
            ↓
    ┌───────┴────────┐
    ↓                ↓
ruflo orchestrator  tools/swarm
(Hermes agents)    (api_consult.py)
    ↓                ↓
  YAML configs     .md prompts
    ↓                ↓
  multi-agent      multi-engine
  consensus        consensus
    ↓                ↓
    └───────┬────────┘
            ↓
    SWARM_STYLE_DIFF comparison
    (pick best output per task)
```

### Priority Integration Steps

1. **Wire paid models into ruflo** — Add OpenRouter API keys to `~/.hermes/config.toml` or env vars
2. **Skip WSL for ruflo** — Add `--direct` mode to `orchestrator.py` calling `api_consult.py` directly
3. **Add ruflo YAML agent configs to tools/swarm** — Accept `--agent-config .ruflo/agents/strategist.yaml`
4. **Create interactive wizard** — `/swarm-ruflo` slash command: FREE (risky) / PAID (reliable) / HYBRID (compare)
5. **Add cost tracking to ruflo** — Track tokens and estimate USD cost per swarm run
6. **Add post-run inspection** — `python3 .ruflo/orchestrator.py --inspect <run_dir>`

---

## Quick Start Commands

### tools/swarm
```bash
# Second opinion (3 engines, cheap)
python3 tools/swarm/swarm_run.py --prompt-file my_prompt.md --engines deepseek,xai,kilo --cost-cap-usd 0.10

# PR review preset
python3 tools/swarm/swarm_run.py --preset consensus-3

# Fast cheap
python3 tools/swarm/swarm_run.py --preset fast-cheap

# Inspect latest
python3 tools/swarm/swarm_inspect.py --latest
```

### ruflo swarm
```bash
# Interactive wizard
python3 .ruflo/wizard.py

# Run audit swarm (2 agents parallel)
python3 .ruflo/orchestrator.py --swarm audit --tier hybrid

# Check paid API key status
python3 .ruflo/orchestrator.py --check-keys

# List agents
python3 .ruflo/orchestrator.py --list-agents

# From Windows (Codebuff)
wsl bash -c "cd /mnt/c/findtorontoevents_antigravity.ca && python3 .ruflo/orchestrator.py --swarm audit --no-verify"
```

### swarm_unified.py (unified runner)
```bash
# Combine architecture (N-model consensus)
python3 swarm_unified.py "fix this bug" --architecture combine --model ULTRA_FREE_CLOUD_FAST

# Ruflo architecture (role-specialized)
python3 swarm_unified.py "audit performance" --architecture ruflo --model ULTRA_FREE_CLOUD_FAST

# Hermes architecture (planning → workers → verify → synthesize)
python3 swarm_unified.py "code a feature" --architecture hermes --model ULTRA_PAID_MODE
```

---

## Files of Interest

### tools/swarm/
| File | Purpose |
|------|---------|
| `swarm_run.py` | One-shot fan-out dispatcher |
| `worker_runner.py` | Per-engine adapter (CLIs + APIs) |
| `api_consult.py` | Direct API caller (shared with .ruflo) |
| `swarm_followup.py` | Multi-turn chain |
| `swarm_inspect.py` | Per-run health audit |
| `swarm_stats.py` | Historical engine stats |
| `session_manager.py` | SQLite session ops |
| `config_loader.py` | YAML config loader + key env vars |

### .ruflo/
| File | Purpose |
|------|---------|
| `orchestrator.py` | Main dispatcher — 5 agents, 5 tiers, failover |
| `wizard.py` | Interactive tier & model selector |
| `agents/*.yaml` | Agent definitions (loaded at runtime) |

### core/v2/
| File | Purpose |
|------|---------|
| `meta_orchestrator.py` | Self-improving orchestrator with quality scoring, A/B testing |
| `engines/coding_swarm.py` | Coding swarm with test enforcement |
| `engines/debate_swarm.py` | Adversarial debate with synthesizer |
| `engines/ensemble_swarm.py` | Parallel consensus with quality scoring |
| `engines/hierarchical_swarm.py` | Role-based hierarchical orchestration |
| `engines/pr_review_swarm.py` | Weighted approval PR review |
| `engines/research_swarm.py` | Research pipeline with critique |

---

## References

- [SWARM_ARCHITECTURE_COMPARISON.md](SWARM_ARCHITECTURE_COMPARISON.md) — Industry patterns & recommended architecture
- [SWARM_RESEARCH_PATTERNS_2026-11-13.md](SWARM_RESEARCH_PATTERNS_2026-11-13.md) — How successful swarms do research
- [SWARM_CONCURRENCY_RESEARCH_2026-11-13.md](SWARM_CONCURRENCY_RESEARCH_2026-11-13.md) — LiteLLM concurrency & production config
- [RUFLO_SWARM_GUIDE.MD](RUFLO_SWARM_GUIDE.MD) — Ruflo swarm user guide
- [HERMES_SWARM_NOTES.MD](HERMES_SWARM_NOTES.MD) — Two swarm systems reference
- [updates/SWARM_STYLE_DIFF.MD](updates/SWARM_STYLE_DIFF.MD) — Side-by-side live benchmark
- [DEPLOY.md](DEPLOY.md) — Deployment guide

---

## Conclusion

**Use `tools/swarm` for production tasks today** — PR reviews, Actions failure analysis, audit evaluation. It works reliably with paid models.

**Fix `ruflo swarm`'s OpenRouter 404** by wiring paid API keys into Hermes config and adding a `--direct` mode.

**Build the hybrid** — ruflo's YAML agent configs + tools/swarm's reliable API transport = best of both worlds.

The `core/v2/` architecture represents the next generation with self-improving meta-orchestration, quality scoring, and A/B testing — but needs the proxy concurrency issues resolved first (see SWARM_CONCURRENCY_RESEARCH).