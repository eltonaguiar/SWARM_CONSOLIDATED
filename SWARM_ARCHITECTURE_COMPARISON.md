# Swarm Architecture Comparison & Best Practices

> **Date:** 2026-11-13
> **Source:** Research from GitHub repos (OpenAI Swarm, Microsoft AutoGen, CrewAI, LangGraph, FREELLM domain repos)
> **Purpose:** Document industry-standard patterns for concurrent multi-agent LLM swarms, and apply them to our infrastructure.

---

## 1. Executive Summary

Testing 16 models against a broken mermaid diagram acceptance test showed **14/16 solved** with all free and paid models performing equally well (~$0.001–$0.0023 per task, ~663 chars context). The critical finding is that **LLM proxy concurrency is the bottleneck**, not model capability. LiteLLM with `--num_workers 1` serializes all calls through a single event loop. Industry-standard swarm architectures route each agent to its **own independent inference endpoint** for true parallelism.

---

## 2. Swarm Architecture Patterns

### 2.1 CombineTeam (N-Model Parallel Consensus)
**Pattern:** Ask N AIs the same question simultaneously, deduplicate by upstream model fingerprint, return first N unique results.

**Best for:** Quick second opinions, simple tasks, cost-sensitive operations.

**Pattern characteristics:**
- Parallel fan-out to N aliases/models
- Deduplicate by upstream model fingerprint
- Health gate counts `content` AND `reasoning_content` (thinking models emit empty content)
- First N unique results win

**Cost:** ~$0.0004–$0.0023 per task  
**Latency:** Parallel (max of individual calls, not sum)

---

### 2.2 DebateTeam (Adversarial Multi-Round Debate)
**Pattern:** N debaters debate over R rounds, each seeing previous round's responses, then a judge/synthesizer declares consensus.

**Best for:** High-stakes decisions, complex reasoning, controversial topics.

**Pattern characteristics:**
- N debaters × R rounds
- Cross-round context (each debater sees previous round)
- Final round: debate synthesis/summary
- Debate multiplies requests by N×R

**Warning:** Debate multiplies requests (N×R). One dead upstream = N dead requests. Only enable when proxy is healthy.

---

### 2.3 CodingSwarm (Planner → Executor → Reviewer → Verifier)
**Pattern:** Triangle orchestration with mandatory test enforcement.

**Pattern characteristics:**
1. Planner decomposes task into sub-tasks
2. Code generators fan-out in parallel
3. Test writers enrich with tests
4. Code reviewers review (max 3 revisions)
5. Test enforcement — abort if tests fail (strict mode) or return best-effort

**Best for:** Code generation, bug fixes, feature implementation.

**Cost ceiling:** Hard `cost_cap_usd` aborts if exceeded.

---

### 2.4 PRReviewSwarm (Impact Analyzer + Code Reviewer + Risk Controller)
**Pattern:** Three specialized agents with weighted approval threshold.

**Pattern characteristics:**
- Impact analyzer (weight 0.5)
- Code reviewer (weight 0.3)
- Risk controller (weight 0.2)
- All must approve AND impact score ≥ threshold

**Best for:** PR review, code quality gates.

---

### 2.5 Ruflo (Role-Specialized Agents)
**Pattern:** Role-specific agents (coder, reviewer, security-architect, tester, architect) each producing independent output.

**Pattern characteristics:**
- Each role gets its own model context
- Outputs concatenated, no cross-contamination
- Good for specialized tasks needing different personas

---

### 2.6 Hermes Kanban (Planning Board → Workers → Verifier → Synthesizer)
**Pattern:** Task board with role-based workers and verification gate.

**Pattern characteristics:**
- Planning root task → parallel worker cards → verifier gate → synthesizer
- State persisted in JSON comments on kanban board
- Works across Discord, web dashboard, CLI

---

## 3. Key Architectural Patterns

### 3.1 Proxy-First Pattern
**Rule:** No swarm reads `~/dbpasses.txt` directly. The launcher owns key loading; the proxy holds keys. The swarm library needs NO secrets — just `base_url + alias + placeholder key`.

**One env var** is enough for a new PC: `LITELLM_BASE_URL` (default `http://localhost:4000/v1`).

### 3.2 Health Gate Pattern
**Rule:** A group is "live" if status=200 AND (`content` non-empty OR `reasoning_content` non-empty). Thinking models (LOCAL_CHAT, LOCAL_CODE) return empty `content` at low `max_tokens` but populate `reasoning_content`. Gate on both.

**Rule:** Request `max_tokens >= 300` for reasoning models so they emit content, not just reasoning.

### 3.4 Runtime Alias Resolution
**Rule:** Resolve aliases from `GET /v1/models` at runtime — never hardcode alias lists. 36 aliases today, 34 an hour ago — they move.

### 3.5 Memory-Pattern
**Rule:** Agents write local `.md` "working memory" after every turn. State-board JSON/MD task board instead of single-thread orchestrator. Model-splicing: small-smart models for memory management → large-heavy models for "Hard Truth" fixes.

### 3.6 Cost Ceiling Pattern
**Rule:** Hard `cost_cap_usd` on SwarmTask. Abort + nonzero exit code at cap. Free-tier defaults ($0.00–$0.05).

---

