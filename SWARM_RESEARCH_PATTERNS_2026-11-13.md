# How Professional / Successful Swarms on GitHub Do Research — and How They Run on Free Keys

**Date:** 2026-11-13
**Author:** Hermes (CLI session), for SWARM_CONSOLIDATED
**Method:** GitHub API survey of 28 swarm/research/gateway/agent repos (star counts and last-push dates pulled 2026-11-13), README + docs + code inspection on the highest-signal ones, plus **live credential probing from this machine** (this session) against every LLM key in `~/dbpasses.txt`. Every number below is either from the repo itself or from a probe I ran — nothing is inferred from vibes.

Companion docs already in this repo: `SWARM_FREE_KEYS_FINDINGS_2026-11-13.md` (crash root cause: `--num_workers 1`), `SWARM_CONCURRENCY_RESEARCH_2026-11-13.md`, `SWARM_ARCHITECTURE_COMPARISON.md`. This doc does not repeat them; it adds the **external evidence base** and the **key-admission discipline** those docs assume but do not prove.

---

## 0. TL;DR

1. Successful research swarms do not win by using a smarter model. They win by **decomposing the question, retrieving in parallel, filtering context hard, synthesizing with citations, then critiquing** — and by **measuring** the result on a public bench (Deep Research Bench / RACE, LLM-as-judge).
2. Nobody serious calls provider SDKs directly from agent code. They put a **gateway/router** in front (LiteLLM, Claude Code Router, new-api) that owns key pools, ordered fallbacks, retries, cooldowns and cost accounting.
3. Free keys are used **by role, not uniformly**: cheap/fast model for summarization and conversation simulation, strong model for the final report, diverse panel for consensus. STORM says this explicitly in its own config guidance.
4. The binding constraint on free tiers is **tokens-per-minute, not context window**. Groq free = 8,000 TPM. A Hermes-sized prompt (~15k tokens) 413s 100% of the time. A `/models` 200 response tells you nothing about whether a key can actually serve a request.
5. Our own probe found **roughly half of the LLM keys in dbpasses.txt are dead at the chat endpoint** while still answering `/models`. Any swarm that trusts `/models` will build a chain of fallbacks that all fail at the first real call — which is exactly what happened here before verification.

---

## 1. How the successful ones actually do research

### 1.1 The canonical pipeline (and who implements it)

Every credible research swarm converges on the same five stages:

```
plan → decompose into sub-questions → parallel retrieve → filter/compress → synthesize w/ citations → critique
```

| Repo | Stars | How it maps to the pipeline |
|---|---|---|
| `assafelovic/gpt-researcher` | 30,659 | Explicit **planner agent** generates research questions, **execution agents** gather in parallel, **publisher** aggregates into a cited report. Adds "JEV" (decision model) to keep only context that actually answers the question, plus recursive deep-research for breadth+depth. README states parallel research "keeps it fast, stable and reliable, and reduces misinformation." |
| `langchain-ai/open_deep_research` | 12,676 | Four **separate model slots by role**: summarization (`gpt-4.1-mini`), research (`gpt-4.1`), compression (`gpt-4.1`), final report (`gpt-4.1`). Ranked **#6 on Deep Research Bench**, RACE 0.4344. Requires models that support **structured outputs + tool calling** — stated as a hard requirement, not a nice-to-have. |
| `stanford-oval/storm` | 31,866 | Explicitly rejects naive "ask the LLM for questions." Uses **perspective-guided question asking** (mine existing articles for viewpoints) + **simulated conversation** between a writer and a grounded expert + a **moderator** agent that injects unused retrieved facts as new questions. Two-stage: pre-writing (research→outline), then writing with citations. |
| `bytedance/deer-flow` | 85,296 | Reframed from "deep research framework" to a **harness**: filesystem, memory, skills, sandbox, plus **plan-and-spawn-sub-agents**. Hit #1 GitHub Trending in Feb 2026. |
| `FoundationAgents/MetaGPT` | 71,268 | Research-as-**SOP**: roles with fixed responsibilities (PM, architect, engineer) instead of one generalist agent. Its `AFlow` paper (ICLR 2025 oral) automates the *workflow* search itself. |

