# SWARM_CONSOLIDATED

Consolidated research, harness, and reference for LLM agent swarms. This repo documents how our swarm methods perform, compares the swarm architectures we run (Ruflo, Hermes-driven, Combine/Debate/Coding/PRReview, and swarm_v2), and records the live probe findings behind every model and key we trust in a swarm.

> **Repo:** https://github.com/eltonaguiar/SWARM_CONSOLIDATED  
> **Parent repo of record:** `eltonaguiar/TORONTOEVENTS_ANTIGRAVITY` (the AI_MENU and swarm tooling live there under `tools/ai_menu.sh`, `tools/swarm/`, `tools/swarm_v2/`, `.ruflo/`)  
> **Status:** active — research + reference, no production traffic served from this repo

---

## 1. What this repo contains

| Path | What it is |
|------|------------|
| `swarm_unified.py` | Unified runner for all 6 swarm architectures: `combine`, `debate`, `coding`, `pr_review`, `ruflo`, `hermes` |
| `swarm_task.py` | Single-task swarm submitter (modes: coding / debate / combine / auto) with memory checkpoints |
| `swarm_acceptance_driver.py` | Acceptance-test driver (e.g. mermaid-diagram fix acceptance across 16 models) |
| `swarm_parallel_runner.py` | Parallel swarm execution harness |
| `swarm_model_eval.py` / `swarm_model_server.py` | Model evaluation + local model server |
| `swarm_e2e_fix.py` / `swarm_fix_worktree.py` | E2E fix loop + worktree fix automation |
| `probe_providers.py` | Live provider/key admission probe (tool-calling + context-capacity + chat-level auth) |
| `core/combine_team.py` | CombineTeam — N-model parallel consensus with health gate + dedup by upstream fingerprint |
| `core/debate_team.py` | DebateTeam — N debaters × R rounds + synthesizer judge |
| `core/file_team.py` | FileTeam — file-backed swarm variant |
| `core/transport.py` | OpenAI-compatible transport (`call_openai_compat`) |
| `core/worker.py` | Worker execution primitive |
| `core/v2/` | swarm_v2 orchestrator family: `BaseOrchestrator`, `MetaOrchestrator`, `models`, `registry`, `engines` |
| `cli/swarm_picker.py` | Guided picker that routes a goal to the right swarm tool |
| `deploy.py` / `setup.py` / `DEPLOY.md` | Deployment + setup |

There is **no single "best" swarm**. The right architecture depends on the task (see §4 and §6).

---

## 2. The six swarm architectures (`swarm_unified.py`)

| Architecture | Pattern | Best for | Cost / latency |
|--------------|---------|----------|----------------|
| `combine` | N-model parallel consensus; deduplicate by upstream model fingerprint; health gate counts `content` AND `reasoning_content` | Quick second opinions, simple tasks, cost-sensitive ops | ~$0.0004–$0.0023/task; parallel (max of calls, not sum) |
| `debate` | N debaters × R rounds, cross-round context, final synthesis judge | High-stakes decisions, complex reasoning, controversial topics | Multiplies requests (N×R); only enable when proxy is healthy |
| `coding` | Planner → generator → test writer → reviewer (max 3 revisions) → verifier; hard `cost_cap_usd` abort | Code generation, bug fixes, feature implementation | Cost-capped; strict or best-effort test enforcement |
| `pr_review` | Impact analyzer (0.5) + code reviewer (0.3) + risk controller (0.2); all must approve + impact ≥ threshold | PR review, code quality gates | Weighted approval threshold |
| `ruflo` | Role-specialized agents (coder, reviewer, security-architect, tester, architect); each role own model context; outputs concatenated, no cross-contamination | Specialized tasks needing different personas | One model per role |
| `hermes` | Planning root task → parallel worker cards → verifier gate → synthesizer; state persisted in JSON comments on kanban board | Task-board-driven work across Discord/web/CLI | State persisted |

Source: `SWARM_ARCHITECTURE_COMPARISON.md` (2026-11-13).

---

## 3. The two swarm systems that actually run (parent repo)

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

### Ruflo Swarm vs Hermes Swarm — direct answer

**Ruflo Swarm IS the Hermes-driven swarm.** There is no separate "Hermes Swarm" distinct from Ruflo: `.ruflo/orchestrator.py` dispatches work *through* Hermes Agent. The real comparison is **Ruflo (Hermes-driven) vs tools/swarm (direct API)**:

- **Choose Ruflo** when you want free-tier, agent-specialized, continuous/periodic audits (audit_researcher + audit_quant run in parallel; `--continuous` loop), GitHub hygiene, or bug hunting — and you can tolerate ephemeral memory and occasional free-tier 404/429.
- **Choose tools/swarm** when you need multi-model consensus (2+ engines must agree), persistent SQLite sessions across repeated identical tasks, second opinions before a push, or PR review — and you have API keys to pay for it.

Rule of thumb from `HERMES_SWARM_NOTES.MD`: need a second opinion → `tools/swarm`; audit performance/hunt bugs → `.ruflo/`; persistent memory across repeats → `tools/swarm --persist-sessions`; same daily check on live data → `.ruflo/ --continuous`.

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

---

## 4. tools/swarm_v2 vs Ruflo swarm

`swarm_v2` (the `core/v2/` orchestrator family in this repo, mirrored by `tools/swarm_v2/` in the parent repo) and Ruflo solve different problems:

