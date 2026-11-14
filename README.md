# SWARM_CONSOLIDATED — Multi-Agent AI Swarm Orchestration

> **Consolidated swarm orchestrtion layer for** `findtorontoevents_antigravity.ca` **+** `FREELLM`
> Agent-level coornation: `FREBUFF_SWARM_2026-11-12.MD` (Freebuf/Bufy), `OLLAMA_CLAUDE_2026-11-12.md` (Ollam/Claude)
> **Prent repo f record:** `eltonaguiar/TORONTOEVENTS_ANTIGRAVITY` — `tools/ai_menu.sh`, `tools/swarm/`, `tools/swarm_v2/`, `.ruflo/` live there

---

## 1. What This Is

A production-hardened library of **11 swarm architectures** (V1 + V2 + Meta) that orchestrate multiple LLMs — local + free cloud + paid — through a single, consistent `http://localhost:4000/v1` LiteLLM proxy endpoint. The agents never see provider keys. The proxy owns routing, retries, coolowns, and fallbacks.

**One env var** deploys it on a new PC: `LITELLM_BASE_URL` (default `http://localhost:4000/v1`).

---

## 2. Swarm Methods — Performance & Use-Case Matrix

### 2.1 V1 Core (Lightweight, Direct)

| Method | Pattern | Cost/Latency | Best For | Status |
|---|---|---|---|---|
| **CombineTeam** | N-model parallel consensus, dedup by upstream fingerprint, first-N-unique | ~$0.0004–0.0023/task, parallel latency (max, not sum) | Quick second opinions, consensus aggregation, cost-sensitive ops | **Production** — 16/21 free groups verified live (2026-11-12) |
| **DebateTeam** | N debaters × R rounds, cross-round context, final judge/synthesizer | N×R requests (expensive), 25s deadline per combine sub-step | High-stakes decisions, complex reasoning, adversarial testing | **Production** — dead-alias default list kept fresh |
| **FileTeam** | Distributed file processing across agents | Varies by file count | Batch document analysis, multi-file review | **Stable** |
| **Ruflo** | Role-specialized agents (coder, reviewer, security-architect, tester, architect), independent model context per role | N parallel calls, no cross-contamination overhead | Specialized multi-role tasks (code + security + architecture review in one pass) | **Production** — `.ruflo/orchestrator.py` active, uses cerebras + deepseek + xai |
| **Hermes Kanban** | Planning root → parallel worker cards → verifier gate → synthesizer, state persisted in JSON kanban board | Variable (fan-out + verification pass) | Multi-channel workflows (Discord, web dashboard, CLI), distributed task tracking | **⚠ Needs Fixes** — peer review found P0 bugs (see §4) |

### 2.2 V2 Engines (Async, Message-Bus, Test-Gated)

| Method | Agents | Pipeline | Best For | Status |
|---|---|---|---|---|
| **CodingSwarm** | 3 CodeGenerators + 2 CodeReviewers + 2 TestWriters | Decompose → generate → test-write → review (max 3 revisions) → enforce | Code generation, bug fixes, feature implementation with mandatory test coverage ≥80% | **Production** — strict/non-strict modes, cost_cap_usd hard abort |
| **EnsembleSwarm** | 5 Tacticians (expandable) | Collect predictions → weighted majority (class) / weighted avg (regression) → CI check → auto-expand if low confidence | Prediction aggregation, classification, regression | **Stable** — Thompson-sampled expansion on low-confidence results |
| **ResearchSwarm** | 4 Researchers | Decompose topic → fan-out per dimension → cross-verify contradictions → synthesize with gaps | Deep research with epistemic triangulation | **Stable** — confidence ≥0.7 consensus filter |
| **PRReviewSwarm** | ImpactAnalyzer + CodeReviewer + RiskController | Parallel impact analysis + code review + risk assessment → weighted approval (0.5/0.3/0.2) | PR review gates, code quality enforcement | **Production** — configurable approval threshold |
| **GitHubActionsSwarm** | 2 ImpactAnalyzers | Fetch workflow runs → detect flaky/stale/cancelled/failed → blast-radius impact per flaky job → recommendations | CI/CD health monitoring, workflow flakiness detection | **Stable** — detects alternating pass/fail patterns, stale window configurable |
| **HierarchicalSwarm** | Strategists + Tacticians + RiskController | Strategic (macro regime) → Tactical (asset-specific) → Execution (order sizing + stop-loss) with risk veto at every layer | Investment decision flows, multi-asset portfolio analysis | **Stable** — risk-profile-aware (conservative/moderate/aggressive) |