**Takeaway for us:** the research quality comes from the *shape* of the pipeline (decomposition + parallelism + filtering + citation), not from model size. `CombineTeam`/`DebateTeam` in `tools/freellm.py` already implements the middle of this pipeline; what is missing is the *planner* stage (sub-question generation) and the *critic* stage (verify claims against local data).

### 1.2 Coordination topologies that survive contact with reality

| Pattern | Repo evidence | When it pays |
|---|---|---|
| **Graph / state machine** | `langchain-ai/langgraph` 44,882 ("Build resilient agents") | Deterministic, resumable research loops; checkpointing; cheapest to debug |
| **Queen-led hierarchy + consensus** | `ruvnet/ruflo` (formerly claude-flow) 81,594 — hierarchical / mesh / adaptive topologies, Queen-led with **Raft, Byzantine, Gossip** consensus, shared memory | Many workers, one decision; Byzantine consensus is the right frame when workers are *unreliable free models* |
| **Role/SOP specialization** | MetaGPT 71,268, `OpenBMB/ChatDev` 34,740 | Outputs that need a fixed artifact format (report, spec, deck) |
| **Handoff** | `openai/swarm` 22,130 — last push 2026-04-15, explicitly "educational"; superseded by `openai/openai-agents-python` 30,645 | Simple routing between specialists; do not build production on the deprecated one |
| **Barebones code-agents** | `huggingface/smolagents` 30,346, `SWE-agent` 20,790, `OpenHands` 93,366 | Tool-use-heavy work; small loop, strong tool interface (ACI) |

The honest read on consensus: **Raft/Gossip are overkill for LLM panels** — you are not replicating a state machine, you are aggregating opinions. What actually improves accuracy in practice is (a) diverse upstreams, (b) structured JSON output so votes are comparable, (c) an explicit judge/critic pass, (d) outlier rejection. `ruflo`'s "Byzantine" framing is useful as a *mental model* (assume k workers lie or fail), not as a protocol to implement.

### 1.3 Accuracy is engineered, then measured

- **Grounding beats eloquence.** gpt-researcher and STORM both refuse to let the model "remember" — every claim must attach to retrieved text, and the report carries citations.
- **Evaluation is part of the system, not an afterthought.** open_deep_research ships the Deep Research Bench harness: 100 PhD-level tasks across 22 fields, scored by **LLM-as-judge (Gemini) against expert-written golden reports**, RACE metric, published per-run cost/token table.
- **Cost is reported alongside quality.** Their GPT-5 run consumed **204,640,896 tokens** for the 100-task set; they warn a full eval run costs **$20–$100** depending on model choice. Successful projects treat tokens as a first-class budget line.
- **Role tiering shows up in configs, not blog posts.** STORM's own guidance: "choose a cheaper/faster model for `conv_simulator_lm` which is used to split queries, synthesize answers." open_deep_research defaults its summarizer to `gpt-4.1-mini` while the researcher/report roles get the bigger model.

---

## 2. How they use free AI API keys

### 2.1 The three-layer stack everyone converges on

```
agent code  →  local gateway / router  →  provider pool (keys, quotas, fallbacks)
              (LiteLLM, CCR, new-api)     (many free tiers + a few paid)
```

| Gateway | Stars | What it gives you that raw SDK calls don't |
|---|---|---|
| `BerriAI/litellm` | 63,201 | `Router` with **fallbacks**, per-deployment rpm/tpm, cooldowns, `num_retries`, virtual keys, spend tracking, load balancing. The de-facto standard for "many providers, one OpenAI-compatible endpoint." |
| `musistudio/claude-code-router` | 38,131 | Explicit feature list: "**retries, credential pools, key rotation, and ordered fallback models**", plus resolved-route logs, latency, token usage, **cost estimates, account status**. Local control plane for Claude Code / Codex / Grok CLI / Kimi CLI / Kilo / OpenCode. |
| `QuantumNous/new-api` | 51,856 | **Channels** with priorities and **weights**, retries, channel affinity, **multiple upstream keys per channel**, protocol conversion between OpenAI/Claude/Gemini. Self-hosted key aggregation. |
| `songquanpeng/one-api` | 37,420 | The older, simpler ancestor of new-api (last push 2026-01-09) — still widely deployed. |