| Dimension | Ruflo swarm | swarm_v2 |
|-----------|-------------|----------|
| **Orchestrator** | `.ruflo/orchestrator.py` via Hermes Agent | `core/v2/base_orchestrator.py` + `meta_orchestrator.py` (BaseOrchestrator ABC) |
| **Architectures** | 5 fixed role-agents | coding / pr-review / research / ensemble / hierarchical (pluggable) |
| **Memory** | Ephemeral per run | Persistent `SwarmMemory` + `MessageBus` + `AgentRegistry` + `SafetyEnforcer` |
| **Transport** | Hermes internal routing → OpenRouter / direct API | OpenAI-compatible transport, provider fallbacks |
| **Free tier** | ✅ Yes (Hermes + OpenRouter free) | ⚠️ Depends on wired keys/proxy |
| **Best for** | Structured audit/strategy/bugs, continuous loops | Programmable multi-agent workflows with safety, registry, shared memory |
| **CLI entry** | `python3 .ruflo/orchestrator.py --swarm <audit|github|strategy|bugs|all|continuous>` | `python3 swarm_task.py <task> --mode coding|debate|combine|auto` |

**Verdict:** Ruflo is the better choice for ready-to-run, free-tier audit/strategy work with zero setup beyond Hermes. swarm_v2 is the better choice when you want to compose a custom multi-agent workflow (planner→executor→reviewer) with persistent shared memory, a safety enforcer, and an agent registry. They are complementary, not mutually exclusive — the parent repo runs both and cross-validates important findings with both systems.

---

## 5. Performance findings per AI_MENU items

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

---

## 6. Critical architectural finding: the LiteLLM concurrency bottleneck

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

---

## 7. How professional swarms do research (external evidence)

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

---

## 8. Quick start

```bash
# Clone
git clone https://github.com/eltonaguiar/SWARM_CONSOLIDATED.git
cd SWARM_CONSOLIDATED

# One-task swarm (combine = N-model consensus)
python3 swarm_task.py "is approach X better than Y?" --mode combine

# Unified runner with explicit architecture
python3 swarm_unified.py "fix this mermaid diagram" --architecture combine --model ULTRA_FREE_CLOUD_FAST
python3 swarm_unified.py "review this PR" --architecture pr_review --model ULTRA_FREE_NVIDIA
python3 swarm_unified.py "code a feature" --architecture coding --model ULTRA_PAID_MODE

# Guided picker
python3 cli/swarm_picker.py

# Probe a provider before trusting it in a swarm
python3 probe_providers.py
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

---

## 9. Recommendations (ordered by payoff)

1. **Kill the serialization.** Raise `--num_workers` in `tools/start_litellm_proxy.sh:435`, or have the fan-out leg call upstreams directly in parallel and use the proxy only for single-shot calls. (`SWARM_FREE_KEYS_FINDINGS_2026-11-13.md`)
2. **Adopt the 3-part admission test** as a gate in `probe_providers.py`, emitting a machine-readable pool file: `{provider, model, base_url, key_env, tool_calls, max_ctx_ok, tpm, status}`. Build the pool from evidence, never hand-written. (`SWARM_RESEARCH_PATTERNS_2026-11-13.md`)
3. **Separate "panel" keys from "report" keys.** Free keys with 8k TPM are fine as panel voters (short prompts, structured JSON) and useless as report writers (long context).
4. **Add a planner + critic stage** around `CombineTeam`: planner emits 3–6 sub-questions as JSON → `CombineTeam` answers each with a different provider → critic (different provider than any panel member) flags unsupported claims → publisher writes the report citing panel answers. (gpt-researcher / STORM shape.)
5. **Structured output or it didn't happen.** Votes must be JSON with a schema (`{claim, confidence, evidence_ref}`); otherwise consensus degenerates into comparing prose.
6. **Budget guard per run.** Track tokens and abort at a cap. (`cost_cap_usd` already exists in `core/combine_team.py`; default $0.05 free-tier ceiling.)
7. **Route log per call:** provider, resolved model, latency, tokens, estimated cost, fallback depth.
8. **Ground against local data, always.** Free proxy models have no browser and will hallucinate fetches. Pull `audit_dashboard/data/*.json` locally and embed it verbatim in prompts.

---

## 10. Related documents (in this repo)

- `SWARM_ARCHITECTURE_COMPARISON.md` — architecture patterns + recommended 3-agent parallel swarm
- `SWARM_CONCURRENCY_RESEARCH_2026-11-13.md` — LiteLLM concurrency failures, production config, token buckets, circuit breakers
- `SWARM_FREE_KEYS_FINDINGS_2026-11-13.md` — crash root cause (`--num_workers 1`) + free-key swarm recommendations
- `SWARM_MODEL_ASSESSMENT_SERVICENOW_RESEARCH_2026-11-13.md` — which models can be trusted for swarm research
- `SWARM_RESEARCH_PATTERNS_2026-11-13.md` — how successful GitHub swarms do research + live key probes
- `FREEBUFF_SWARM_2026-11-12.MD` — Freebuff swarm mission (Mercury API sunset migration)
- `OLLAMA_CLAUDE_2026-11-12.md` — Ollama/Claude peer plan
- `DEPLOY.md` — deployment notes

---

## 11. Appendix — AI_MENU → swarm mapping

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

<details>
<summary>Maintenance</summary>

- No `README.md` existed in this repo before this file; created 2026-11-14 from `SWARM_*` research docs, `HERMES_SWARM_NOTES.MD`, `RUFLO_SWARM_GUIDE.MD`, and live provider probes.
- Secrets: `~/dbpasses.txt` is gitignored and outside this repo; no secret values appear here — keys referenced by name only.
- All model/provider verdicts are from live HTTP probes run 2026-11-13 from this machine; key rot is constant, re-probe before trusting.

</details>
