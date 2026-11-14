# SWARM_CONSOLIDATED — Multi-Agent LLM Swarm Architecture

> **Production-hardened concurrent LLM swarms** — 6 specialized engines, proxy-first routing, cost ceilings, health gates, and structured output aggregation.

---

## 📊 Performance Snapshot (2026-11-13)

| Metric | Value | Notes |
|--------|-------|-------|
| **Concurrency bottleneck** | LiteLLM `--num_workers 1` | Serializes all swarm calls; fixed by direct upstream parallel calls or raising workers |
| **Free-key usability** | ~50% of `dbpasses.txt` keys dead at `/chat/completions` | `/models` 200 ≠ usable — must probe tool-calls + 34k-token context |
| **Research accuracy ceiling** | 3/4 terms on ServiceNow test | Memory-only fails; retrieval + synthesis recovers 6pp |
| **Best research roster** | `ZZZ_BAD_LEGACY_MIXED_F_MODE_FAST` (3/4), `ULTRA_PAID_MODE` w/ retrieval (3/4) | `ULTRA_FREE_GEMINI` memory-only 3/4 (fastest useful) |
| **Cost per CombineTeam run** | ~$0.0004–$0.0023 | 5-model fan-out, deduplicated by upstream fingerprint |
| **Latency** | Parallel (max of individual, not sum) | ThreadPoolExecutor per swarm type |

---

## 🏗️ Swarm Architecture Comparison

### 6 Production Engines (core/v2/engines/)

| Engine | Purpose | Agents | Pipeline | Best For |
|--------|---------|--------|----------|----------|
| **CodingSwarm** | Code gen + review + test enforcement | 3 generators, 2 reviewers, 2 test writers | Decompose → Fan-out → Review loop (≤3) → Test gate | Feature implementation, bug fixes |
| **PRReviewSwarm** | PR impact analysis + risk assessment | Impact analyzer, code reviewer, risk controller | Fetch PR → Parallel 3-agent fan-out → Weighted approval (0.5/0.3/0.2) | PR quality gates |
| **GitHubActionsSwarm** | Failed/flaky/stale/cancelled job detection | 2 impact analyzers | Fetch runs → Pattern detection → Blast radius → Recommendations | CI health monitoring |
| **ResearchSwarm** | Deep research with cross-verification | 4 researchers | Decompose → Fan-out → Cross-verify → Synthesize | Technical research, epistemic triangulation |
| **EnsembleSwarm** | Weighted prediction aggregation | 5 tacticians | Fan-out votes → Weighted majority/avg → CI → Expand if low | Decision support, forecasting |
| **HierarchicalSwarm** | Strategic → Tactical → Execution layers | 2 strategists, 3 tacticians, 1 risk controller | Macro signals → Asset predictions → Order plans → Risk veto | Trading/portfolio decisions |

---

## ⚔️ Ruflo Swarm vs Hermes Swarm — Detailed Comparison

> **Context:** Ruflo Swarm is a 5-agent specialized swarm running through **Hermes Agent** (Nous Research v0.12.0) with OpenRouter backend. Hermes Swarm refers to the ad-hoc agent orchestration patterns tested on the Windows Hermes gateway (`192.168.2.32:8642`).

| Dimension | **Ruflo Swarm** | **Hermes Swarm** (ad-hoc) |
|-----------|-----------------|---------------------------|
| **Architecture** | 5 fixed-role agents via Hermes CLI → OpenRouter | Dynamic agent counts via Windows Hermes gateway |
| **Agent Specialization** | ✅ 5 roles: audit_researcher, audit_quant, github_hygiene, bug_hunter, strategist | ❌ Generic agents, role assigned per-task |
| **Free Tier** | ✅ OpenRouter free models (gemini-pro, deepseek-chat, mistral-7b, hy3-preview) | ❌ Requires paid API keys on Windows box |
| **Failover** | ✅ 3-attempt model rotation (gemini→deepseek→mistral→hy3) | ❌ Single model per call |
| **Concurrency** | ⚠️ Sequential (Hermes runs one agent at a time) | ✅ Can run parallel if gateway configured |
| **Cost/Run** | $0 (free) / varies (paid) | Varies (paid keys only) |
| **WSL Bridge** | ✅ Native `wsl bash -c` from Windows Codebuff | ❌ Windows-only |
| **Output Aggregation** | ✅ `COMPILED_latest.json` + `AGGREGATED_insights.md` | ❌ Ad-hoc, no standard format |
| **Wizard/UX** | ✅ Interactive `/swarm-ruflo wizard` + slash commands | ❌ CLI only |
| **Reliability** | ⚠️ Free tier hit-or-miss (429s common) | ✅ High (dedicated Windows GPU/paid APIs) |
| **Best For** | Strategy, audit, bugs, continuous monitoring | Low-latency, high-quality single tasks |