Pattern: **the agent never knows which key served it.** Routing, rotation, retry and accounting live one layer down. That is also why their agents stay portable — swapping a dead free key is a gateway config edit, not a code change.

Counter-pattern worth naming: `xtekky/gpt4free` (67,050 stars) gets "free" access by reverse-engineering consumer endpoints. It is popular and it is **not appropriate for a production swarm** — ToS violation, unstable, and it breaks without warning. `pollinations/pollinations` (5,294) is the legitimate version of that idea (keyless gateway with published quotas).

### 2.2 Free-tier math that actually constrains design

From `mnfst/awesome-free-llm-apis` (13,016 stars, "list of permanent free LLM API") plus our own probes:

| Provider | Model | Context | Rate limit (documented) | Implication |
|---|---|---|---|---|
| Groq | `openai/gpt-oss-120b` | 131K | **30 RPM, 1,000 RPD, 8,000 TPM**, 200k TPD | 131K context is a lie in practice — TPM caps you 16× below it |
| Kilo Code | `kilo-auto/free`, various `:free` | 256K–1M | **200 req/hr** | Great for wide fan-out, useless for long single prompts |
| Google Gemini | 2.5/3.x Flash | 1M | free tier, no card (prompts may be used for training) | Best free context; treat as non-confidential |
| Cloudflare Workers AI | various | 128K | 10k neurons/day shared | Fine for aux tasks |

**The lesson:** for agent workloads, **TPM/RPD is the real currency**. A research swarm making 8 parallel calls × 20k-token prompts needs ~160k tokens — Groq's free tier delivers that over 20 minutes, i.e. one burst and you're done for the minute. Plan fan-out width against TPM, not against context size.

### 2.3 Cost-tiering by role (free-key edition)

The pattern from STORM and open_deep_research, applied to a free-key swarm:

| Role | Model class | Where to source it free |
|---|---|---|
| Query splitting, summarization, compression | small/fast (gpt-oss-20b, mistral-small, Gemini Flash-Lite) | Groq 20b, Cerebras, Kilo `:free` |
| Research / tool-calling agent | mid (gpt-oss-120b, DeepSeek V3.x, Qwen 3.8) | Cerebras, DeepInfra, AIML API |
| Panel diversity members | anything with a different training lineage | xAI Grok, Kimi, GLM, Llama on SambaNova |
| Final synthesis / judge | strongest available | xAI Grok-4.x, DeepSeek V4.x, Kimi K3.x |
| Concurrency workhorse | local vLLM / Ollama | free, unlimited, continuous batching |

### 2.4 Operational habits that separate working swarms from demos

1. **Explicit fallback chain, ordered, with a reason per entry** (CCR: "ordered fallback models"; LiteLLM: `fallbacks` + `context_window_fallbacks`).
2. **Cooldowns / circuit breakers**, not infinite retry: LiteLLM `allowed_fails` + `cooldown_time`; ruflo ships a federation circuit breaker.
3. **Per-key accounting**: rpm/tpm counters so one hot key doesn't poison the pool.
4. **Route observability**: log resolved provider/model/cost per request (CCR does this in its dashboard; new-api logs usage/audit).
5. **Probe before trust**: health-check keys on a schedule. The awesome-list projects (e.g. `mvalentsev/awesome-free-ai-coding`, "probe-verified twice a week"; `ClawLabsAI/free-ai-models`, "live status") exist *because* key rot is constant.

---

## 3. Ground truth from our own keys (probed live, 2026-11-13)

This is the part no public repo can give us. Every row below is an actual HTTP call from this machine.

### 3.1 `/models` 200 ≠ usable

