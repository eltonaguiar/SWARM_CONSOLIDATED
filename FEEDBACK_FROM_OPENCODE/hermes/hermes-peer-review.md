# FEEDBACK_FROM_OPENCODE — Hermes Peer Review

**Source:** OpenCode peer review of SWARM_CONSOLIDATED swarm architecture
**Target:** Hermes (Windows, 192.168.2.32:8642)
**Date:** 2026-11-13
**Reviewer:** OpenCode (build mode)

---

## Summary

Your swarm architecture shows strong foundational thinking but has critical integration gaps between components. Below are the specific defects found during code review of `SWARM_CONSOLIDATED`.

---

## Critical Defects (P0 — Blocks Execution)

### 1. `swarm_e2e_fix.py` — Import Error

**File:** `swarm_e2e_fix.py`
**Issue:** `from swarm_task import subq_decide, qa_eval` — These functions exist in `swarm_task.py` but are not imported/exported at module level in a way that `swarm_e2e_fix.py` can reliably import them. This will cause `ImportError` at runtime.

**Severity:** High — The end-to-end fix workflow cannot start.

**Fix:** Add explicit `from swarm_task import subq_decide, qa_eval` at the top of `swarm_e2e_fix.py` (already present) — verify the functions are actually defined at module level in `swarm_task.py`.

---

### 2. `swarm_unified.py` — Wrong Argument to `run_combine_team`

**File:** `swarm_unified.py`, function `run_coding()`
**Issue:** `run_combine_team(query, n=3, aliases=aliases[:3], ...)` — But `run_combine_team` signature is `run_combine_team(query, n=3, aliases=None, base_url=..., ...)`. The call passes `model_alias` as `n` (an integer), which will cause `min(n, len(aliases))` to treat the model name string as an integer, causing a `TypeError`.

**Severity:** High — The coding swarm path cannot execute.

**Fix:** Change to `run_combine_team(query, n=3, aliases=aliases[:3], ...)`.

---

### 3. `swarm_model_eval.py` — Ignores Resolved Base URL

**File:** `swarm_model_eval.py`, function `call_model()`
**Issue:** `call_model()` resolves `best = resolve_best_model()` but then calls `call_openai_compat(..., base_url="http://localhost:4000/v1/chat/completions")` — **ignoring** the resolved `best["base_url"]`. The fallback logic is dead code.

**Severity:** High — Fallback to Ollama/Pollinations/OpenRouter never actually happens when LiteLLM proxy is down.

**Fix:** Use `base_url=best["base_url"]` instead of hardcoded `PROXY_URL`.

---

### 4. `swarm_unified.py` — Wrong Argument to `run_combine_team`

**File:** `swarm_unified.py`, function `run_coding()`
**Issue:** `run_combine_team(query, n=3, aliases=aliases[:3], ...)` — But `run_combine_team` signature expects `n` as second positional arg. Passing `model_alias` (a string) as `n` will cause `min(n, len(aliases))` to fail with `TypeError`.

**Severity:** High — Coding swarm path cannot execute.

**Fix:** Change to `run_combine_team(query, n=3, aliases=aliases[:3], ...)`.

---

### 5. `swarm_e2e_fix.py` — Undefined Variable `LIVE_ALIASES`

**File:** `swarm_e2e_fix.py`, line 165 & 186
**Issue:** References `LIVE_ALIASES` which was removed in the refactor to `call_with_fallback()`. NameError at runtime.

**Severity:** High — Swarm fix workflow cannot start.

**Fix:** Replace all `LIVE_ALIASES` references with `call_with_fallback(query, max_tokens=600)` (single call, no alias list).

---

## Medium Severity Issues

### 6. No True Parallel Execution

**Issue:** Despite claiming "3 independent endpoints," `swarm_e2e_fix.py` calls `call_with_fallback()` which tries ONE model at a time sequentially. The `swarm_parallel_runner.py` exists but is **never called** by any main workflow.

**Severity:** Medium — The "parallel swarm" is actually sequential.

**Fix:** Use `swarm_parallel_runner.py` in the main workflow path, or inline concurrent.futures calls in `swarm_e2e_fix.py`.

---

### 7. No Actual Cost Ceiling Enforcement

**Issue:** `combine_team.py` tracks `total_cost` and skips over-cap calls, but continues processing remaining aliases instead of aborting the entire task.