### 2.3 Meta Layer (Self-Improving)

| Method | Function | Status |
|---|---|---|
| **MetaSwarmOrchestrator** | Reviews outputs from all 6 V2 engines, scores quality across 4 dimensions, runs A/B tests via Thompson sampling on prompt variants, identifies weak personas, exports improved skill definitions | **Stable** — JSON-persisted memory, Markdown-formatted review cycles |

---

## 3. Ruflo Swarm vs Hermes Swarm — Head-to-Head

### 3.1 Architecture

| Dimension | Ruflo | Hermes Kanban |
|---|---|---|
| **Agent model** | Role-specialized agents each with own model/persona context | Task-board with role-based workers |
| **Orchestration** | Simple parallel fan-out with concatenated output | Planning → parallel workers → verifier → synthesizer |
| **State** | No persistent cross-run state | JSON kanban board persisted across restarts |
| **Cross-platform** | CLI only | Discord + web dashboard + CLI |
| **Complexity** | Low — flat parallel roles | Medium — state machine with verifier gate |

### 3.2 Current Readiness

- **Ruflo**: Actively maintained. `.ruflo/orchestrator.py` operates on cerebras (researcher) + deepseek (coder) + xai (reviewer). Mercury migration complete. Provider rotation verified.
- **Hermes**: P0 bugs identified by peer review (§4 below). `swarm_e2e_fix.py` broken (undefined `LIVE_ALIASES`), `swarm_unified.py` wrong argument order, no true parallel execution. Windows gateway (`192.168.2.32:8642`) sometimes unreachable due to bind-address config.

### 3.3 Verdict

**Ruflo is currently the more reliable choice** for multi-role specialized work. It is simpler, has fewer moving parts, and its bugs are cosmetic rather than blocking. Hermes has a more ambitious architecture (persistent state, multi-channel, verifier gate) but the P0 bugs prevent it from executing reliably. Fix the Hermes bugs (§6) and it pulls ahead for persistent, multi-channel workflows.

---

## 4. tools/swarm_v2 vs Ruflo Swarm

### 4.1 Scope

| Dimension | `tools/swarm_v2` (V2 Engines) | Ruflo |
|---|---|---|
| **Engines** | 6 specialized orchestrators + Meta self-improver | 1 flat multi-role runner |
| **Architecture** | Async message bus, Agent Registry, persistent SwarmMemory, SafetyEnforcer | Direct `ThreadPoolExecutor` parallel calls |
| **Verification** | Test enforcement (Coding), weighted approval (PR Review), confidence CI (Ensemble), risk veto (Hierarchical) | None — outputs concatenated raw |
| **Self-improvement** | Thompson-sampled A/B testing, weak-persona detection, skill export | None |
| **State** | Memory entries persisted per engine output | No state between runs |

### 4.2 When to Use Which