| Key | `/models` | `/chat/completions` | Verdict |
|---|---|---|---|
| NVIDIA + ALT | 200, 83 models | every call times out; per-model 404 "not found for account" | **unusable** |
| SambaNova | 200, 5 models | 401 "Incorrect API key" | **unusable** |
| Groq | 200, 11 models | 200 on small prompt; **413 on 15k-token prompt (TPM 8000)** | unusable as main-agent fallback |
| Cerebras | 200 | 200 incl. 34k-token prompt + tool call | **works** |
| DeepInfra | 200 | 200, 35k prompt, tool call | **works** |
| AIML API | 200 | 200, 34k prompt, tool call | **works** ($20 paid cap) |
| xAI | 200, 13 models | 200, 33.5k prompt, tool call | **works** |
| Kimi | 200, 6 models | 429 "engine overloaded" (persistent during test) | flaky |
| Novita / Z.AI GLM / SiliconFlow | 200 | 402/429 insufficient balance | **no credits** |
| Gemini ×3 | — | 401 invalid credentials | **dead** |
| Together ×2 / Hyperbolic | — | 401 | **dead** |
| Fireworks ×2 | — | 412 account suspended | **dead** |
| Infron ×2 | 200 | 403 credits used up | **no credits** |
| Mistral ×3 | 200 | 200 but `content` is a **list of blocks** → breaks `.strip()` clients | fragile |
| AionLabs | 200 | 200 but empty `content` | pointless for agents |

### 3.2 The admission test for any key entering a swarm

Run all three; a key must pass all three or it does not join the pool:

1. **Tool-calling call** — 1 tiny prompt with a JSON tool schema, assert a `tool_calls` response.
2. **Context-capacity call** — ~34k-token prompt (Hermes system prompt + skills + memory is ~15k before any research starts). A provider that can't hold the prompt is worse than no fallback.
3. **Balance/auth at chat level** — `/models` is not evidence. Only chat is evidence.

The reusable script from this session (`findtorontoevents_antigravity.ca/updates/verify_hermes_fallback.py`) uses the same resolution path the agent uses, so it does not "pass" on a config the runtime can't actually build.

### 3.3 The chain that survived verification (Hermes, this machine)

```
primary  deepseek-v4-flash
  1. xai / grok-4.5                    (tool call OK, 33.5k prompt OK)
  2. deepinfra / DeepSeek-V3.2         (tool call OK, 35k prompt OK)
  3. aimlapi / gpt-4o-mini             (tool call OK, 34k prompt OK)
  4. cerebras / gpt-oss-120b           (tool call OK, 34k prompt OK)
  5. kimi-coding / kimi-k3.1-pro       (key valid, 429s often — last resort)
```

Verified end-to-end by pointing the primary at a dead URL: log line
`Fallback activated: deepseek-v4-flash → grok-4.5 (xai)` and the session answered normally.

Groq was **position 1** in the first draft of the chain and failed the live test with `413 ... TPM: Limit 8000, Requested 15391`. That is the single most useful fact in this document: *a fallback that cannot hold the prompt is worse than no fallback, because it burns the one fallback activation the runtime allows per turn.*

---

## 4. What we should change in SWARM_CONSOLIDATED

Ordered by payoff per unit of work.

