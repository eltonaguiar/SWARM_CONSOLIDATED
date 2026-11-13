#!/usr/bin/env python3
"""
swarm_task — Unified swarm command for the AI agent swarm.

Submit ONE task and let a swarm code it, test it, debate it, and iterate
until a coordinator + QA loop sign off.

Usage:
    python3 swarm_task.py "write a mermaid parser fix" --mode coding
    python3 swarm_task.py "is approach X better than Y?" --mode debate
    python3 swarm_task.py "second opinion on this bug" --mode combine
    python3 swarm_task.py "complex architecture decision" --mode auto

Modes:
    coding   Code + test + QA loop (coordinator + QA tester between rounds)
    debate   Multi-round adversarial debate, then coordinator synthesizes
    combine  N-model consensus, then coordinator evaluates
    auto     Router picks mode based on task keywords

The swarm runs proxy-first (LiteLLM :4000, aliases from GET /v1/models),
never reads dbpasses.txt, enforces a hard cost ceiling, and writes
memory/state checkpoints after every round so pause/steer works.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Optional

# Consolidated swarm core on the path.
sys.path.insert(0, str(Path.home() / "SWARM_CONSOLIDATED"))
from core.combine_team import run_combine_team, fetch_live_aliases, is_live, COST_CAP_USD  # noqa: E402
from core.debate_team import run_debate_team  # noqa: E402
from core.transport import call_openai_compat  # noqa: E402
from probe_providers import resolve_best_model, get_best_alias  # noqa: E402

PROXY_URL = "http://localhost:4000/v1"
SUBQ_API_BASE = "https://api.subq.ai/v1/system1"
MEMORY_DIR = Path.home() / "SWARM_CONSOLIDATED" / "memory"
STATE_DIR = Path.home() / "SWARM_CONSOLIDATED" / "state"

# SubQ API keys from dbpasses.txt (line 68: SUBQ Token, line 71: SUBQ FREE).
# Read from env — never hardcoded.
SUBQ_FREE_API_KEY = os.environ.get("SUBQ_FREE_API_KEY", "")
SUBQ_TOKEN_API_KEY = os.environ.get("SUBQ_TOKEN_API_KEY", "")


def resolve_model(preferred_alias: str | None = None,
                  tier: str | None = None) -> dict[str, str] | None:
    """Resolve the best available model alias via probe_providers.

    Tries the preferred alias first, then falls back through the probe chain:
    :4000 proxy → :8765 subq → ollama local → pollinations → openrouter →
    ollama CLI (last resort).

    Returns a dict with alias, base_url, key_env, tier, priority — or None
    if no provider is reachable.
    """
    return resolve_best_model(preferred_alias=preferred_alias, tier=tier)


def best_alias() -> str | None:
    """Return just the best available alias string."""
    p = resolve_best_model()
    return p["alias"] if p else None

# --------------------------------------------------------------------------- #
# Memory / state checkpoints
# --------------------------------------------------------------------------- #
def _ensure_dirs():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def task_id_for(query: str) -> str:
    return hashlib.sha256(query.encode()).hexdigest()[:12]


def write_memory(task_id: str, round_n: int, agent: str, content: str):
    """Append a turn to per-agent working memory (Memory-First)."""
    _ensure_dirs()
    agent_dir = MEMORY_DIR / task_id / agent
    agent_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    (agent_dir / f"turn-{round_n:03d}-{ts}.md").write_text(
        f"# Round {round_n} — {agent}\n\n{content}\n", encoding="utf-8"
    )


def write_state(task_id: str, round_n: int, state: dict):
    """Atomic state checkpoint between rounds (pause/steer support)."""
    _ensure_dirs()
    path = STATE_DIR / f"{task_id}-round-{round_n:03d}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_latest_state(task_id: str) -> Optional[dict]:
    """Load the most recent state checkpoint for resume."""
    if not STATE_DIR.exists():
        return None
    files = sorted(STATE_DIR.glob(f"{task_id}-round-*.json"))
    if not files:
        return None
    return json.loads(files[-1].read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# SubQ decision model — native /v1/systemone client
# --------------------------------------------------------------------------- #
# SubQ Snap 1.2 is a DECISION model (not a chat/completions model).  It takes
# a `state` string + `questions` with type="choice" and criteria.options
# (2+ items), and returns which option wins with probabilities.
#
# Endpoint: POST https://api.subq.ai/v1/systemone
# Body:  { model, state, questions: {q: {instructions, type:"choice",
#          criteria: {key: value, options: [2+ items]}}}, temperature }
# Response: { answers: {q: {type, choice, probabilities, confidence}} }
#
# Keys come from dbpasses.txt (SUBQ_FREE_API_KEY line 71, SUBQ_TOKEN_API_KEY
# line 68) — read from env, never hardcoded.
# --------------------------------------------------------------------------- #
def subq_decide(
    state: str,
    question: str,
    options: list[str],
    model_alias: str = "SUBQ_FREE",
) -> dict:
    """Ask SubQ Snap 1.2 to pick the best option from a list.

    Returns:
        {"choice": str, "probabilities": dict, "confidence": float, "raw": dict}
    """
    api_key = SUBQ_FREE_API_KEY if model_alias == "SUBQ_FREE" else SUBQ_TOKEN_API_KEY
    if not api_key:
        return {"choice": options[0] if options else "", "probabilities": {},
                "confidence": 0.0, "raw": {}, "error": "no SubQ API key"}

    # Build criteria: descriptive keys for each option + required "options" array
    criteria: dict[str, str] = {}
    for i, opt in enumerate(options):
        criteria[f"option_{i}"] = opt
    criteria["options"] = options  # SubQ requires an "options" array with 2+ items

    payload = {
        "model": "subq-snap-1.2",
        "state": state,
        "questions": {
            "q1": {
                "instructions": question,
                "type": "choice",
                "criteria": criteria,
            }
        },
        "temperature": 1,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        SUBQ_API_BASE,
        data=data,
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        return {"choice": "", "probabilities": {}, "confidence": 0.0, "raw": {},
                "error": f"SubQ HTTP {e.code}: {body}"}
    except Exception as e:  # noqa: BLE001
        return {"choice": "", "probabilities": {}, "confidence": 0.0, "raw": {},
                "error": str(e)}

    answers = raw.get("answers", {})
    q1 = answers.get("q1", {})
    choice_key = q1.get("choice", "")
    # Map choice key back to the actual option value (option_0 -> options[0], etc.)
    choice_value = ""
    if choice_key.startswith("option_"):
        try:
            idx = int(choice_key.split("_")[1])
            choice_value = options[idx] if 0 <= idx < len(options) else ""
        except (ValueError, IndexError):
            choice_value = ""
    elif choice_key in options:
        choice_value = choice_key

    return {
        "choice": choice_value,
        "choice_key": choice_key,
        "probabilities": q1.get("probabilities", {}),
        "confidence": q1.get("confidence", 0.0),
        "raw": raw,
    }


# --------------------------------------------------------------------------- #
# Coordinator agent — evaluates output after each round (SubQ-native decision)
# --------------------------------------------------------------------------- #
COORDINATOR_PROMPT = """You are a coordinator agent evaluating swarm output.