| Scenario | Use |
|---|---|
| Quick multi-role review (check code quality + security + architecture) | **Ruflo** — minimal overhead, fast |
| Code generation with mandatory test coverage | **swarm_v2 CodingSwarm** — test-gated, revision loop |
| PR review with weighted, threshold-gated approval | **swarm_v2 PRReviewSwarm** |
| Deep research with contradiction detection | **swarm_v2 ResearchSwarm** |
| Investment signal hierarchy (macro → tactical → execution) | **swarm_v2 HierarchicalSwarm** |
| Ensemble prediction with confidence intervals | **swarm_v2 EnsembleSwarm** |
| CI/CD health monitoring | **swarm_v2 GitHubActionsSwarm** |
| Continuous quality optimization across all engines | **swarm_v2 MetaSwarmOrchestrator** |

### 4.3 Verdict

**`tools/swarm_v2` is architecturally superior** for complex, test-gated, and self-improving workflows. It has 6 purpose-built engines with verification gates, a Meta layer for continuous improvement, and proper async/bus architecture. Ruflo wins on simplicity — for a flat multi-role opinion, it's faster and has less overhead. Use Ruflo for quick role-specialized passes; use swarm_v2 when you need verification, state, or optimization.

---

## 5. Critical Architecture Findings

### 5.1 The LiteLLM Concurrency Bottleneck (THE Problem)
**`--num_workers 1` (line 435 in `tools/start_litellm_proxy.sh`)** serializes ALL swarm fan-out calls through a single event loop. A 10-agent fan-out becomes 10 sequential calls. The fix is **hard**: either raise `--num_workers` or route agents direct to their local endpoints (vLLM `:8000`, Ollama `:11434`) for the fan-out leg, keeping the proxy for single-shot routing.

**Industry standard (confirmed by Diagrid, OpenLegion, TrueFoundry):** route each agent to its own independent inference endpoint. vLLM and Ollama handle true concurrent batching natively.

### 5.2 Key Health: `/models` 200 ≠ Usable
~45% of keys in `~/dbpasses.txt` answer `/models` with 200 but fail at `/chat/completions`. The 3-point admission test for any key entering the swarm pool:
1. Tool-calling call with JSON schema
2. Context-capacity call (~34k tokens — Hermes system prompt + skills)
3. Balance/auth verification at chat level

### 5.3 Admission Gating
NVIDIA, SambaNova, Scaleway, Alibaba, and Z.ai free tiers: **dead** (402/403/quota). Groq: 200 on small prompts, **413 on 15k tokens** (TPM 8000 hard cap). A fallback that can't hold the prompt is worse than no fallback — it burns the one fallback activation per turn.

### 5.4 Reasoning Models and `max_tokens`
At `max_tokens < 300`, thinking models (LOCAL_CHAT, LOCAL_CODE) emit only `reasoning_content` with empty `content`. The health gate counts both — but the 25 empty answers in the ServiceNow benchmark were a budget artifact, not ignorance. Rule: `max_tokens >= 3000` for reasoning aliases.

### 5.5 Health Gate
A group is "live" only if `status=200` AND (`content` non-empty OR `reasoning_content` non-empty). At `max_tokens=4` for health probes, 11/16 live groups returned empty content — use `max_tokens >= 100` for probes.

### 5.6 Fastest Verified Providers (2026-11-12 health audit)
| Rank | Group | Latency |
|---|---|---|
| 1 | `ULTRA_FREE_NVIDIA` | 185ms |
| 2 | `ULTRA_FREE_LOCAL_MULTI` | 341ms |
| 3 | `ULTRA_FREE_TOOLS` | 351ms |
| 4 | `ULTRA_FREE_OPENROUTER` | 382ms |
| 5 | `ULTRA_FREE_CLOUD_FAST` | 430ms |

**16/21 free groups verified live.** 4 local timeouts (probably cold Ollama, not dead). 1 NVIDIA 401 (terminal in chain).

### 5.7 Verified Fallback Chain (Hermes, this machine)
```
primary  deepseek-v4-flash
  1. xai / grok-4.5                    (tool call OK, 33.5k prompt OK)
  2. deepinfra / DeepSeek-V3.2         (tool call OK, 35k prompt OK)
  3. aimlapi / gpt-4o-mini             (tool call OK, 34k prompt OK)
  4. cerebras / gpt-oss-120b           (tool call OK, 34k prompt OK)
  5. kimi-coding / kimi-k3.1-pro       (key valid, 429s often — last resort)
```