1. **Kill the serialization.** `--num_workers 1` in `tools/start_litellm_proxy.sh:435` makes every "concurrency" claim false (already documented in `SWARM_FREE_KEYS_FINDINGS_2026-11-13.md`). Either raise workers or have the fan-out leg call upstreams directly in parallel and use the proxy only for single-shot calls.
2. **Adopt the admission test above as a gate**, not a one-off. Put it in `probe_providers.py` and make it emit a machine-readable pool file: `{provider, model, base_url, key_env, tool_calls: bool, max_ctx_ok: int, tpm: int, status}`. The pool is then generated from evidence, never hand-written.
3. **Separate "panel" keys from "report" keys.** Free keys with 8k TPM are fine as panel voters (short prompts, structured JSON) and useless as report writers (long context). Today the repo treats every key as interchangeable.
4. **Add a planner stage and a critic stage** around `CombineTeam`. Concretely: planner emits 3–6 sub-questions as JSON → `CombineTeam` answers each with a different provider → critic (a different provider than any panel member) flags unsupported claims → publisher writes the report citing the panel answers. This is the gpt-researcher/STORM shape, and it is the difference between "consensus of opinions" and "research."
5. **Structured output or it didn't happen.** Votes must be JSON with a schema (`{claim, confidence, evidence_ref}`), otherwise consensus degenerates into comparing prose. open_deep_research lists structured outputs as a *hard requirement* for exactly this reason.
6. **Budget guard per run.** Track tokens and abort at a cap (open_deep_research publishes 204.6M tokens for a 100-task eval — that's ~2M tokens per research task; our free-key runs must be given a much smaller cap and a hard abort).
7. **Route log per call**: provider, resolved model, latency, tokens, estimated cost, fallback depth. Without this you cannot tell "the swarm is dumb" from "the swarm silently ran on the 3rd-choice model all night."
8. **Ground against local data, always.** Already a rule in `.claude/skills/consult-PROXY/SKILL.md`; it is also the single biggest accuracy lever in gpt-researcher/STORM. Free proxy models have no browser and will hallucinate fetches.

---

## Appendix A — Survey sample (stars / last push, 2026-11-13)

| Repo | Stars | Last push |
|---|---|---|
| Significant-Gravitas/AutoGPT | 188,012 | 2026-11-13 |
| OpenHands/OpenHands | 93,366 | 2026-11-13 |
| bytedance/deer-flow | 85,296 | 2026-11-13 |
| ruvnet/ruflo (ex claude-flow) | 81,594 | 2026-11-13 |
| FoundationAgents/MetaGPT | 71,268 | 2026-01-21 |
| xtekky/gpt4free | 67,050 | 2026-11-11 |
| BerriAI/litellm | 63,201 | 2026-11-13 |
| microsoft/autogen | 61,800 | 2026-11-12 |
| crewAIInc/crewAI | 60,832 | 2026-11-13 |
| QuantumNous/new-api | 51,856 | 2026-11-13 |
| langchain-ai/langgraph | 44,882 | 2026-11-13 |
| musistudio/claude-code-router | 38,131 | 2026-10-10 |
| songquanpeng/one-api | 37,420 | 2026-01-09 |
| OpenBMB/ChatDev | 34,740 | 2026-11-06 |
| stanford-oval/storm | 31,866 | 2025-09-30 |
| assafelovic/gpt-researcher | 30,659 | 2026-11-12 |
| openai/openai-agents-python | 30,645 | 2026-11-13 |
| huggingface/smolagents | 30,346 | 2026-11-10 |
| mastra-ai/mastra | 29,495 | 2026-11-13 |
| google/adk-python | 22,198 | 2026-11-13 |
| openai/swarm | 22,130 | 2026-04-15 (educational, superseded) |
| SWE-agent/SWE-agent | 20,790 | 2026-11-09 |
| dzhng/deep-research | 19,894 | 2026-04-11 |
| agent0ai/agent-zero | 19,846 | 2026-11-12 |
| camel-ai/camel | 18,033 | 2026-11-09 |
| mnfst/awesome-free-llm-apis | 13,016 | — |
| langchain-ai/open_deep_research | 12,676 | 2026-08-10 |
| open-free-llm-api/awesome-freellm-apis | 5,566 | — |
| pollinations/pollinations | 5,294 | 2026-11-13 |

## Appendix B — Sources quoted

- gpt-researcher architecture (planner / execution / publisher, parallel research, JEV): repo README §"Architecture", https://github.com/assafelovic/gpt-researcher
- open_deep_research role models, Deep Research Bench #6 / RACE 0.4344, 204,640,896 tokens: repo README §Configurations + §Results, https://github.com/langchain-ai/open_deep_research
- STORM perspective-guided question asking + simulated conversation + "cheaper/faster model for conv_simulator_lm": repo README, https://github.com/stanford-oval/storm
- ruflo topologies + Raft/Byzantine/Gossip consensus: repo README table §Swarm Coordination, https://github.com/ruvnet/ruflo
- CCR "retries, credential pools, key rotation, and ordered fallback models" + resolved-route/cost dashboard: repo README §Why use Claude Code Router, https://github.com/musistudio/claude-code-router
- new-api "channel priorities and weights, retries, channel affinity, and multiple upstream keys": repo README feature table, https://github.com/QuantumNous/new-api
- Groq free tier "30 RPM, 1,000 RPD, 8,000 TPM, 200,000 TPD" and Kilo "200 req/hr": https://github.com/mnfst/awesome-free-llm-apis (Groq / Kilo Code sections)
- All key-status rows in §3: live probes from this machine, 2026-11-13 (see `findtorontoevents_antigravity.ca/updates/2026-11-13-hermes-fallback-providers.md` for full transcript and the verification script).