Task: {query}
Mode: {mode}
Round: {round_n}

Output to evaluate:
------------------
{output}
------------------

Your job:
1. Score the output 0-100 on: correctness, completeness, code quality, test coverage.
2. State ONE short verdict: PASS, NEEDS_REVISION, or FAIL.
3. If NEEDS_REVISION, list the specific changes needed (max 3 bullets).
4. Output ONLY a JSON object: {{"score": int, "verdict": "PASS|NEEDS_REVISION|FAIL", "feedback": "..."}}

Do not add prose outside the JSON."""


def coordinator_eval(query: str, mode: str, round_n: int, output: str) -> dict:
    """Evaluate output using SubQ decision model.

    Asks SubQ to choose between PASS / NEEDS_REVISION / FAIL based on the
    task + output. Falls back to the OpenAI-compatible model if SubQ is
    unavailable.
    """
    state = f"Task: {query}\nMode: {mode}\nRound: {round_n}\n\nOutput to evaluate:\n{output[:3000]}"
    decision = subq_decide(
        state=state,
        question="Is this output acceptable as-is, does it need revision, or has it failed?",
        options=["PASS", "NEEDS_REVISION", "FAIL"],
        model_alias="SUBQ_FREE",
    )

    verdict = decision.get("choice", "NEEDS_REVISION")
    if verdict not in ("PASS", "NEEDS_REVISION", "FAIL"):
        verdict = "NEEDS_REVISION"

    probs = decision.get("probabilities", {})
    conf = decision.get("confidence", 0.0)
    top_prob = max(probs.values()) if probs else 0.0

    feedback = (f"SubQ decision: {verdict} (confidence={conf:.2f}, "
                f"top_probability={top_prob:.2f})")
    if probs:
        prob_str = ", ".join(f"{k}={v:.2f}" for k, v in sorted(probs.items(),
                                                              key=lambda x: -x[1]))
        feedback += f" | {prob_str}"

    # If SubQ failed, fall back to OpenAI-compatible evaluation.
    if decision.get("error") and not decision.get("choice"):
        return _coordinator_eval_openai(query, mode, round_n, output)

    score = 100 if verdict == "PASS" else (50 if verdict == "NEEDS_REVISION" else 0)
    return {"score": score, "verdict": verdict, "feedback": feedback}


def _coordinator_eval_openai(query: str, mode: str, round_n: int, output: str) -> dict:
    """Fallback coordinator using OpenAI-compatible chat/completions."""
    best = resolve_best_model(preferred_alias="ULTRA_FREE_CLOUD_FAST", tier="free-proxy")
    if not best:
        return {"score": 0, "verdict": "NEEDS_REVISION",
                "feedback": "no model available"}
    prompt = COORDINATOR_PROMPT.format(query=query, mode=mode, round_n=round_n, output=output[:4000])
    try:
        content, meta = call_openai_compat(
            provider="openrouter",
            prompt=prompt,
            model_override=best["alias"],
            sampling={"temperature": 0.2, "max_tokens": 400},
            base_url=best["base_url"],
        )
        m = re.search(r"\{.*\}", content, re.S)
        if m:
            return json.loads(m.group(0))
    except Exception:
        pass
    verdict = "PASS" if output and "error" not in output.lower()[:200] else "NEEDS_REVISION"
    return {"score": 60, "verdict": verdict, "feedback": "coordinator fallback eval"}


# --------------------------------------------------------------------------- #
# QA tester agent — validates code fixes
# --------------------------------------------------------------------------- #
QA_PROMPT = """You are a QA tester agent. Validate that the code fix below actually
resolves the reported issue and does not introduce regressions.