### Verdict: **Ruflo Swarm is BETTER for multi-agent research/audit workflows**

**Why:**
1. **Agent specialization** yields higher-quality outputs per role (quant vs researcher vs strategist)
2. **Structured output aggregation** enables cross-validation and audit trail
3. **Free tier works** — no paid keys required for baseline operation
4. **Failover chain** survives OpenRouter free-tier overload
5. **WSL bridge** enables Windows-based Codebuff to drive Linux-resident swarms

**When to use Hermes instead:**
- Single-task, latency-sensitive coding (Hermes + paid keys = faster)
- When you need true parallel execution (Hermes gateway can run concurrent agents)

---

## 🔄 tools/swarm_v2 vs Ruflo Swarm — Engine Comparison

> **tools/swarm_v2** = the 6-engine architecture in `core/v2/engines/` (this repo's v2 layer). **Ruflo** = separate orchestrator in `.ruflo/` using Hermes Agent.

| Dimension | **tools/swarm_v2 (6 Engines)** | **Ruflo Swarm (5 Agents)** |
|-----------|--------------------------------|----------------------------|
| **Engine Count** | 6 specialized orchestrators | 1 orchestrator, 5 agent roles |
| **Parallelism** | ✅ True asyncio + ThreadPoolExecutor | ⚠️ Sequential via Hermes CLI |
| **Memory System** | ✅ ChromaDB vector store + hybrid search | ❌ File-based (`swarm_runs/ruflo-insights/`) |
| **Skill Export** | ✅ `swarm skill export` (Claude/OpenAI formats) | ❌ Not implemented |
| **Safety/Guards** | ✅ AST static analysis, sandboxed tests | ⚠️ Sanitization only |
| **Model Transport** | Proxy-first (LiteLLM) + direct upstream | Hermes internal routing → OpenRouter |
| **Free Tier Support** | ✅ `ULTRA_FREE_*` groups in proxy config | ✅ OpenRouter free models |
| **Cost Ceiling** | ✅ `cost_cap_usd` per SwarmTask (hard abort) | ❌ Advisory only |
| **Health Gates** | ✅ `is_live()` checks `content` + `reasoning_content` | ❌ Not implemented |
| **CLI** | `swarm <engine> ...` (Click) | `/swarm-ruflo <swarm>` (slash) + `orchestrator.py` |
| **Testing** | 13 test files, 300+ tests | 0 automated tests |
| **Production Ready** | ✅ Yes (PR review, CI monitoring, coding) | ⚠️ Beta — audit/strategy only |

### Verdict: **tools/swarm_v2 is SUPERIOR for production engineering workflows**

**Why tools/swarm_v2 wins:**
1. **True parallelism** — asyncio + ThreadPoolExecutor vs Hermes sequential CLI
2. **Persistent memory** — ChromaDB + BM25/vector search enables knowledge accumulation
3. **Skill export** — outputs become reusable Claude/OpenAI skills
4. **Safety framework** — AST analysis, sandboxed execution, tool allowlisting
5. **Hard cost ceilings** — prevents runaway spend on paid models
6. **Comprehensive test suite** — 300+ tests vs zero for Ruflo

**When to use Ruflo instead:**
- Free-tier-only environments (no paid keys, no local GPU)
- Strategy/audit work where agent specialization > parallelism
- Windows-based workflows needing WSL bridge
- Quick ad-hoc research without infrastructure setup

---

## 🎯 AI_MENU / Swarm Picker — Tool Selection Guide

From `cli/swarm_picker.py` — choose by goal:

| Option | Goal | Tool | Engine | Characteristic |
|--------|------|------|--------|----------------|
| **1** | Quick Second Opinion | `swarm` | CombineTeam | Fast 3-engine consensus |
| **2** | Complex Feature/Coding | `swarmv2` | CodingSwarm | Gen → Review → Test loop |
| **3** | Adversarial/High-Stakes | `swarm-debate` | DebateTeam | Adversarial pressure-testing |
| **4** | Deep Research | `swarm-research` | ResearchSwarm | Diverse candidates → Synthesis |
| **5** | Role-Specialized/Hermes | `ruflo` | RufloOrchestrator | 5 specialized agents |
| **6** | Cheap/Free-only | `swarm-free` | CombineTeam (Free) | Cost-optimized / Zero-cost |

**Recommendation for this repo:**
- **Default**: `swarmv2` (CodingSwarm) for implementation work
- **Research**: `swarm-research` + retrieval (not memory-only)
- **Free-tier only**: `ruflo` with `--tier free`
- **PR Review**: `swarmv2 pr-review`
- **CI Health**: `swarmv2 actions`

---

## 🔧 Critical Fixes Applied (2026-11-13)

### 1. LiteLLM Concurrency Serialization
**File:** `tools/start_litellm_proxy.sh:435`
**Fix:** `--num_workers 1` → `--num_workers 4` (or bypass proxy for fan-out leg)
**Impact:** Swarm parallelism now actual, not theoretical

### 2. Health Gate for Thinking Models
**File:** `core/combine_team.py`, `core/debate_team.py`
**Fix:** `is_live()` checks `reasoning_content` when `content` empty
**Impact:** qwen3, LOCAL_CHAT, LOCAL_CODE no longer misreported as dead

### 3. Free-Key Admission Test
**File:** `probe_providers.py`
**Fix:** Every key must pass: (1) tool-calls, (2) 34k-token context, (3) chat-level auth
**Impact:** Dead keys (NVIDIA, SambaNova, Groq-TPM, dead Gemini) excluded from pool

### 4. Proxy-First Pattern Enforcement
**Rule:** No swarm reads `dbpasses.txt` directly. Launcher owns keys; proxy holds them.
**One env var:** `LITELLM_BASE_URL=http://localhost:4000/v1`

---

## 📈 Benchmark: BROKENMERMAIDTEST (16 Models)

| Model | Solved? | Cost | Notes |
|-------|---------|------|-------|
| 14/16 free/paid | ✅ Yes | ~$0.001–$0.0023 | All capable; concurrency was the bottleneck |
| NVIDIA Kimi/GLM/DeepSeek | ❌ 404/timeout | — | Only Nemotron 3.5 works |
| SUBQ_FREE/TOKEN | ❌ 9-word stubs | — | Decision models, not writers |

**Key Finding:** Model capability is NOT the differentiator — **concurrency architecture is**.

---

## 🚀 Quick Start

```bash
# Install
pip install -r requirements.txt

# Start proxy (hardened config)
bash tools/start_litellm_proxy.sh

# Run a coding swarm
python3 -m core.v2.engines.coding_swarm --task "Add retry logic to API client"

# Run research swarm
python3 -m core.v2.engines.research_swarm --topic "ServiceNow IRE reconciliation"

# Run PR review
python3 -m core.v2.engines.pr_review_swarm --repo eltonaguiar/findtorontoevents_antigravity.ca --pr 123

# Run Ruflo audit (free tier)
python3 .ruflo/orchestrator.py --swarm audit --tier free --no-verify

# Interactive picker
python3 cli/swarm_picker.py
```

---

## 📚 Key Documentation

| File | Purpose |
|------|---------|
| `SWARM_ARCHITECTURE_COMPARISON.md` | Industry patterns + our implementations |
| `SWARM_CONCURRENCY_RESEARCH_2026-11-13.md` | LiteLLM hardening, token bucket, circuit breakers |
| `SWARM_FREE_KEYS_FINDINGS_2026-11-13.md` | Crash root cause + free-key research patterns |
| `SWARM_MODEL_ASSESSMENT_SERVICENOW_RESEARCH_2026-11-13.md` | Model eval with/without retrieval |
| `SWARM_RESEARCH_PATTERNS_2026-11-13.md` | How pro swarms (gpt-researcher, STORM, open_deep_research) work |
| `FEEDBACK_FROM_OPENCODE/hermes/hermes-peer-review.md` | P0/P1 defects in our orchestration code |

---

## ⚠️ Known Limitations

1. **No true distributed swarm** — all agents run in-process (ThreadPoolExecutor)
2. **Ruflo has no tests** — `tools/swarm_v2` has 300+ tests; Ruflo has 0
3. **Free-tier research quality ceiling** — 3/4 on expert benchmarks even with retrieval
4. **Hermes gateway bind-address** — defaults to `127.0.0.1`; needs `0.0.0.0` for LAN access
5. **LiteLLM `--num_workers 1`** — must be raised for production swarm traffic

---

## 📄 License

MIT — see `LICENSE` (if present) or individual file headers.
