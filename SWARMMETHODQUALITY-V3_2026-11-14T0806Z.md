# Swarm Method Quality Audit — swarmmethodquality-v3

**Date:** 2026-11-14T08:06Z  
**Worktree:** `swarmmethodquality-v3`  
**Repo analyzed:** `eltonaguiar/SWARM_CONSOLIDATED`  
**Scope:** Performance comparison of all swarm methods per AI_MENU items, README collision audit, content recovery

---

## 1. Swarm Methods Evaluated

### V1 Core (5 methods)

| Method | Pattern | Status |
|---|---|---|
| **CombineTeam** | N-model parallel consensus, dedup by upstream fingerprint | Production — 16/21 free groups verified live |
| **DebateTeam** | N debaters × R rounds, cross-round context, final judge | Production — dead-alias list fresh |
| **FileTeam** | Distributed file processing across agents | Stable |
| **Ruflo** | 5 role-specialized agents (coder, reviewer, security-architect, tester, architect) | Production — cerebras + deepseek + xai active |
| **Hermes Kanban** | Planning root → parallel workers → verifier → synthesizer, JSON kanban state | ⚠ P0 bugs |

### V2 Engines (6 methods)

| Engine | Agents | Pipeline | Status |
|---|---|---|---|
| **CodingSwarm** | 3 generators + 2 reviewers + 2 test writers | Decompose → Fan-out → Review (≤3) → Test gate | Production |
| **PRReviewSwarm** | Impact analyzer + code reviewer + risk controller | Parallel 3-agent → Weighted approval (0.5/0.3/0.2) | Production |
| **GitHubActionsSwarm** | 2 impact analyzers | Fetch runs → Pattern detect → Blast radius → Recs | Stable |
| **ResearchSwarm** | 4 researchers | Decompose → Fan-out → Cross-verify → Synthesize | Stable |
| **EnsembleSwarm** | 5 tacticians (expandable) | Fan-out → Weighted majority/avg → CI → Expand if low | Stable |
| **HierarchicalSwarm** | 2 strategists + 3 tacticians + risk controller | Strategic → Tactical → Execution + risk veto | Stable |

### Meta Layer (1 method)

| Method | Function | Status |
|---|---|---|
| **MetaSwarmOrchestrator** | Reviews all 6 V2 engine outputs, A/B tests via Thompson sampling, identifies weak personas | Stable |

**Total: 12 swarm architectures across 3 layers.**

---

## 2. Key Performance Findings

### Is Ruflo Swarm better than Hermes Swarm?

**Finding:** Ruflo Swarm IS the Hermes-driven swarm. `.ruflo/orchestrator.py` dispatches through Hermes Agent. There is no separate "Hermes Swarm." The real comparison is Ruflo (5 fixed-role agents, free tier via OpenRouter, 3-attempt failover) vs Hermes ad-hoc (dynamic agents via Windows gateway, paid keys only).

**Verdict:** Ruflo is better for multi-agent research/audit workflows (agent specialization, structured output, free tier). Hermes wins only for low-latency paid single tasks when the gateway is properly configured.

### What about tools/swarm_v2 vs Ruflo?

**Finding:** swarm_v2 has 6 specialized engines with true parallelism (asyncio), persistent ChromaDB memory, 300+ tests, and hard cost ceilings. Ruflo has 5 agent roles but runs sequentially through Hermes CLI with zero automated tests.

**Verdict:** swarm_v2 is architecturally superior for production engineering workflows. Ruflo wins only for zero-setup free-tier audit/strategy work.

### #1 Performance Problem

LiteLLM `--num_workers 1` serializes all swarm fan-out calls through a single event loop. A 10-agent fan-out becomes 10 sequential calls. **This is the bottleneck, not model capability.** Fix: route each agent to its own independent inference endpoint (vLLM `:8000`, Ollama `:11434`) for the fan-out leg.

### Provider Health (2026-11-12/13 probes)

- **16/21 free groups verified live** (fastest: NVIDIA 185ms, LOCAL_MULTI 341ms)
- **~50% of dbpasses.txt keys dead at chat level** despite `/models` returning 200
- **Dead providers:** NVIDIA (except Nemotron 3.5), SambaNova, Scaleway, Alibaba, Z.ai, Gemini ×3, Together ×2, Fireworks ×2, Infron ×2
- **Verified fallback chain:** deepseek-v4-flash → xai/grok-4.5 → deepinfra/DeepSeek-V3.2 → aimlapi/gpt-4o-mini → cerebras/gpt-oss-120b → kimi/kimi-k3.1-pro (last resort, 429s)

### Research Accuracy

- **0/38 models named all 4 ServiceNow terms** memory-only
- **Research ceiling: 3/4 terms** even with retrieval
- Retrieval + synthesis recovers 6pp over memory-only
- `max_tokens >= 3000` required for reasoning aliases (25/38 had empty content at 900 tokens)

---

## 3. README Collision Audit

### Timeline

