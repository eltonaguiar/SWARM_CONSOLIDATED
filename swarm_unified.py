#!/usr/bin/env python3
"""
Unified Swarm Runner — supports all 6 swarm architectures.

Usage:
    python3 swarm_unified.py "fix this mermaid diagram" --architecture combine --model ULTRA_FREE_CLOUD_FAST
    python3 swarm_unified.py "review this PR" --architecture pr_review --model ULTRA_FREE_NVIDIA
    python3 swarm_unified.py "code a feature" --architecture coding --model ULTRA_PAID_MODE
    python3 swarm_unified.py "debate this approach" --architecture debate --model ULTRA_FREE_CLOUD_LARGE

Architectures:
    combine    — N-model parallel consensus (fast, cheap, good for simple tasks)
    debate     — Multi-round adversarial debate + synthesizer judge (high-stakes)
    coding     — Decompose → generate → test → review → revise → enforce (referee pattern)
    pr_review  — Impact analyzer + code reviewer + risk controller (weighted approval)
    ruflo      — Role-specialized agents (coder, reviewer, security, tester, architect)
    hermes     — Planning root → parallel workers → verifier → synthesizer

Fallback models (when credits run out):
    Primary:   ULTRA_FREE_CLOUD_FAST, ULTRA_FREE_NVIDIA, ULTRA_FREE_GEMINI
    Fallback:  ULTRA_FREE_KILO, ULTRA_FREE_LOCAL_CODE, ULTRA_FREE_LOCAL_CHAT (ollama keyless)
    Paid:      ULTRA_PAID_MODE, PAID-DEEPSEEK-PRO, PAID-DEEPSEEK-FLASH
    Decision:  SUBQ_FREE, SUBQ_TOKEN (SubQ Snap 1.2 — decision model, not code gen)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path.home() / "SWARM_CONSOLIDATED"))
from core.combine_team import (
    run_combine_team as _run_combine_team,
    fetch_live_aliases,
    COST_CAP_USD,
)  # noqa: E402
from core.debate_team import run_debate_team as _run_debate_team  # noqa: E402
from core.transport import call_openai_compat  # noqa: E402
from probe_providers import resolve_best_model  # noqa: E402

PROXY_URL = "http://localhost:4000/v1"

# Per-run routing override. When ``--direct`` is set, run_with_fallback fills
# this with a provider's own base_url/api_key so runners hit that endpoint
# directly instead of the shared :4000 proxy. Default (None) keeps the proxy.
_ROUTE: dict[str, str | None] = {"base_url": None, "api_key": None}


def _strip_chat_suffix(url: str) -> str:
    """probe_providers returns full ``.../chat/completions`` URLs, but
    core.combine_team/debate_team append ``/chat/completions`` themselves.
    Strip the suffix so direct routing does not double it."""
    suffix = "/chat/completions"
    return url[: -len(suffix)] if url.endswith(suffix) else url


def _routed_kwargs() -> dict[str, str]:
    kw: dict[str, str] = {}
    if _ROUTE.get("base_url"):
        kw["base_url"] = _strip_chat_suffix(_ROUTE["base_url"])
    if _ROUTE.get("api_key"):
        kw["api_key"] = _ROUTE["api_key"]  # type: ignore[assignment]
    return kw


def run_combine_team(query: str, n: int = 5, aliases=None, max_tokens: int = 300, **kw):
    """Wrap core CombineTeam so every call honours the active --direct route."""
    merged = {**_routed_kwargs(), **kw}
    return _run_combine_team(query, n=n, aliases=aliases, max_tokens=max_tokens, **merged)


def run_debate_team(query: str, **kw):
    """Wrap core DebateTeam so every call honours the active --direct route."""
    merged = {**_routed_kwargs(), **kw}
    return _run_debate_team(query, **merged)


def _provider_key(provider: dict[str, Any]) -> str:
    """Best-effort env key lookup for direct mode.

    ``probe_providers`` stores ``key_env`` as a human description (e.g.
    ``"OPENROUTER_API_KEY (from dbpasses.txt)"``), so extract ENV-like tokens
    and try each in the environment. Falls back to a placeholder, which is
    what keyless local endpoints (vLLM/Ollama) and the proxy expect.
    """
    key_env = str(provider.get("key_env") or "")
    for name in re.findall(r"[A-Z][A-Z0-9_]{2,}", key_env):
        val = os.environ.get(name)
        if val:
            return val
    return "anything"

# --------------------------------------------------------------------------- #
# Architecture registry
# --------------------------------------------------------------------------- #
ARCHITECTURES = {
    "combine": "N-model parallel consensus",
    "debate": "Multi-round adversarial debate + synthesizer",
    "coding": "Decompose → generate → test → review → revise → enforce",
    "pr_review": "Impact analyzer + code reviewer + risk controller",
    "ruflo": "Role-specialized agents (coder, reviewer, security, tester, architect)",
    "hermes": "Planning root → parallel workers → verifier → synthesizer",
}

# SubQ decision model (not for code gen — only for PASS/FAIL decisions)
SUBQ_API_BASE = "https://api.subq.ai/v1/system1"
os.environ.setdefault("SUBQ_FREE_API_KEY", "")
os.environ.setdefault("SUBQ_TOKEN_API_KEY", "")
SUBQ_FREE_API_KEY = os.environ.get("SUBQ_FREE_API_KEY", "")
SUBQ_TOKEN_API_KEY = os.environ.get("SUBQ_TOKEN_API_KEY", "")


def task_id_for(query: str) -> str:
    return hashlib.sha256(query.encode()).hexdigest()[:12]


# --------------------------------------------------------------------------- #
# SubQ decision model — for PASS/FAIL verdicts (not code generation)
# --------------------------------------------------------------------------- #
def subq_decide(state: str, question: str, options: list[str],
                model_alias: str = "SUBQ_FREE") -> dict:
    """Ask SubQ Snap 1.2 to pick the best option from a list."""
    api_key = SUBQ_FREE_API_KEY if model_alias == "SUBQ_FREE" else SUBQ_TOKEN_API_KEY
    if not api_key:
        return {"choice": options[0] if options else "", "confidence": 0.0,
                "error": "no SubQ API key"}

    criteria = {f"option_{i}": opt for i, opt in enumerate(options)}
    criteria["options"] = options

    payload = {
        "model": "subq-snap-1.2",
        "state": state,
        "questions": {"q1": {"instructions": question, "type": "choice",
                            "criteria": criteria}},
        "temperature": 1,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        SUBQ_API_BASE, data=data,
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        return {"choice": "", "confidence": 0.0,
                "error": f"SubQ HTTP {e.code}: {body}"}
    except Exception as e:
        return {"choice": "", "confidence": 0.0, "error": str(e)}

    answers = raw.get("answers", {})
    q1 = answers.get("q1", {})
    choice_key = q1.get("choice", "")
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
# Architecture runners
# --------------------------------------------------------------------------- #
def run_combine(query: str, model_alias: str, max_rounds: int = 3) -> dict:
    """N-model parallel consensus."""
    aliases = fetch_live_aliases()
    if model_alias not in aliases:
        # Try anyway — proxy may resolve it
        aliases = [model_alias] + [a for a in aliases if a != model_alias]

    result = run_combine_team(query, n=min(3, len(aliases)), aliases=aliases[:3],
                              max_tokens=1000)
    return {
        "architecture": "combine",
        "models_used": [r["alias"] for r in result["results"]],
        "output": "\n\n---\n\n".join(
            f"## {r['alias']}\n{r['content']}" for r in result["results"]),
        "results": result["results"],
        "cost_usd": result.get("cost_usd", 0.0),
    }


def run_debate(query: str, model_alias: str, rounds: int = 3, n: int = 4) -> dict:
    """Multi-round adversarial debate + synthesizer judge."""
    aliases = fetch_live_aliases()
    if model_alias not in aliases:
        aliases = [model_alias] + [a for a in aliases if a != model_alias]
    aliases = aliases[:n]

    dt = run_debate_team(query, rounds=rounds, n=n, aliases=aliases)

    # Build synthesis input
    synth_input = []
    for rnd in range(1, rounds + 1):
        rd = dt["round_results"].get(rnd, [])
        for j, r in enumerate(rd):
            synth_input.append(f"### Round {rnd} Debater {j+1} ({r.get('alias','?')})\n{r.get('content','')}")
    debate_text = "\n\n".join(synth_input)

    return {
        "architecture": "debate",
        "models_used": aliases,
        "output": debate_text,
        "results": dt["round_results"],
        "cost_usd": 0.0,
    }


def run_coding(query: str, model_alias: str) -> dict:
    """Coding swarm: decompose → generate → test → review → revise → enforce."""
    # Use CombineTeam as the generation engine with multiple rounds
    # (coding_swarm.py requires full v2 infrastructure; using combine_team as proxy)
    aliases = fetch_live_aliases()
    if model_alias not in aliases:
        aliases = [model_alias] + [a for a in aliases if a != model_alias]

    # Round 1: Generate
    gen = run_combine_team(query, n=3, aliases=aliases[:3], max_tokens=1000)
    gen_output = "\n\n---\n\n".join(
        f"## {r['alias']}\n{r['content']}" for r in gen["results"])

    # Round 2: Review (CombineTeam with review-focused prompt)
    review_query = (f"Review this code for correctness, bugs, and best practices. "
                    f"Task: {query}\n\nCode to review:\n{gen_output[:3000]}")
    rev = run_combine_team(review_query, n=2, aliases=aliases[:2], max_tokens=800)
    rev_output = "\n\n---\n\n".join(
        f"## {r['alias']}\n{r['content']}" for r in rev["results"])

    # Round 3: Revise based on review
    revise_query = (f"Revise the code based on these review comments. "
                    f"Task: {query}\n\nOriginal code:\n{gen_output[:2000]}\n\n"
                    f"Review comments:\n{rev_output[:2000]}\n\n"
                    f"Output the corrected code only.")
    final = run_combine_team(revise_query, n=2, aliases=aliases[:2], max_tokens=1000)
    final_output = "\n\n---\n\n".join(
        f"## {r['alias']}\n{r['content']}" for r in final["results"])

    return {
        "architecture": "coding",
        "models_used": aliases,
        "output": final_output,
        "stages": {
            "generate": gen_output,
            "review": rev_output,
            "revise": final_output,
        },
        "cost_usd": gen.get("cost_usd", 0) + rev.get("cost_usd", 0) + final.get("cost_usd", 0),
    }


def run_pr_review(query: str, model_alias: str) -> dict:
    """PR review: impact analyzer + code reviewer + risk controller."""
    aliases = fetch_live_aliases()
    if model_alias not in aliases:
        aliases = [model_alias] + [a for a in aliases if a != model_alias]

    # Impact analyzer
    impact_q = (f"Analyze the impact of this change: {query}\n"
                f"Identify affected modules, dependency graph, breaking changes, "
                f"and assign an impact score 0-100.")
    impact = run_combine_team(impact_q, n=2, aliases=aliases[:2], max_tokens=800)

    # Code reviewer
    review_q = (f"Review this code for quality, patterns, security issues. "
                f"Task: {query}\n\nCode:\n{impact['results'][0]['content'][:2000] if impact['results'] else query}")
    review = run_combine_team(review_q, n=2, aliases=aliases[:2], max_tokens=800)

    # Risk controller
    risk_q = (f"Assess risk: test coverage impact, rollback complexity. "
              f"Task: {query}\n\nReview: {review['results'][0]['content'][:1500] if review['results'] else ''}")
    risk = run_combine_team(risk_q, n=1, aliases=aliases[:1], max_tokens=600)

    output = f"IMPACT ANALYSIS:\n{impact['results'][0]['content'] if impact['results'] else ''}\n\n"
    output += f"CODE REVIEW:\n{review['results'][0]['content'] if review['results'] else ''}\n\n"
    output += f"RISK ASSESSMENT:\n{risk['results'][0]['content'] if risk['results'] else ''}\n"

    return {
        "architecture": "pr_review",
        "models_used": aliases,
        "output": output,
        "cost_usd": impact.get("cost_usd", 0) + review.get("cost_usd", 0) + risk.get("cost_usd", 0),
    }


def run_ruflo(query: str, model_alias: str) -> dict:
    """Ruflo role-specialized swarm: coder, reviewer, security-architect, tester, architect."""
    aliases = fetch_live_aliases()
    if model_alias not in aliases:
        aliases = [model_alias] + [a for a in aliases if a != model_alias]

    roles = ["coder", "reviewer", "security-architect", "tester", "architect"]
    role_outputs = {}

    for i, role in enumerate(roles[:len(aliases)]):
        alias = aliases[i % len(aliases)]
        role_q = (f"You are a {role}. Task: {query}\n"
                  f"Provide your specialized assessment and recommendations as a {role}.")
        r = run_combine_team(role_q, n=1, aliases=[alias], max_tokens=800)
        role_outputs[role] = r["results"][0]["content"] if r["results"] else ""

    output = "\n\n---\n\n".join(
        f"### {role.upper()}\n{content}" for role, content in role_outputs.items())

    return {
        "architecture": "ruflo",
        "models_used": aliases,
        "output": output,
        "roles": role_outputs,
        "cost_usd": 0.0,
    }


def run_hermes(query: str, model_alias: str) -> dict:
    """Hermes Kanban: planning root → parallel workers → verifier → synthesizer."""
    aliases = fetch_live_aliases()
    if model_alias not in aliases:
        aliases = [model_alias] + [a for a in aliases if a != model_alias]

    # Planning root
    plan_q = (f"Create a plan for this task: {query}\n"
              f"Break it into subtasks, assign owners, identify dependencies.")
    plan = run_combine_team(plan_q, n=1, aliases=[aliases[0]], max_tokens=800)
    plan_output = plan["results"][0]["content"] if plan["results"] else ""

    # Parallel workers
    worker_q = (f"Execute this plan: {plan_output[:1500]}\n"
                f"Task: {query}\nProduce your assigned work.")
    workers = run_combine_team(worker_q, n=3, aliases=aliases[:3], max_tokens=1000)
    worker_output = "\n\n---\n\n".join(
        f"## Worker {i+1} ({w['alias']})\n{w['content']}" for i, w in enumerate(workers["results"]))

    # Verifier
    verify_q = (f"Verify this work is correct and complete: {query}\n"
                f"Work produced:\n{worker_output[:2500]}\n"
                f"Report any issues or missing pieces.")
    verify = run_combine_team(verify_q, n=1, aliases=[aliases[0]], max_tokens=800)
    verify_output = verify["results"][0]["content"] if verify["results"] else ""

    # Synthesizer
    synth_q = (f"Synthesize the final answer from all work: {query}\n"
               f"Plan: {plan_output[:1000]}\n"
               f"Work: {worker_output[:2000]}\n"
               f"Verification: {verify_output[:1000]}\n"
               f"Output the final consolidated answer.")
    synth = run_combine_team(synth_q, n=1, aliases=[aliases[0]], max_tokens=1000)
    synth_output = synth["results"][0]["content"] if synth["results"] else ""

    return {
        "architecture": "hermes",
        "models_used": aliases,
        "output": synth_output,
        "stages": {
            "plan": plan_output,
            "workers": worker_output,
            "verify": verify_output,
            "synthesize": synth_output,
        },
        "cost_usd": 0.0,
    }


ARCH_RUNNERS = {
    "combine": run_combine,
    "debate": run_debate,
    "coding": run_coding,
    "pr_review": run_pr_review,
    "ruflo": run_ruflo,
    "hermes": run_hermes,
}


def run_with_fallback(arch: str, query: str, model_alias: str,
                      tier: str = "free", max_cost_usd: float = COST_CAP_USD,
                      direct: bool = False) -> dict:
    """Run a swarm architecture with model fallback chain.

    Uses probe_providers.resolve_best_model() to find the best available
    model, falling back through alternative aliases if the preferred one
    fails or the proxy is down. Tries direct endpoints (vLLM :8000,
    Ollama :11434) first for concurrent execution, then LiteLLM proxy
    (:4000), then pollinations/openrouter/ollama CLI as last resorts.

    When ``direct`` is True, each candidate model is routed to its own
    provider ``base_url`` (and env key) instead of the shared :4000 proxy —
    this is the in-repo half of the ``--direct`` path that bypasses the
    proxy/single-worker bottleneck.
    """
    last_err = "unknown"

    # Build the model list: preferred alias first, then probe results
    models_to_try = [model_alias]
    prov_map: dict[str, dict[str, Any]] = {}

    # Add all available providers from probe_providers, in priority order
    try:
        from probe_providers import probe_providers
        all_providers = probe_providers()
        for p in all_providers:
            prov_map[p["alias"]] = p
            if p["alias"] not in models_to_try:
                models_to_try.append(p["alias"])
    except Exception:
        pass

    try:
        for model in models_to_try:
            try:
                p = prov_map.get(model)
                if direct and p and p.get("base_url"):
                    _ROUTE["base_url"] = p["base_url"]
                    _ROUTE["api_key"] = _provider_key(p)
                else:
                    if direct:
                        print(f"  Direct route unavailable for {model}: not in provider map; using proxy")
                    _ROUTE["base_url"] = None
                    _ROUTE["api_key"] = None
                route = "direct" if _ROUTE["base_url"] else "proxy"
                print(f"  Trying model: {model} (architecture: {arch}, route: {route})")
                runner = ARCH_RUNNERS[arch]
                result = runner(query, model)
                result["model_used"] = model
                result["tier"] = tier
                result["route"] = route
                result["cost_usd"] = result.get("cost_usd", 0.0)
                if result["cost_usd"] > max_cost_usd:
                    print(f"  Cost cap exceeded (${result['cost_usd']:.4f} > ${max_cost_usd}), trying next model")
                    continue
                return result
            except Exception as e:
                last_err = str(e)
                print(f"  Model {model} failed: {e}")
                continue
    finally:
        _ROUTE["base_url"] = None
        _ROUTE["api_key"] = None

    return {
        "architecture": arch,
        "model_used": None,
        "tier": tier,
        "route": "direct" if direct else "proxy",
        "output": f"All models failed. Last error: {last_err}",
        "cost_usd": 0.0,
        "error": last_err,
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Unified Swarm Runner")
    ap.add_argument("query", help="Task for the swarm")
    ap.add_argument("--architecture", choices=list(ARCH_RUNNERS.keys()),
                    default="combine", help="Swarm architecture (default: combine)")
    ap.add_argument("--model", default="ULTRA_FREE_CLOUD_FAST",
                    help="Primary model alias")
    ap.add_argument("--tier", choices=["free", "paid", "decision"],
                    default="free", help="Model tier for fallback chain")
    ap.add_argument("--max-cost", type=float, default=COST_CAP_USD,
                    help="Hard cost ceiling USD")
    ap.add_argument("--direct", action="store_true",
                    help="Route each model to its own provider base_url instead "
                         "of the shared :4000 proxy (bypasses the single-worker "
                         "serialization bottleneck). Best for keyless local "
                         "endpoints (vLLM/Ollama); cloud providers still need "
                         "keys wired where the endpoint is served.")
    args = ap.parse_args()

    print(f"[swarm_unified] task: {args.query[:80]}...")
    print(f"[swarm_unified] architecture: {args.architecture}")
    print(f"[swarm_unified] model: {args.model} ({args.tier})")
    print(f"[swarm_unified] cost cap: ${args.max_cost}")
    print(f"[swarm_unified] route: {'direct' if args.direct else 'proxy'}")

    result = run_with_fallback(args.architecture, args.query, args.model,
                               args.tier, args.max_cost, direct=args.direct)

    print("\n" + "=" * 60)
    print(f"SWARM RESULT — arch={result['architecture']} "
          f"model={result.get('model_used')} cost=${result['cost_usd']:.4f}")
    print("=" * 60)
    print(result["output"][:5000])
    print("=" * 60)

    return 0 if result.get("output") and not result.get("error") else 1


if __name__ == "__main__":
    sys.exit(main())