---

## 6. Known Bugs (From Hermes Peer Review 2026-11-13)

| Severity | File | Issue |
|---|---|---|
| **P0** | `swarm_e2e_fix.py` | `LIVE_ALIASES` undefined → NameError; import path mismatch for `call_with_fallback` |
| **P0** | `swarm_unified.py` | `run_combine_team(query, model)` passes model alias string as `n` parameter → TypeError |
| **P0** | `swarm_model_eval.py` | `call_model()` ignores resolved `base_url` from `resolve_best_model()`, always uses `:4000` |
| **P0** | `swarm_fix_worktree.py` | Same issues as `swarm_e2e_fix.py` |
| **MEDIUM** | All V1 paths | `swarm_parallel_runner.py` exists but is **never called** by any main workflow — all "parallel" swarms are sequential |
| **MEDIUM** | `core/combine_team.py` | Cost cap continues processing remaining aliases instead of hard abort |
| **MEDIUM** | All swarms | No red-team / verifier stage beyond mermaid syntax validation |

---

## 7. Repository Structure

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
│           ├── github_actions_swarm.py #  CI/CD health monitor
│           └── hierarchical_swarm.py   #  Strategic → Tactical → Execution
├── cli/
│   └── swarm_picker.py            # Interactive swarm launcher (planned)
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

## 8. Quick Start

```bash
# Clone and install
git clone https://github.com/eltonaguiar/SWARM_CONSOLIDATED.git
cd SWARM_CONSOLIDATED
python3 -m pip install -r requirements.txt
cp .env.example .env

# Verify the proxy is up
curl -s localhost:4000/health/readiness

# Run a consensus swarm (cheap, fast, soft consensus)
python3 swarm_unified.py "What are the top 3 trends in AI agent orchestration?" \
    --architecture combine --model ULTRA_FREE_CLOUD_FAST

# Run an adversarial debate (multi-round, rigorous)
python3 swarm_unified.py "Should we adopt LangGraph or CrewAI?" \
    --architecture debate --rounds 3 --n 4

# Run a code-generation swarm (test-gated)
python3 swarm_unified.py "Write a Python rate limiter with token bucket algorithm" \
    --architecture coding --model ULTRA_PAID_MODE

# Run PR review (weighted approval gate)
python3 swarm_unified.py "review" --architecture pr_review \
    --repo eltonaguiar/SWARM_CONSOLIDATED --pr 1

# Run Ruflo multi-role (flat parallel, fast)
python3 swarm_unified.py "Review this architecture decision" \
    --architecture ruflo --model ULTRA_FREE_CLOUD_FAST
```

---

## 9. Next Steps (Owner Decisions)

1. **P0 fixes**: Fix `swarm_e2e_fix.py` (undefined `LIVE_ALIASES`), `swarm_unified.py` (wrong arg order), `swarm_model_eval.py` (ignores resolved base_url)
2. **Wire `swarm_parallel_runner.py`** into the main workflow path — all "parallel" claims are currently false
3. **Hard cost-cap abort** in `combine_team.py` (currently continues processing after cap)
4. **Raise `--num_workers`** in LiteLLM proxy launcher from 1 → 4+, or bypass proxy for fan-out legs
5. **Adopt the 3-point admission test** (tool-call, context-capacity, chat-auth) as a gate in `probe_providers.py`
6. **Separate panel keys from report keys** — free 8k TPM keys work for voting but not for long synthesis
7. **Add planner + critic stages** around CombineTeam for proper research pipeline
8. **Route log per call**: provider, model, latency, tokens, cost, fallback depth
9. **Resolve Mercury persona**: repoint `mercury` tournament persona from Together (401s) to cerebras