## 4. Critical Finding: LiteLLM Concurrency Bottleneck

**LiteLLM with `--num_workers 1` runs a single process.** Even with multiple uvicorn workers, LiteLLM's router processes requests through a single event loop and makes **blocking calls to upstream providers**. All requests come through the same process, serially.

### Industry Standard Solution

**Do NOT route all swarm agents through a single LiteLLM proxy.** Instead, route each agent to its **own independent inference endpoint**:

| Agent | Endpoint | Model | Type |
|-------|----------|-------|------|
| Agent 1 | `http://localhost:8000/v1` | qwen3-8b | Local GPU (vLLM) |
| Agent 2 | `http://localhost:11434/v1` | qwen2.5-coder:7b | Local GPU (Ollama) |
| Agent 3 | `http://localhost:11434/v1` | qwen3:30b-a3b | Local GPU (Ollama) |

**All three are already running.** All three handle concurrent requests natively. No shared queue, no single event loop, no bottleneck. If one model goes down, the others keep running.

**Why this beats scaling LiteLLM:**
- vLLM/Ollama are the actual inference engines — built for concurrency
- LiteLLM adds routing/failover on top, but with `--num_workers 1` it becomes a serial bottleneck
- For a swarm, you want independent agents, not a centralized queue
- If one model goes down, the others keep running — no single point of failure

**For cloud models:** Each agent calls its cloud provider directly (OpenRouter, Gemini, etc.) — no shared proxy needed.

---

## 5. Multi-Agent Swarm Frameworks Survey

| Framework | Stars | Language | Key Pattern | Notes |
|-----------|-------|----------|-------------|-------|
| OpenAI Swarm | 22,129 | Python | Agent + handoffs | Educational, now superseded by OpenAI Agents SDK |
| LangGraph | ~17k | Python | Graph-based state machines | Production-ready, persistent state |
| AutoGen | ~30k | Python | Conversational agents | Microsoft, mature |
| CrewAI | ~29k | Python | Role-based agents | Popular, simple |
| MetaGPT | ~28k | Python | Software engineering workflow | Software-focused |
| SWARM_CONSOLIDATED | — | Python | Combine/Debate/Coding/PRReview/Ruflo/Hermes | **Our repo** |

---

## 6. Recommended Architecture for Our Use Case

### Recommended: 3-Agent Parallel Swarm

| Agent | Endpoint | Model | Type | Role |
|-------|----------|-------|------|------|
| Agent 1 | `http://localhost:8000/v1` | qwen3-8b | Local GPU (vLLM) | Fast general reasoning |
| Agent 2 | `http://localhost:11434/v1` | qwen2.5-coder:7b | Local GPU (Ollama) | Code/technical tasks |
| Agent 3 | `http://localhost:11434/v1` | qwen3:30b-a3b | Local GPU (Ollama) | Deep reasoning |

**All three can run simultaneously.** Each has its own GPU process. No shared queue. No LiteLLM in the path.

If Windows Hermes comes back online (`192.168.2.32:8642`), add a 4th agent.

### Fallback Model Chain (when credits run out)

```
Primary free:   ULTRA_FREE_CLOUD_FAST → ULTRA_FREE_NVIDIA → ULTRA_FREE_GEMINI
Fallback free:  ULTRA_FREE_KILO → ULTRA_FREE_LOCAL_CODE → ULTRA_FREE_LOCAL_CHAT (ollama keyless)
Paid:           ULTRA_PAID_MODE → PAID-DEEPSEEK-PRO → PAID-DEEPSEEK-FLASH
Decision only:  SUBQ_FREE → SUBQ_TOKEN (SubQ Snap 1.2 — decision model only)
```

---

## 7. Implementation Pattern

```python
# Each agent calls its own endpoint directly
AGENT_ENDPOINTS = [
    {"name": "vllm-qwen3-8b", "url": "http://localhost:8000/v1/chat/completions", "model": "qwen3-8b"},
    {"name": "ollama-qwen2.5-coder-7b", "url": "http://localhost:11434/v1/chat/completions", "model": "qwen2.5-coder:7b"},
    {"name": "ollama-qwen3-30b-a3b", "url": "http://localhost:11434/v1/chat/completions", "model": "qwen3:30b-a3b"},
]

# Parallel execution
with cf.ThreadPoolExecutor(max_workers=len(AGENT_ENDPOINTS)) as ex:
    futures = {ex.submit(call_model, a, prompt): a["name"] for a in AGENT_ENDPOINTS}
    for fut in cf.as_completed(futures):
        result = fut.result()
```

---

## 8. References

- [OpenAI Swarm](https://github.com/openai/swarm) — Educational framework, Agent + handoffs pattern
- [Microsoft AutoGen](https://github.com/microsoft/autogen) — Conversational agents
- [CrewAI](https://github.com/crewAIInc/crewAI) — Role-based agents
- [LangGraph](https://github.com/langchain-ai/langgraph) — Graph-based state machines
- [MetaGPT](https://github.com/geffan/metagpt) — Software engineering workflow
- [SWARM_CONSOLIDATED](https://github.com/eltonaguiar/SWARM_CONSOLIDATED) — Our repo: Combine/Debate/Coding/PRReview/Ruflo/Hermes