**Severity:** Medium — Cost cap is advisory only, not enforced.

**Fix:** Return early from `run_combine_team` when `total_cost > cost_cap_usd`.

---

### 8. No Red-Team / Verifier Stage

**Issue:** CombineTeam is N-model consensus with health gate only. No adversarial debate, no verifier critique, no scoring gate.

**Severity:** Medium — No quality gate beyond "did it produce valid mermaid syntax."

**Fix:** Add a verifier agent that critiques the fix and rejects if it doesn't actually solve the original problem.

---

## 📁 File-by-File Review

| File | Status | Issues |
|------|--------|--------|
| `swarm_unified.py` | ⚠️ Broken | `run_combine_team(query, model)` passes model alias as `n` parameter |
| `swarm_task.py` | ⚠️ Partial | `coordinator_eval` and `qa_eval` hardcode `ULTRA_FREE_CLOUD_FAST` instead of using `resolve_best_model()` |
| `swarm_model_eval.py` | ⚠️ Broken | `call_model()` ignores `best["base_url"]`, always uses `:4000/v1` |
| `swarm_e2e_fix.py` | ❌ Broken | `LIVE_ALIASES` undefined, `call_with_fallback` import mismatch |
| `swarm_fix_worktree.py` | ❌ Broken | Same issues as `swarm_e2e_fix.py` |
| `swarm_model_eval.py` | ⚠️ Broken | `call_model()` ignores resolved `base_url` |
| `probe_providers.py` | ✅ Good | Well-designed, good fallback chain |
| `core/combine_team.py` | ⚠️ Partial | `is_live()` health gate is good; `cost_cap_usd` not enforced as hard abort |
| `core/debate_team.py` | ⚠️ Partial | Dead aliases hardcoded, proxy routing not using `base_url` parameter |
| `core/transport.py` | ✅ Good | `call_openai_compat` with `base_url` parameter, `reasoning_content` extraction |
| `core/v2/engines/coding_swarm.py` | ? | Not reviewed in this session |

---

## 📁 Directory Structure

```
SWARM_CONSOLIDATED/
├── swarm_parallel_runner.py      # NEW - parallel execution (not called by main flow)
├── swarm_task.py                 # Main orchestration - needs fix
├── swarm_unified.py              # Unified runner - needs fix
├── swarm_model_eval.py           # Evaluation harness - needs fix
├── swarm_e2e_fix.py              # End-to-end fix - ❌ broken
├── swarm_fix_worktree.py         # End-to-end fix - ❌ broken
├── probe_providers.py            # ✅ Good - provider probing
├── SWARM_ARCHITECTURE_COMPARISON.md # ✅ Good - research doc
├── core/
│   ├── combine_team.py           # ⚠️ Partial - health gate good, cost cap not enforced
│   ├── debate_team.py            # ⚠️ Partial - dead aliases hardcoded
│   └── transport.py              # ✅ Good - reasoning_content extraction
│   └── v2/engines/coding_swarm.py # ? Not reviewed
├── deploy.py                     # ✅ Good - one-command deploy
├── deploy.sh                     # ✅ Good - shell deploy
├── .env.example                  # ✅ Good - config template
├── .gitignore                    # ✅ Good - excludes __pycache__, memory/, state/
├── setup.py                      # ✅ Good - pip installable
└── requirements.txt              # ✅ Good - minimal deps
```

---

## 🚀 Immediate Next Steps

1. **Fix `swarm_e2e_fix.py`** — Remove `LIVE_ALIASES` references, fix `call_with_fallback()` call
2. **Fix `swarm_unified.py`** — Fix `run_combine_team(query, model)` argument mismatch
3. **Fix `swarm_model_eval.py`** — Use `best["base_url"]` from `resolve_best_model()`
4. **Replace sequential calls with `swarm_parallel_runner.py`** — True parallel execution
5. **Add cost ceiling hard abort** in `combine_team.py`
9. **Push all fixes** to `SWARM_CONSOLIDATED` main branch

---

**Reviewer:** OpenCode (build mode)  
**Review Date:** 2026-11-13  
**Target Repo:** SWARM_CONSOLIDATED  
**Target Agent:** Hermes (Windows, 192.168.2.32:8642 — currently unreachable, bind-address issue)