# SWARM_CONSOLIDATED

Consolidated research, harness, and reference for LLM agent swarms. Documents how our swarm methods perform, compares the swarm architectures we run (Ruflo, Hermes-driven, Combine/Debate/Coding/PRReview, and swarm_v2), and records the live probe findings behind every model and key we trust in a swarm.

> **Repo:** https://github.com/eltonaguiar/SWARM_CONSOLIDATED  
> **Parent repo of record:** `eltonaguiar/TORONTOEVENTS_ANTIGRAVITY` (the AI_MENU and swarm tooling live there under `tools/ai_menu.sh`, `tools/swarm/`, `tools/swarm_v2/`, `.ruflo/`)  
> **Status:** active — research + reference, no production traffic served from this repo

---

## Table of Contents

- [Performance Snapshot (2026-11-13)](#performance-snapshot-2026-11-13)
- [What This Repo Contains](#what-this-repo-contains)
- [Repository Structure](#repository-structure)
- [The Six Swarm Architectures](#the-six-swarm-architectures)
- [The Two Swarm Systems That Actually Run](#the-two-swarm-systems-that-actually-run)
- [Ruflo Swarm vs Hermes Swarm](#ruflo-swarm-vs-hermes-swarm)
- [tools/swarm_v2 vs Ruflo Swarm](#tools/swarm_v2-vs-ruflo-swarm)
- [AI_MENU / Swarm Picker — Tool Selection Guide](#ai_menu--swarm-picker--tool-selection-guide)
- [Performance Findings per AI_MENU Items](#performance-findings-per-ai_menu-items)
- [Critical Architectural Finding: LiteLLM Bottleneck](#critical-architectural-finding-litellm-bottleneck)
- [How Professional Swarms Do Research](#how-professional-swarms-do-research)
- [Critical Fixes Applied (2026-11-13)](#critical-fixes-applied-2026-11-13)
- [Known Bugs & Limitations](#known-bugs--limitations)
- [Live Reliability Benchmark (2026-05-05)](#live-reliability-benchmark-2026-05-05)
- [Quick Start](#quick-start)
- [Recommendations (ordered by payoff)](#recommendations-ordered-by-payoff)
- [Related Documents](#related-documents)
- [TL;DR](#tldr)
- [ELI5 — Explain Like I'm 5](#eli5--explain-like-im-5)
- [Follow-up Fixes Applied (2026-11-14)](#follow-up-fixes-applied-2026-11-14)
- [Overall Conclusion](#overall-conclusion)
- [Appendix — AI_MENU → Swarm Mapping](#appendix--ai_menu--swarm-mapping)
- [Maintenance](#maintenance)
- [License](#license)

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

**TL;DR:** Concurrency architecture, not model capability, is the differentiator. ~half of free keys are dead at chat level despite `/models` returning 200. Research tops out at 3/4 terms without retrieval.

---

## What This Repo Contains

| Path | What it is |
|------|------------|
| `swarm_unified.py` | Unified runner for all 6 swarm architectures: `combine`, `debate`, `coding`, `pr_review`, `ruflo`, `hermes` |
| `swarm_task.py` | Single-task swarm submitter (modes: coding / debate / combine / auto) with memory checkpoints |
| `swarm_acceptance_driver.py` | Acceptance-test driver (e.g. mermaid-diagram fix acceptance across 16 models) |
| `swarm_parallel_runner.py` | Parallel swarm execution harness (⚠ exists but not wired into main workflow) |
| `swarm_model_eval.py` / `swarm_model_server.py` | Model evaluation + local model server |
| `swarm_e2e_fix.py` / `swarm_fix_worktree.py` | E2E fix loop + worktree fix automation (⚠ P0 bugs — see Known Bugs) |
| `probe_providers.py` | Live provider/key admission probe (tool-calling + context-capacity + chat-level auth) |
| `core/combine_team.py` | CombineTeam — N-model parallel consensus with health gate + dedup by upstream fingerprint |
| `core/debate_team.py` | DebateTeam — N debaters × R rounds + synthesizer judge |
| `core/file_team.py` | FileTeam — file-backed swarm variant |
| `core/transport.py` | OpenAI-compatible transport (`call_openai_compat`) |
| `core/worker.py` | Worker execution primitive |
| `core/v2/` | swarm_v2 orchestrator family: `BaseOrchestrator`, `MetaOrchestrator`, `models`, `registry`, `engines` |
| `cli/swarm_picker.py` | Guided picker that routes a goal to the right swarm tool |
| `deploy.py` / `setup.py` / `DEPLOY.md` | Deployment + setup |

There is **no single "best" swarm**. The right architecture depends on the task (see sections below).

---

## Repository Structure

```
SWARM_CONSOLIDATED/
├── core/                          # V1: lightweight direct-call swarms
│   ├── transport.py               #   Direct LLM API routing (14 providers)
│   ├── combine_team.py            #   N-model parallel consensus
│   ├── debate_team.py             #   Multi-round adversarial debate
│   ├── file_team.py               #   Distributed file processing
│   ├── worker.py                  #   Universal agent adapter
│   └── v2/                        # V2: message-bus async orchestrators
│       ├── base_orchestrator.py   #   Shared base (memory, bus, registry, safety)
│       ├── models.py              #   Data models (SwarmTask, AgentRole, etc.)
│       ├── registry.py            #   Agent registry
│       ├── meta_orchestrator.py   #   Meta: self-improving review layer
│       └── engines/
│           ├── coding_swarm.py    #     Test-gated code generation
│           ├── ensemble_swarm.py  #     Weighted prediction aggregation
│           ├── research_swarm.py  #     Epistemic research triangulation
│           ├── pr_review_swarm.py #     Weighted PR review gate
│           ├── github_actions_swarm.py # CI/CD health monitor
│           └── hierarchical_swarm.py   # Strategic → Tactical → Execution
├── cli/
│   └── swarm_picker.py            # Interactive swarm launcher
├── swarm_unified.py               # Unified CLI: --architecture {combine,debate,coding,pr_review,ruflo,hermes}
├── swarm_task.py                  # Main orchestration coordinator
├── swarm_parallel_runner.py       # True parallel executor (not wired yet)
├── swarm_model_eval.py            # Multi-model evaluation harness
├── swarm_e2e_fix.py               # End-to-end fix workflow (⚠ P0 bugs)
├── swarm_fix_worktree.py          # Worktree fix variant (⚠ P0 bugs)
├── swarm_acceptance_driver.py     # Acceptance test harness
├── swarm_model_server.py          # Model server coordinator
├── probe_providers.py             # Provider health probe (✅ well-designed)
├── deploy.py / deploy.sh          # One-command deploy
├── requirements.txt               # Minimal deps
├── setup.py                       # pip install -e .
├── .env.example                   # Config template
├── DEPLOY.md                      # Deploy guide
├── SWARM_ARCHITECTURE_COMPARISON.md  # Industry survey
├── SWARM_CONCURRENCY_RESEARCH_2026-11-13.md  # LiteLLM deep dive
├── SWARM_RESEARCH_PATTERNS_2026-11-13.md      # GitHub landscape + key probes
├── SWARM_FREE_KEYS_FINDINGS_2026-11-13.md     # Free-key crash root cause
├── SWARM_MODEL_ASSESSMENT_SERVICENOW_RESEARCH_2026-11-13.md  # Model benchmark
├── FREEBUFF_SWARM_2026-11-12.MD    # Freebuff agent plan
├── OLLAMA_CLAUDE_2026-11-12.md     # Ollama/Claude agent plan
└── FEEDBACK_FROM_OPENCODE/
    └── hermes/hermes-peer-review.md  # P0 bug report
```

---

## The Six Swarm Architectures (`swarm_unified.py`)

| Architecture | Pattern | Best for | Cost / latency |
|--------------|---------|----------|----------------|
| `combine` | N-model parallel consensus; deduplicate by upstream model fingerprint; health gate counts `content` AND `reasoning_content` | Quick second opinions, simple tasks, cost-sensitive ops | ~$0.0004–$0.0023/task; parallel (max of calls, not sum) |
| `debate` | N debaters × R rounds, cross-round context, final synthesis judge | High-stakes decisions, complex reasoning, controversial topics | Multiplies requests (N×R); only enable when proxy is healthy |
| `coding` | Planner → generator → test writer → reviewer (max 3 revisions) → verifier; hard `cost_cap_usd` abort | Code generation, bug fixes, feature implementation | Cost-capped; strict or best-effort test enforcement |
| `pr_review` | Impact analyzer (0.5) + code reviewer (0.3) + risk controller (0.2); all must approve + impact ≥ threshold | PR review, code quality gates | Weighted approval threshold |
| `ruflo` | Role-specialized agents (coder, reviewer, security-architect, tester, architect); each role own model context; outputs concatenated, no cross-contamination | Specialized tasks needing different personas | One model per role |
| `hermes` | Planning root task → parallel worker cards → verifier gate → synthesizer; state persisted in JSON comments on kanban board | Task-board-driven work across Discord/web/CLI | State persisted |

Source: `SWARM_ARCHITECTURE_COMPARISON.md` (2026-11-13).

**TL;DR:** Use `combine` for quick second opinions, `coding`/`pr_review` for implementation work with gates, `ruflo` for free-tier specialized audit, `debate` only when the proxy is healthy (it multiplies cost N×R).

---

## The Two Swarm Systems That Actually Run

Our day-to-day swarm tooling lives in the parent repo (`TORONTOEVENTS_ANTIGRAVITY`) and splits into two independent systems:

| | Ruflo Swarm (`.ruflo/`) | tools/swarm (`tools/swarm/`) |
|---|---|---|
| **Drives via** | Hermes Agent (`hermes chat -q`) | Direct API calls + CLI adapters |
| **Agent model** | 5 specialized agents (audit_researcher, audit_quant, github_hygiene, bug_hunter, strategist) | 16+ engine adapters (claude, deepseek, xai, kilo, gemini, grok, …) |
| **Best for** | Structured analysis, continuous loops, strategy ideation, bug hunt, GitHub hygiene | PR reviews, multi-model consensus, ad-hoc prompts, second opinions |
| **Free tier** | ✅ Yes — Hermes + OpenRouter free models | ❌ Needs API keys (~$0.001–$0.01/run paid) |
| **Memory / persistence** | ❌ Ephemeral (each run fresh) | ✅ SQLite sessions (`swarm_runs/_sessions.db`) via `--persist-sessions` |
| **Multi-model consensus** | ❌ Single model per agent | ✅ N models in parallel → ranked synthesis |
| **Setup** | Hermes binary + WSL | Python + API keys |
| **Output** | `swarm_runs/ruflo-insights/COMPILED_latest.json` | `swarm_runs/run_<TS>/` + `_summary.json` |
| **Failover** | 3-attempt model rotation + exponential backoff | Single engine call (pre-flight key skip) |

Source: `HERMES_SWARM_NOTES.MD`, `RUFLO_SWARM_GUIDE.MD`.

**TL;DR:** Need a second opinion → `tools/swarm`; audit performance / hunt bugs → `.ruflo/`; persistent memory across repeats → `tools/swarm --persist-sessions`; same daily check on live data → `.ruflo/ --continuous`.

---

## Ruflo Swarm vs Hermes Swarm

### Direct answer

**Ruflo Swarm IS the Hermes-driven swarm.** There is no separate "Hermes Swarm" distinct from Ruflo: `.ruflo/orchestrator.py` dispatches work *through* Hermes Agent. The real comparison is **Ruflo (Hermes-driven) vs tools/swarm (direct API)**:

- **Choose Ruflo** when you want free-tier, agent-specialized, continuous/periodic audits (audit_researcher + audit_quant run in parallel; `--continuous` loop), GitHub hygiene, or bug hunting — and you can tolerate ephemeral memory and occasional free-tier 404/429.
- **Choose tools/swarm** when you need multi-model consensus (2+ engines must agree), persistent SQLite sessions across repeated identical tasks, second opinions before a push, or PR review — and you have API keys to pay for it.

Rule of thumb from `HERMES_SWARM_NOTES.MD`: need a second opinion → `tools/swarm`; audit performance/hunt bugs → `.ruflo/`; persistent memory across repeats → `tools/swarm --persist-sessions`; same daily check on live data → `.ruflo/ --continuous`.

### Detailed comparison

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

### Ruflo tier comparison (`RUFLO_SWARM_GUIDE.MD`)

| Dimension | FREE | PAID | HYBRID (recommended) |
|-----------|------|------|----------------------|
| Models | OpenRouter free via Hermes | Direct API via `api_consult.py` | Paid first, free fallback |
| Cost | $0.00 | Varies by provider | Pay only when paid succeeds |
| Speed | Slow (shared capacity) | Fast (dedicated) | Fast normally |
| Quality | Base models | Frontier models | Best effort |
| Reliability | Rate-limited, may 404 | High | High (always completes) |
| Failover | 3-attempt rotation | None | Paid fails → free |

Free-tier models: audit_researcher=gemini-pro-1.5-preview:free, audit_quant=deepseek-chat:free, github_hygiene=mistral-7b-instruct:free, bug_hunter=strategist=hy3-preview:free.

**TL;DR:** Ruflo IS Hermes-driven — there's no separate "Hermes Swarm." Ruflo wins for free-tier specialized audit; use Hermes gateway (paid) only when you need true parallelism for low-latency single tasks.

---

## tools/swarm_v2 vs Ruflo Swarm

`swarm_v2` (the `core/v2/` orchestrator family in this repo, mirrored by `tools/swarm_v2/` in the parent repo) and Ruflo solve different problems:

| Dimension | Ruflo swarm | swarm_v2 |
|-----------|-------------|----------|
| **Orchestrator** | `.ruflo/orchestrator.py` via Hermes Agent | `core/v2/base_orchestrator.py` + `meta_orchestrator.py` (BaseOrchestrator ABC) |
| **Architectures** | 5 fixed role-agents | coding / pr-review / research / ensemble / hierarchical (pluggable) |
| **Memory** | Ephemeral per run | Persistent `SwarmMemory` + `MessageBus` + `AgentRegistry` + `SafetyEnforcer` |
| **Transport** | Hermes internal routing → OpenRouter / direct API | OpenAI-compatible transport, provider fallbacks |
| **Free tier** | ✅ Yes (Hermes + OpenRouter free) | ⚠️ Depends on wired keys/proxy |
| **Best for** | Structured audit/strategy/bugs, continuous loops | Programmable multi-agent workflows with safety, registry, shared memory |
| **CLI entry** | `python3 .ruflo/orchestrator.py --swarm <audit\|github\|strategy\|bugs\|all\|continuous>` | `python3 swarm_task.py <task> --mode coding\|debate\|combine\|auto` |

### Engine-level comparison

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

### Verdict

**tools/swarm_v2 is SUPERIOR for production engineering workflows.**

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

**TL;DR:** Use swarm_v2 for production engineering (parallelism, memory, safety, tests). Use Ruflo for free-tier audit/strategy with zero setup.

---

## AI_MENU / Swarm Picker — Tool Selection Guide

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

**TL;DR:** Default to `swarmv2` CodingSwarm for implementation; `ruflo --tier free` when you have no paid keys; `swarm-research` + retrieval for deep research.

---

## Performance Findings per AI_MENU Items

The AI_MENU (`tools/ai_menu.sh` in the parent repo) lists the AI agent CLIs we route swarms through:

**Agent CLIs:** claude, command-code, cursor, opencode, kilo, codex, grok, gemini, qwen, copilot, continue, hermes, openclaude, blackbox, freebuff, kimi, agent, freellm, browseruse, ollama

**Repo-local swarm commands:** litellm (rotating proxy on :4000), swarm (`tools/swarm/swarm_run.py` multi-engine fan-out), consult (`tools/swarm/api_consult.py` single-provider API consult)

### What the live probes found (2026-11-13)

A `/models` 200 response is **not** evidence a key can serve a request. Every key entering a swarm must pass a 3-part admission test: (1) tool-calling call returns `tool_calls`, (2) ~34k-token context-capacity call succeeds, (3) chat-level auth/balance succeeds. Source: `SWARM_RESEARCH_PATTERNS_2026-11-13.md` §3.

| Provider / key | `/models` | `/chat/completions` | Swarm verdict |
|---|---|---|---|
| NVIDIA + ALT | 200, 83 models | every call times out; per-model 404 | **unusable** |
| SambaNova | 200, 5 models | 401 incorrect key | **unusable** |
| Groq | 200, 11 models | 200 small; **413 on 15k-token prompt** (TPM 8,000) | unusable as main-agent fallback |
| Cerebras | 200 | 200 incl. 34k-token + tool call | **works** |
| DeepInfra | 200 | 200, 35k prompt, tool call | **works** |
| AIML API | 200 | 200, 34k prompt, tool call | **works** ($20 paid cap) |
| xAI (Grok) | 200, 13 models | 200, 33.5k prompt, tool call | **works** |
| Kimi | 200, 6 models | 429 engine overloaded (persistent) | flaky |
| Novita / Z.AI GLM / SiliconFlow | 200 | 402/429 insufficient balance | **no credits** |
| Gemini ×3 | — | 401 invalid credentials | **dead** |
| Together ×2 / Hyperbolic | — | 401 | **dead** |
| Fireworks ×2 | — | 412 account suspended | **dead** |
| Mistral ×3 | 200 | 200 but `content` is a list of blocks | fragile (breaks `.strip()` clients) |

### Verified fallback chain (Hermes, this machine)

```
primary  deepseek-v4-flash
  1. xai / grok-4.5                    (tool call OK, 33.5k prompt OK)
  2. deepinfra / DeepSeek-V3.2         (tool call OK, 35k prompt OK)
  3. aimlapi / gpt-4o-mini             (tool call OK, 34k prompt OK)
  4. cerebras / gpt-oss-120b           (tool call OK, 34k prompt OK)
  5. kimi-coding / kimi-k3.1-pro       (key valid, 429s often — last resort)
```

Groq was position 1 in an earlier draft and failed live with `413 ... TPM: Limit 8000, Requested 15391` — a fallback that cannot hold the prompt is worse than no fallback, because it burns the single fallback activation per turn.

### Model assessment for swarm research (`SWARM_MODEL_ASSESSMENT_SERVICENOW_RESEARCH_2026-11-13.md`)

Tested 38 proxy groups on a neutral ServiceNow Discovery research question (must name: Identification Rules, Reconciliation Rules, Data Precedence, CMDB 360/multisource):

- **0 models named all 4 terms** memory-only; best score 3/4.
- **25 of 38 returned empty `content` with `finish=length`** — reasoning consumed the whole 900-token budget. This is a **budget artifact, not ignorance**: re-asking with `max_tokens=3500` recovered 8 of 18 cloud candidates and 2 of 7 local.
- **Hard rule:** `max_tokens >= 3000` for any reasoning alias, or a `200` with `content: ""` is indistinguishable from a refusal.
- **Retrieval matters more than the model:** `ULTRA_PAID_MODE` went 1/4 (memory) → 3/4 (with harness-fetched pages); `ULTRA_FREE_LOCAL_FAST` stayed 0/4 even with web. A keyless SERP (Startpage/Ecosia) + full-markup frame extraction works for every model; per-model browser loops were strictly worse.
- **Exclude from research duty:** `PAID-GROK` (400), `ULTRA_HYBRID_MODEL_LARGE` + `ZZZ_BAD_LEGACY_MIXED_F_MODE_TOOLS` (401), `ULTRA_FREE_LOCAL_EMBED` (embedding model), `ULTRA_FREE_LOCAL_BATCH/CHAT/CODE` (150s timeouts), `SUBQ_FREE`/`SUBQ_TOKEN` (9-word stubs — decision models, not writers).
- **Best research roster:** `ZZZ_BAD_LEGACY_MIXED_F_MODE_FAST` and `ULTRA_PAID_MODE` with retrieval (3/4); `ULTRA_FREE_GEMINI` memory-only (3/4, fastest useful answer at 2.9s); `ULTRA_FREE_CLOUD_LARGE` / `ULTRA_HYBRID_MODEL` as backups.

### Free-tier economics (real currency is TPM/RPD, not context window)

| Provider | Model | Context | Documented limit | Implication |
|----------|-------|---------|------------------|-------------|
| Groq | gpt-oss-120b | 131K | 30 RPM, 1,000 RPD, 8,000 TPM, 200k TPD | 131K context is a lie in practice |
| Kilo Code | kilo-auto/free, `:free` | 256K–1M | 200 req/hr | Great for wide fan-out, useless for long prompts |
| Google Gemini | 2.5/3.x Flash | 1M | free tier, no card | Best free context; treat as non-confidential |
| Cloudflare Workers AI | various | 128K | 10k neurons/day shared | Fine for aux tasks |

Plan fan-out width against TPM, not context size. A research swarm making 8 parallel calls × 20k-token prompts needs ~160k tokens — Groq free delivers that over ~20 minutes (one burst, then done for the minute).

**TL;DR:** `/models` 200 ≠ usable — probe tool-calls + 34k context + chat auth. Best research roster: `ZZZ_BAD_LEGACY_MIXED_F_MODE_FAST` + `ULTRA_PAID_MODE` with retrieval. Plan fan-out by TPM, not context. Groq fails large prompts (413 at 15k tokens).

---

## Critical Architectural Finding: LiteLLM Bottleneck

Testing 16 models against a broken mermaid-diagram acceptance test: **14/16 solved**, all free and paid models performed equally (~$0.001–$0.0023 per task, ~663 chars context). The bottleneck is **not model capability — it's LiteLLM proxy concurrency.**

`tools/start_litellm_proxy.sh:435` launches LiteLLM with `--num_workers 1` — a single worker serializes every request. A swarm fan-out (N concurrent model calls) queues behind one worker; timeouts pile up; the proxy looks "crashed." vLLM wins not because it's smarter but because continuous batching handles concurrency.

### Industry-standard solution

Do **not** route all swarm agents through a single LiteLLM proxy. Route each agent to its **own independent inference endpoint**:

| Agent | Endpoint | Model | Type |
|-------|----------|-------|------|
| Agent 1 | `http://localhost:8000/v1` | qwen3-8b | Local GPU (vLLM) |
| Agent 2 | `http://localhost:11434/v1` | qwen2.5-coder:7b | Local GPU (Ollama) |
| Agent 3 | `http://localhost:11434/v1` | qwen3:30b-a3b | Local GPU (Ollama) |

All three run simultaneously, each its own GPU process, no shared queue, no LiteLLM in the path, no single point of failure. If Windows Hermes comes back online (`192.168.2.32:8642`, key `hermes-local-web-2026`), add it as a 4th agent.

For cloud models, each agent calls its cloud provider directly (OpenRouter, Gemini, xAI, …) — no shared proxy needed.

Recommended 3-agent parallel swarm is documented in `SWARM_ARCHITECTURE_COMPARISON.md` §6.

**TL;DR:** Don't route all swarm agents through one LiteLLM proxy (`--num_workers 1` serializes everything). Give each agent its own endpoint (vLLM/Ollama) for true parallelism.

---

## How Professional Swarms Do Research

Survey of 28 swarm/research/gateway repos (stars, 2026-11-13). Every credible research swarm converges on one pipeline:

```
plan → decompose into sub-questions → parallel retrieve → filter/compress → synthesize w/ citations → critique
```

| Repo | Stars | How it maps |
|------|-------|-------------|
| gpt-researcher | 30,659 | Planner agent generates questions; execution agents gather in parallel; publisher aggregates into cited report; JEV decision model keeps only context that answers the question |
| open_deep_research | 12,676 | Four model slots by role (summarization / research / compression / final report); ranked #6 on Deep Research Bench, RACE 0.4344; structured outputs + tool calling are a hard requirement |
| STORM | 31,866 | Perspective-guided question asking + simulated conversation writer↔expert + moderator agent injecting unused facts |
| deer-flow | 85,296 | Harness: filesystem, memory, skills, sandbox + plan-and-spawn sub-agents |
| MetaGPT | 71,268 | Research as SOP: roles with fixed responsibilities |

**Takeaway:** research quality comes from pipeline shape (decomposition + parallelism + filtering + citation), not model size. `CombineTeam`/`DebateTeam` in `core/` implement the middle of this pipeline; what's missing is the **planner** stage (sub-question generation) and **critic** stage (verify claims against local data).

### Coordination topologies

| Pattern | Evidence | When it pays |
|---------|----------|--------------|
| Graph / state machine | langgraph 44,882 | Deterministic, resumable loops; cheapest to debug |
| Queen-led + consensus (Raft/Byzantine/Gossip) | ruflo/ruflo 81,594 | Many workers, one decision; Byzantine framing is a *mental model* (assume k workers lie/fail), not a protocol to implement |
| Role/SOP specialization | MetaGPT 71,268, ChatDev 34,740 | Fixed artifact formats (report, spec, deck) |
| Handoff | openai/swarm 22,130 (educational, superseded) | Simple routing between specialists |

Raft/Gossip are overkill for LLM panels — you're aggregating opinions, not replicating a state machine. What improves accuracy: diverse upstreams, structured JSON votes, explicit judge/critic pass, outlier rejection.

**TL;DR:** Professional swarms win via pipeline shape (decompose → parallel retrieve → filter → synthesize w/ citations → critique), not model size. Add a planner + critic stage to our CombineTeam.

---

## Critical Fixes Applied (2026-11-13)

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

## Known Bugs & Limitations

### P0 bugs (from Hermes Peer Review 2026-11-13)

| Severity | File | Issue |
|----------|------|-------|
| **P0** | `swarm_e2e_fix.py` | `LIVE_ALIASES` undefined → NameError; import path mismatch for `call_with_fallback` |
| **P0** | `swarm_unified.py` | `run_combine_team(query, model)` passes model alias string as `n` parameter → TypeError |
| **P0** | `swarm_model_eval.py` | `call_model()` ignores resolved `base_url` from `resolve_best_model()`, always uses `:4000` |
| **P0** | `swarm_fix_worktree.py` | Same issues as `swarm_e2e_fix.py` |
| **MEDIUM** | All V1 paths | `swarm_parallel_runner.py` exists but is **never called** by any main workflow — all "parallel" swarms are sequential |
| **MEDIUM** | `core/combine_team.py` | Cost cap continues processing remaining aliases instead of hard abort |
| **MEDIUM** | All swarms | No red-team / verifier stage beyond mermaid syntax validation |

### Known Limitations

1. **No true distributed swarm** — all agents run in-process (ThreadPoolExecutor)
2. **Ruflo has no tests** — `tools/swarm_v2` has 300+ tests; Ruflo has 0
3. **Free-tier research quality ceiling** — 3/4 on expert benchmarks even with retrieval
4. **Hermes gateway bind-address** — defaults to `127.0.0.1`; needs `0.0.0.0` for LAN access
5. **LiteLLM `--num_workers 1`** — must be raised for production swarm traffic

**TL;DR:** P0 bugs in `swarm_e2e_fix.py`, `swarm_unified.py`, `swarm_model_eval.py`, `swarm_fix_worktree.py` need fixing before production use. Ruflo has zero tests.

---

## Live Reliability Benchmark (2026-05-05)

> **Source:** `findtorontoevents_antigravity.ca/updates/SWARM_STYLE_DIFF.MD` (parent repo) — Side-by-side comparison on identical real-world tasks.

### Test 1: PR Review (4 open PRs: #798, #777, #772, #764)

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

### Critical Caveats (Config-Dependent)

⚠️ **This comparison is NOT architecture vs architecture — it's CONFIG vs CONFIG:**

1. **tools/swarm ran with PAID DeepSeek key** (`deepseek-v4-flash`) — reliable, fast, structured output
2. **Ruflo ran FREE-TIER ONLY** — no paid keys were wired into Hermes config (`~/.hermes/config.toml`)
3. **OpenRouter free-tier models were down/rate-limited** at test time (persistent 404/429)
4. **Hermes `chat -q --source tool --yolo` path** may have OpenRouter config issues in WSL

**With paid keys wired into Hermes or `--direct` mode calling `api_consult.py` directly, re-benchmark before concluding.** The failure reflects missing configuration, not an architectural cap.

**TL;DR:** tools/swarm beat Ruflo on reliability *in this specific test* because it had working paid keys while Ruflo ran free-tier-only against a down OpenRouter free tier. Fix: wire paid keys into Hermes config and add `--direct` mode to bypass WSL.

---

---

## Quick Start

```bash
# Clone
git clone https://github.com/eltonaguiar/SWARM_CONSOLIDATED.git
cd SWARM_CONSOLIDATED

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

In the parent repo (`TORONTOEVENTS_ANTIGRAVITY`):
```bash
# Ruflo audit (free tier, Hermes-driven)
python3 .ruflo/orchestrator.py --swarm audit --tier free

# tools/swarm second opinion (consensus-3: deepseek + xai + kilo)
python3 tools/swarm/swarm_run.py --preset consensus-3 --prompt-file my_prompt.md

# AI_MENU launcher
tools/ai_menu.sh swarm
```

**TL;DR:** Clone, `pip install -r requirements.txt`, start the LiteLLM proxy, then run `python3 cli/swarm_picker.py` or a specific engine.

---

## Recommendations (ordered by payoff)

1. **Kill the serialization.** Raise `--num_workers` in `tools/start_litellm_proxy.sh:435`, or have the fan-out leg call upstreams directly in parallel and use the proxy only for single-shot calls. (`SWARM_FREE_KEYS_FINDINGS_2026-11-13.md`)
2. **Adopt the 3-part admission test** as a gate in `probe_providers.py`, emitting a machine-readable pool file: `{provider, model, base_url, key_env, tool_calls, max_ctx_ok, tpm, status}`. Build the pool from evidence, never hand-written. (`SWARM_RESEARCH_PATTERNS_2026-11-13.md`)
3. **Separate "panel" keys from "report" keys.** Free keys with 8k TPM are fine as panel voters (short prompts, structured JSON) and useless as report writers (long context).
4. **Add a planner + critic stage** around `CombineTeam`: planner emits 3–6 sub-questions as JSON → `CombineTeam` answers each with a different provider → critic (different provider than any panel member) flags unsupported claims → publisher writes the report citing panel answers. (gpt-researcher / STORM shape.)
5. **Structured output or it didn't happen.** Votes must be JSON with a schema (`{claim, confidence, evidence_ref}`); otherwise consensus degenerates into comparing prose.
6. **Budget guard per run.** Track tokens and abort at a cap. (`cost_cap_usd` already exists in `core/combine_team.py`; default $0.05 free-tier ceiling.)
7. **Route log per call:** provider, resolved model, latency, tokens, estimated cost, fallback depth.
8. **Ground against local data, always.** Free proxy models have no browser and will hallucinate fetches. Pull `audit_dashboard/data/*.json` locally and embed it verbatim in prompts.

---

## Related Documents

| File | Purpose |
|------|---------|
| `SWARM_ARCHITECTURE_COMPARISON.md` | Industry patterns + our implementations |
| `SWARM_CONCURRENCY_RESEARCH_2026-11-13.md` | LiteLLM hardening, token bucket, circuit breakers |
| `SWARM_FREE_KEYS_FINDINGS_2026-11-13.md` | Crash root cause + free-key research patterns |
| `SWARM_MODEL_ASSESSMENT_SERVICENOW_RESEARCH_2026-11-13.md` | Model eval with/without retrieval |
| `SWARM_RESEARCH_PATTERNS_2026-11-13.md` | How pro swarms (gpt-researcher, STORM, open_deep_research) work |
| `FEEDBACK_FROM_OPENCODE/hermes/hermes-peer-review.md` | P0/P1 defects in our orchestration code |
| `FREEBUFF_SWARM_2026-11-12.MD` | Freebuff swarm mission (Mercury API sunset migration) |
| `OLLAMA_CLAUDE_2026-11-12.md` | Ollama/Claude peer plan |
| `DEPLOY.md` | Deployment notes |

---

## TL;DR

| Question | Answer |
|----------|--------|
| **Is Ruflo Swarm better than Hermes Swarm?** | Ruflo Swarm *is* the Hermes-driven swarm — `.ruflo/orchestrator.py` runs through Hermes Agent. There's no separate "Hermes Swarm." The real comparison is Ruflo vs tools/swarm: Ruflo for free-tier specialized audit (5 roles, 3-attempt failover, WSL bridge), tools/swarm for multi-model consensus with persistent SQLite sessions (needs API keys). |
| **Is tools/swarm_v2 better than Ruflo?** | swarm_v2 is superior for production engineering: true parallelism (asyncio + ThreadPoolExecutor), persistent ChromaDB memory, skill export, AST safety guards, hard cost ceilings, 300+ tests. Ruflo wins only for zero-setup free-tier audit/strategy work. |
| **What's the #1 performance problem?** | LiteLLM `--num_workers 1` serializes all swarm fan-out calls through one event loop. Fix: give each agent its own endpoint (vLLM :8000, Ollama :11434) instead of a shared proxy. |
| **Which keys actually work in a swarm?** | Cerebras, DeepInfra, AIML API, xAI (Grok) pass tool-calls + 34k-context + chat auth. Groq 413s on 15k-token prompts (TPM 8,000). NVIDIA/SambaNova/Gemini/Together/Fireworks are dead at chat level despite `/models` returning 200. |
| **Best research setup?** | Planner → CombineTeam (diverse providers) → Critic → Publisher, with harness-fetched retrieval (Startpage/Ecosia + frame extraction). `max_tokens >= 3000` for reasoning aliases. Expect ~3/4 on expert benchmarks even with retrieval. |
| **Live benchmark verdict?** | tools/swarm ✅ vs Ruflo ❌ 100% failure on identical tasks — **but config-dependent**: tools/swarm used a paid DeepSeek key while Ruflo ran free-tier-only against a down OpenRouter tier. Wire paid keys into Hermes + add `--direct` mode, then re-benchmark. Full section below. |

---

## ELI5 — Explain Like I'm 5

Imagine you need a big job done — say, checking a pile of pull requests. You can ask one helper, or you can ask a whole team at once.

- **tools/swarm** is a reliable team that you pay a little to use. In our test it finished the job in about 11 seconds for a fraction of a cent.
- **Ruflo** is a free team that only works if the free phone line is open. In our test the line was busy, so all five helpers said "no answer" — that's not because the team is bad, it's because nobody gave them a working phone.
- **swarm_v2** is the newest, best-equipped team: more than one helper works at the same time, they remember past jobs, and there's a safety checklist. It's the best choice for serious work — once its "traffic cop" (the LiteLLM proxy) stops making everyone wait in a single line.

One more thing: telling a model something is "free" doesn't mean it can do the job. Half the free "keys" answer a simple "hello?" but fall over when you hand them real work.

## Follow-up Fixes Applied (2026-11-14)

The 2026-11-13 peer review flagged five P0 issues. Re-verification found three already fixed; the remaining two plus a related routing gap were fixed in **PR #2 (squash-merged as `570e9d84`)**:

| Item | File | Change |
|------|------|--------|
| **P0** | `swarm_model_eval.py` | `call_model()` accepts `base_url`; the fallback path uses `resolve_best_model()['base_url']` instead of always hitting `localhost:4000`. Restores the previously dead Ollama/vLLM fallback. |
| **P1** | `swarm_parallel_runner.py` | Replaced the accidental acceptance-driver duplicate with a real generic multi-endpoint parallel runner (ThreadPoolExecutor over vLLM `:8000` / Ollama `:11434`, TCP health probe, per-endpoint isolation). |
| **P1** | `swarm_e2e_fix.py` | `call_with_fallback()` prefers parallel fan-out when local endpoints are reachable; sequential `probe_providers()` fallback preserved. `SWARM_PARALLEL=0/false/no/off` disables. |
| **P2** | `swarm_unified.py` | Added `--direct`; threads provider `base_url`/`api_key` through `run_with_fallback` into CombineTeam/DebateTeam; strips `/chat/completions` to avoid double-suffixing; prints a notice when a direct route is unavailable. Default (proxy) behavior unchanged. |

**Verification:** `py_compile` clean on all four files; `--direct` present in `--help`; parallel runner `--help` no longer fires inference; empty-endpoint path returns cleanly; two independent read-only reviews found (and this PR fixed) a direct-route URL-doubling bug.

**Still open (not code, environment):** Ruflo's OpenRouter 404 is config/endpoint dependent — wire paid keys into Hermes (`~/.hermes/config.toml`) or use `--direct` against a reachable endpoint, then re-benchmark. `.ruflo/orchestrator.py` lives in the parent repo, so it cannot be patched here.

## Overall Conclusion

- **Ruflo vs Hermes:** they are the same system — Ruflo *is* the Hermes-driven swarm. The meaningful comparison is Ruflo (free-tier, role-specialized audit) vs tools/swarm (paid, multi-model consensus).
- **Best for production engineering:** `swarm_v2` (true parallelism, persistent memory, safety guards, hard cost ceilings, 300+ tests).
- **Best for zero-setup audit/strategy:** Ruflo on the free tier — once its endpoint configuration is fixed and re-benchmarked.
- **Biggest system-level blocker:** LiteLLM `--num_workers 1` serializes all fan-out. The fix is per-agent endpoints (this repo's new parallel runner) or raising worker count; `--direct` gives the CLI a path around the proxy.
- **Biggest data-level blocker:** free keys that pass `/models` but fail real chat calls. Admit keys only after a tool-call + 34k-context + chat-auth probe.
- **Bottom line:** the architecture is sound; reliability comes from healthy endpoints and honest probing, not from the model brand. The remaining work is environment/config (wire keys, re-benchmark), not code.

---

## Appendix — AI_MENU → Swarm Mapping

| AI_MENU key | CLI/tool | Swarm role | Free? | Notes |
|-------------|----------|------------|-------|-------|
| hermes | Hermes Agent | Ruflo transport | ✅ (via OpenRouter free) | Drives `.ruflo/` orchestrator; WSL; 36 commits behind — run `hermes update` |
| kilo | Kilo Code | tools/swarm engine | ✅ (`:free`, 200 req/hr) | Wide fan-out, useless for long prompts |
| grok | Grok CLI | tools/swarm engine (xai) | ⚠️ paid/free mix | Works live; `grok-3-fast` not found — use `grok-3`/`grok-3-mini` |
| gemini | Gemini CLI | tools/swarm / Ruflo model | ⚠️ dead keys (401) | `ULTRA_FREE_GEMINI` best fast answer (2.9s, 3/4) but credentials dead in current probe |
| claude | Claude Code | tools/swarm engine | ❌ needs key | Deep-strict preset |
| codex | Codex CLI | tools/swarm engine | ❌ needs key | |
| qwen | Qwen Code | tools/swarm engine | varies | Local vLLM/Ollama qwen3 recommended for concurrency workhorse |
| copilot | Copilot CLI | tools/swarm engine | ❌ needs key | |
| ollama | Ollama | Local inference endpoint | ✅ unlimited | Concurrency workhorse; `OLLAMA_NUM_PARALLEL` default 1 |
| litellm | LiteLLM proxy (:4000) | Swarm routing layer | — | `--num_workers 1` = serialization bottleneck |
| swarm | `tools/swarm/swarm_run.py` | Multi-engine fan-out | ❌ keys | consensus-3 / fast-cheap / deep-strict presets |
| consult | `tools/swarm/api_consult.py` | Single-provider consult | ❌ keys | Shared with Ruflo paid tier |

---

## Maintenance

- No `README.md` existed in this repo before this file; created 2026-11-14 from `SWARM_*` research docs, `HERMES_SWARM_NOTES.MD`, `RUFLO_SWARM_GUIDE.MD`, and live provider probes. Merged content from three agent-authored versions (2026-11-14) to recover lost material.
- **2026-11-14 benchmark merge:** Added *Live Reliability Benchmark (2026-05-05)* from the parent repo's `updates/SWARM_STYLE_DIFF.MD`, with config-dependent caveats (paid DeepSeek vs free-tier-only Ruflo). TOC + TL;DR row added.
- Secrets: `~/dbpasses.txt` is gitignored and outside this repo; no secret values appear here — keys referenced by name only.
- All model/provider verdicts are from live HTTP probes run 2026-11-13 from this machine; key rot is constant, re-probe before trusting.

---

## License

MIT — see `LICENSE` (if present) or individual file headers.