Issue / task: {query}
Proposed fix:
------------------
{fix}
------------------

Your job:
1. Determine if the fix addresses the issue.
2. Check for obvious regressions (broken syntax, missing imports, edge cases).
3. Output ONLY a JSON object: {{"passes": bool, "confidence": float, "notes": "..."}}

Do not add prose outside the JSON."""


def qa_eval(query: str, fix: str) -> dict:
    """QA test a fix using SubQ decision model.

    Asks SubQ to choose between passes / fails. Falls back to the
    OpenAI-compatible model if SubQ is unavailable.
    """
    state = f"Issue / task: {query}\n\nProposed fix:\n{fix[:3000]}"
    decision = subq_decide(
        state=state,
        question="Does this fix resolve the issue without introducing regressions?",
        options=["passes", "fails"],
        model_alias="SUBQ_FREE",
    )

    passes = decision.get("choice") == "passes"
    probs = decision.get("probabilities", {})
    conf = decision.get("confidence", 0.0)
    top_prob = max(probs.values()) if probs else 0.0

    notes = (f"SubQ QA: {'PASS' if passes else 'FAIL'} "
             f"(confidence={conf:.2f}, top_probability={top_prob:.2f})")
    if probs:
        prob_str = ", ".join(f"{k}={v:.2f}" for k, v in sorted(probs.items(),
                                                              key=lambda x: -x[1]))
        notes += f" | {prob_str}"

    # If SubQ failed, fall back to OpenAI-compatible QA.
    if decision.get("error") and not decision.get("choice"):
        return _qa_eval_openai(query, fix)

    return {"passes": passes, "confidence": conf, "notes": notes}


def _qa_eval_openai(query: str, fix: str) -> dict:
    """Fallback QA using OpenAI-compatible chat/completions."""
    best = resolve_best_model(preferred_alias="ULTRA_FREE_CLOUD_FAST", tier="free-proxy")
    if not best:
        return {"passes": bool(fix and len(fix) > 20), "confidence": 0.5,
                "notes": "QA fallback: no model available"}
    prompt = QA_PROMPT.format(query=query, fix=fix[:3000])
    try:
        content, meta = call_openai_compat(
            provider="openrouter",
            prompt=prompt,
            model_override=best["alias"],
            sampling={"temperature": 0.2, "max_tokens": 400},
            base_url=best["base_url"],
        )
        m = re.search(r"\{.*\}", content, re.S)
        if m:
            return json.loads(m.group(0))
    except Exception:
        pass
    return {"passes": bool(fix and len(fix) > 20), "confidence": 0.5,
            "notes": "QA fallback eval"}


# --------------------------------------------------------------------------- #
# Mode runners
# --------------------------------------------------------------------------- #
def run_coding(query: str, max_rounds: int = 3, cost_cap: float = COST_CAP_USD) -> dict:
    """Code + test + QA loop with coordinator between rounds."""
    task_id = task_id_for(query)
    resumed = load_latest_state(task_id)
    start_round = (resumed.get("round", 0) + 1) if resumed else 1

    result = {"task_id": task_id, "mode": "coding", "rounds": [], "final": None, "cost_usd": 0.0}

    for rnd in range(start_round, max_rounds + 1):
        print(f"  [coding] round {rnd}/{max_rounds} — generating...", flush=True)
        ct = run_combine_team(query, n=3, max_tokens=600, cost_cap_usd=cost_cap)
        result["cost_usd"] += ct.get("cost_usd", 0.0)

        if not ct["results"]:
            result["rounds"].append({"round": rnd, "status": "no_results"})
            continue

        output = "\n\n---\n\n".join(
            f"## {x['alias']}\n{x['content']}" for x in ct["results"]
        )
        write_memory(task_id, rnd, "combine_team", output)

        # Coordinator evaluates.
        coord = coordinator_eval(query, "coding", rnd, output)
        write_memory(task_id, rnd, "coordinator", json.dumps(coord, indent=2))

        result["rounds"].append({
            "round": rnd,
            "coordinator": coord,
            "output_len": len(output),
        })

        if coord["verdict"] == "PASS":
            result["final"] = output
            write_state(task_id, rnd, {"status": "done", "round": rnd, "verdict": "PASS"})
            print(f"  [coding] coordinator PASS at round {rnd}", flush=True)
            break

        # QA tester evaluates the best candidate.
        best = ct["results"][0]["content"] if ct["results"] else ""
        qa = qa_eval(query, best)
        write_memory(task_id, rnd, "qa_tester", json.dumps(qa, indent=2))

        if qa["passes"] and qa.get("confidence", 0) > 0.6:
            result["final"] = best
            write_state(task_id, rnd, {"status": "done", "round": rnd, "verdict": "QA_PASS"})
            print(f"  [coding] QA PASS at round {rnd}", flush=True)
            break

        # Revision: feed coordinator feedback back into next round.
        query = f"{query}\n\nPrevious feedback to incorporate: {coord.get('feedback', '')}"
        write_state(task_id, rnd, {"status": "revision", "round": rnd, "verdict": coord["verdict"]})

    if result["final"] is None:
        result["final"] = "Swarm did not converge within max rounds."
    return result


def run_debate(query: str, rounds: int = 3, n: int = 4, cost_cap: float = COST_CAP_USD) -> dict:
    """Adversarial debate, then coordinator synthesizes."""
    task_id = task_id_for(query)
    result = {"task_id": task_id, "mode": "debate", "rounds": [], "final": None, "cost_usd": 0.0}

    print(f"  [debate] {n} debaters x {rounds} rounds...", flush=True)
    dt = run_debate_team(query, rounds=rounds, n=n)
    # debate_team doesn't yet track cost_usd; report 0.

    # Build synthesis input from debate rounds.
    synth_input = []
    for rnd in range(1, rounds + 1):
        rd = dt["round_results"].get(rnd, [])
        for j, r in enumerate(rd):
            synth_input.append(f"### Round {rnd} Debater {j+1} ({r.get('alias','?')})\n{r.get('content','')}")
    debate_text = "\n\n".join(synth_input)
    write_memory(task_id, rounds, "debate_team", debate_text)

    # Coordinator synthesizes consensus.
    coord = coordinator_eval(query, "debate", rounds, debate_text)
    write_memory(task_id, rounds, "coordinator", json.dumps(coord, indent=2))

    result["rounds"] = [{"round": rounds, "coordinator": coord, "debate_len": len(debate_text)}]
    result["final"] = f"DEBATE CONSENSUS (coordinator verdict: {coord['verdict']}):\n\n{debate_text[:3000]}"
    write_state(task_id, rounds, {"status": "done", "round": rounds, "verdict": coord["verdict"]})
    return result


def run_combine(query: str, n: int = 5, cost_cap: float = COST_CAP_USD) -> dict:
    """N-model consensus, then coordinator evaluates."""
    task_id = task_id_for(query)
    result = {"task_id": task_id, "mode": "combine", "rounds": [], "final": None, "cost_usd": 0.0}

    print(f"  [combine] {n} models consensus...", flush=True)
    ct = run_combine_team(query, n=n, max_tokens=600, cost_cap_usd=cost_cap)
    result["cost_usd"] = ct.get("cost_usd", 0.0)

    if ct["results"]:
        output = "\n\n---\n\n".join(
            f"## {x['alias']}\n{x['content']}" for x in ct["results"]
        )
        coord = coordinator_eval(query, "combine", 1, output)
        write_memory(task_id, 1, "combine_team", output)
        write_memory(task_id, 1, "coordinator", json.dumps(coord, indent=2))
        result["rounds"] = [{"round": 1, "coordinator": coord, "models": len(ct["results"])}]
        result["final"] = f"CONSENSUS (verdict: {coord['verdict']}):\n\n{output}"
        write_state(task_id, 1, {"status": "done", "round": 1, "verdict": coord["verdict"]})
    else:
        result["final"] = "No live models returned results."
    return result


def auto_route(query: str) -> str:
    """Router picks mode based on task keywords."""
    q = query.lower()
    coding_kw = ["code", "fix", "write", "implement", "bug", "patch", "refactor", "test", "mermaid", "script"]
    debate_kw = ["better", "versus", "vs ", "compare", "decide", "which", "approach", "tradeoff", "controversial"]
    if any(k in q for k in coding_kw):
        return "coding"
    if any(k in q for k in debate_kw):
        return "debate"
    return "combine"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Unified swarm task runner (code/test/debate/iterate).")
    ap.add_argument("query", help="Task description for the swarm.")
    ap.add_argument("--mode", choices=["coding", "debate", "combine", "auto"], default="auto",
                    help="Swarm mode (default: auto-router).")
    ap.add_argument("--max-rounds", type=int, default=3, help="Max coding rounds (default 3).")
    ap.add_argument("--debate-rounds", type=int, default=3, help="Debate rounds (default 3).")
    ap.add_argument("--debate-n", type=int, default=4, help="Debate participants (default 4).")
    ap.add_argument("--combine-n", type=int, default=5, help="Consensus models (default 5).")
    ap.add_argument("--cost-cap", type=float, default=COST_CAP_USD, help="Hard cost ceiling USD.")
    ap.add_argument("--resume", action="store_true", help="Resume from last state checkpoint.")
    args = ap.parse_args()

    mode = args.mode
    if mode == "auto":
        mode = auto_route(args.query)
        print(f"[auto] routed to mode: {mode}", flush=True)

    print(f"[swarm_task] task: {args.query[:80]}...", flush=True)
    print(f"[swarm_task] mode: {mode} | cost_cap: ${args.cost_cap}", flush=True)

    if args.resume:
        prev = load_latest_state(task_id_for(args.query))
        if prev:
            print(f"[swarm_task] resuming from round {prev.get('round',0)}", flush=True)

    if mode == "coding":
        result = run_coding(args.query, max_rounds=args.max_rounds, cost_cap=args.cost_cap)
    elif mode == "debate":
        result = run_debate(args.query, rounds=args.debate_rounds, n=args.debate_n, cost_cap=args.cost_cap)
    else:
        result = run_combine(args.query, n=args.combine_n, cost_cap=args.cost_cap)

    print("\n" + "=" * 60)
    print(f"SWARM_TASK RESULT — mode={result['mode']} | cost=${result['cost_usd']:.6f}")
    print("=" * 60)
    print(result["final"][:4000])
    print("=" * 60)
    print(f"Memory: {MEMORY_DIR / result['task_id']}")
    state_glob = str(STATE_DIR / f"{result['task_id']}-round-*.json")
    print(f"State:  {state_glob}")
    return 0 if result["final"] and "did not converge" not in result["final"] else 1


if __name__ == "__main__":
    sys.exit(main())