| Commit | Agent | Action |
|---|---|---|
| `097d10f` | Agent 1 | Created first README — file inventory, "two swarm systems" comparison, AI_MENU mapping |
| `15e087c` | Kilo (this session) | Added V1/V2 engine details, Known Bugs table, Architecture Findings, Repo Structure, Next Steps |
| `aaaf234` | Agent 2 | Rewrote Ruflo vs Hermes section, added Performance Snapshot, tools/swarm_v2 comparison |
| `bdc457b` | Agent 3 | Merged all 3 versions, added TOC, TL;DR table, Appendix, Maintenance log |

### Collision: Commits `097d10f` and `15e087c`

Two agents independently created the file. Git rebase conflict was resolved by taking the second agent's version (more comprehensive with 9 major sections vs 11). Content from the first agent's "Two Swarm Systems That Actually Run" and parent repo perspective was temporarily lost.

### Recovery: Commit `aaaf234` and `bdc457b`

Subsequent agents restored the lost material. The final README (`bdc457b`, 578 lines, 21 sections) contains content from all 3 original versions plus merged improvements.

### Content Preservation Verification

| Original content from | Preserved in final? |
|---|---|
| File inventory table (`097d10f`) | ✅ "What This Repo Contains" |
| Two swarm systems comparison (`097d10f`) | ✅ "The Two Swarm Systems That Actually Run" |
| AI_MENU mapping (`097d10f`) | ✅ "Appendix — AI_MENU → Swarm Mapping" |
| V1/V2 engine details (`15e087c`) | ✅ "The Six Swarm Architectures" + expanded V2 section |
| Known Bugs P0 table (`15e087c`) | ✅ "Known Bugs & Limitations" |
| Architecture Findings (`15e087c`) | ✅ "Critical Architectural Finding" + "Performance Findings" |
| Repository Structure (`15e087c`) | ✅ Present |
| Next Steps (`15e087c`) | ✅ "Recommendations (ordered by payoff)" |
| Performance Snapshot (`aaaf234`) | ✅ Present |
| TL;DR table (`bdc457b`) | ✅ Present |

**Result: Zero content loss.** All material from all 3 agents is present in the final README.

---

## 4. AI_MENU → Swarm Performance Summary

| AI_MENU Item | Best Swarm | Key Metric |
|---|---|---|
| Quick Second Opinion | CombineTeam | 16/21 free groups live, ~$0.001/run |
| Complex Coding | CodingSwarm | 14/16 models solved mermaid test, 3 code-gen + 2 review + 2 test agents |
| Adversarial Testing | DebateTeam | N×R cost; verify proxy health before enabling |
| Deep Research | ResearchSwarm | 3/4 accuracy ceiling; +6pp with retrieval |
| Free-Only | CombineTeam (free) | ~50% keys dead; must probe before trust |
| PR Review | PRReviewSwarm | Triple-specialist weight (0.5/0.3/0.2) |
| CI Health | GitHubActionsSwarm | Auto-detects flaky, stale, cancelled jobs |
| Trading Decisions | HierarchicalSwarm | 3-layer risk-veto pipeline |
| Prediction | EnsembleSwarm | Weighted aggregation + CI + auto-expand |
| Self-Improvement | MetaSwarmOrchestrator | Thompson-sampled A/B testing |

---

## 5. P0 Bugs Requiring Immediate Attention

| File | Issue |
|---|---|
| `swarm_e2e_fix.py` | `LIVE_ALIASES` undefined → NameError; import mismatch |
| `swarm_unified.py` | `run_combine_team(query, model)` wrong arg order → TypeError |
| `swarm_model_eval.py` | `call_model()` ignores resolved `base_url`, always uses `:4000` |
| `swarm_fix_worktree.py` | Same issues as `swarm_e2e_fix.py` |
| All V1 paths | `swarm_parallel_runner.py` never called by main workflow |
| `core/combine_team.py` | Cost cap continues processing instead of hard abort |

---

## 6. Recommendations (Ordered by Payoff)

1. Fix P0 bugs in `swarm_e2e_fix.py`, `swarm_unified.py`, `swarm_model_eval.py`
2. Wire `swarm_parallel_runner.py` into main workflow — all "parallel" claims are currently false
3. Raise `--num_workers` from 1 → 4+ or bypass proxy for fan-out legs
4. Adopt 3-point admission test as permanent gate: tool-calls + 34k context + chat auth
5. Separate panel keys from report keys (free 8k TPM works for voting, not long synthesis)
6. Add planner + critic stages around CombineTeam for proper research pipeline
7. Hard cost-cap abort in `combine_team.py`
8. Add tests for Ruflo — parity with swarm_v2's 300+ test suite
9. Route log per call: provider, model, latency, tokens, cost, fallback depth
10. Resolve Mercury persona: repoint from Together (401s) to cerebras

---

## Verification

- All model/provider verdicts from live HTTP probes (2026-11-12/13)
- 16/21 free groups verified via health gate (`is_live()` checks content + reasoning_content)
- Verified fallback chain tested end-to-end: primary dead → xai fallback activated → session answered normally
- README collision audit verified via `git log --oneline -- README.md` and `git diff` across all 4 commits
- No secret values in this document; keys referenced by name only