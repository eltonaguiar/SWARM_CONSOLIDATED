#!/usr/bin/env python3
"""
Swarm Model Server — exposes swarm architectures as OpenAI-compatible models
behind the LiteLLM proxy on :4000.

Each swarm architecture is registered as a distinct "model" alias:
  - model: swarm-combine   → CombineTeam (N-model parallel consensus)
  - model: swarm-debate    → DebateTeam (adversarial debate + synthesizer)
  - model: swarm-coding    → CodingSwarm (decompose → generate → test → review → revise)
  - model: swarm-pr_review → PRReviewSwarm (impact + code review + risk)
  - model: swarm-ruflo     → Ruflo (role-specialized agents)
  - model: swarm-hermes    → Hermes Kanban (plan → workers → verifier → synthesizer)

Register in litellm_config.yaml:
  - model_name: swarm-combine
    litellm_params:
      model: swarm-combine
      api_base: http://127.0.0.1:8766/v1
      api_key: os.environ/SWARM_MODEL_API_KEY
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path.home() / "SWARM_CONSOLIDATED"))
from core.combine_team import run_combine_team  # noqa: E402
from core.debate_team import run_debate_team  # noqa: E402
from core.transport import call_openai_compat  # noqa: E402

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="Swarm Model Server", version="1.0.0")

PROXY_URL = "http://localhost:4000/v1"

# Map swarm model aliases to architecture runners
SWARM_ARCHITECTURES = {
    "swarm-combine": "combine",
    "swarm-debate": "debate",
    "swarm-coding": "coding",
    "swarm-pr_review": "pr_review",
    "swarm-ruflo": "ruflo",
    "swarm-hermes": "hermes",
}

VALID_MODELS = set(SWARM_ARCHITECTURES.keys())


def extract_text_from_messages(messages: list[dict]) -> str:
    """Flatten OpenAI messages into a single prompt string."""
    parts = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        parts.append(f"{role.upper()}: {content}")
    return "\n\n".join(parts)


def extract_model_from_messages(messages: list[dict]) -> str | None:
    """If the user message contains a model hint, extract it."""
    for m in messages:
        content = m.get("content", "") or ""
        for model_alias in VALID_MODELS:
            if model_alias in content.lower():
                return model_alias
    return None


def run_swarm(architecture: str, query: str, model_hint: str | None = None) -> str:
    """Run a swarm architecture and return the text output."""
    aliases = ["ULTRA_FREE_CLOUD_FAST", "ULTRA_FREE_NVIDIA", "ULTRA_FREE_GEMINI",
               "ULTRA_FREE_KILO", "ULTRA_FREE_LOCAL_CODE"]

    if architecture == "combine":
        result = run_combine_team(query, n=3, aliases=aliases, max_tokens=1000)
        return "\n\n---\n\n".join(
            f"## {r['alias']}\n{r['content']}" for r in result["results"]
        )

    elif architecture == "debate":
        from core.debate_team import run_debate_team
        dt = run_debate_team(query, rounds=2, n=3, aliases=aliases[:3])
        synth = []
        for rnd in range(1, 3):
            rd = dt["round_results"].get(rnd, [])
            for j, r in enumerate(rd):
                synth.append(f"### Round {rnd} Debater {j+1} ({r.get('alias','?')})\n{r.get('content','')}")
        return "\n\n".join(synth)

    elif architecture == "coding":
        aliases2 = ["ULTRA_FREE_CLOUD_FAST", "ULTRA_FREE_NVIDIA", "ULTRA_FREE_GEMINI"]
        gen = run_combine_team(query, n=3, aliases=aliases2[:3], max_tokens=1000)
        gen_out = "\n\n---\n\n".join(
            f"## {r['alias']}\n{r['content']}" for r in gen["results"]
        )
        rev_q = (f"Review this code for correctness and bugs. Task: {query}\n\n{gen_out[:2500]}")
        rev = run_combine_team(rev_q, n=2, aliases=aliases2[:2], max_tokens=800)
        rev_out = "\n\n---\n\n".join(
            f"## {r['alias']}\n{r['content']}" for r in rev["results"]
        )
        revise_q = (f"Revise based on review. Task: {query}\n\nCode:\n{gen_out[:1500]}\n\n"
                    f"Review:\n{rev_out[:1500]}\n\nOutput corrected code only.")
        final = run_combine_team(revise_q, n=2, aliases=aliases2[:2], max_tokens=1000)
        final_out = "\n\n---\n\n".join(
            f"## {r['alias']}\n{r['content']}" for r in final["results"]
        )
        return f"GENERATION:\n{gen_out}\n\nREVIEW:\n{rev_out}\n\nREVISED:\n{final_out}"

    elif architecture == "pr_review":
        impact_q = (f"Analyze impact of this change: {query}\n"
                    f"Affected modules, breaking changes, impact score 0-100.")
        impact = run_combine_team(impact_q, n=2, aliases=aliases[:2], max_tokens=800)
        impact_out = "\n\n---\n\n".join(
            f"## {r['alias']}\n{r['content']}" for r in impact["results"]
        )
        review_q = (f"Review code quality, patterns, security. Task: {query}\n"
                    f"Impact:\n{impact_out[:2000]}")
        review = run_combine_team(review_q, n=2, aliases=aliases[:2], max_tokens=800)
        review_out = "\n\n---\n\n".join(
            f"## {r['alias']}\n{r['content']}" for r in review["results"]
        )
        risk_q = (f"Assess risk: test coverage, rollback complexity. Task: {query}\n"
                  f"Review:\n{review_out[:1500]}")
        risk = run_combine_team(risk_q, n=1, aliases=[aliases[0]], max_tokens=600)
        risk_out = "\n\n---\n\n".join(
            f"## {r['alias']}\n{r['content']}" for r in risk["results"]
        )
        return f"IMPACT:\n{impact_out}\n\nREVIEW:\n{review_out}\n\nRISK:\n{risk_out}"

    elif architecture == "ruflo":
        roles = ["coder", "reviewer", "security-architect", "tester", "architect"]
        role_outs = {}
        for i, role in enumerate(roles[:len(aliases)]):
            alias = aliases[i % len(aliases)]
            r = run_combine_team(
                f"You are a {role}. Task: {query}\nProvide your assessment.",
                n=1, aliases=[alias], max_tokens=800
            )
            role_outs[role] = r["results"][0]["content"] if r["results"] else ""
        return "\n\n---\n\n".join(
            f"### {role.upper()}\n{c}" for role, c in role_outs.items()
        )

    elif architecture == "hermes":
        plan_q = (f"Create a plan for: {query}\nBreak into subtasks.")
        plan = run_combine_team(plan_q, n=1, aliases=[aliases[0]], max_tokens=800)
        plan_out = plan["results"][0]["content"] if plan["results"] else ""
        worker_q = (f"Execute: {plan_out[:1500]}\nTask: {query}\nProduce your work.")
        workers = run_combine_team(worker_q, n=3, aliases=aliases[:3], max_tokens=1000)
        worker_out = "\n\n---\n\n".join(
            f"## Worker {i+1} ({w['alias']})\n{w['content']}" for i, w in enumerate(workers["results"])
        )
        verify_q = (f"Verify: {query}\nWork:\n{worker_out[:2500]}\nReport issues.")
        verify = run_combine_team(verify_q, n=1, aliases=[aliases[0]], max_tokens=800)
        verify_out = verify["results"][0]["content"] if verify["results"] else ""
        synth_q = (f"Synthesize: {query}\nPlan: {plan_out[:1000]}\n"
                   f"Work: {worker_out[:2000]}\nVerify: {verify_out[:1000]}\n"
                   f"Final answer:")
        synth = run_combine_team(synth_q, n=1, aliases=[aliases[0]], max_tokens=1000)
        return synth["results"][0]["content"] if synth["results"] else ""

    else:
        raise ValueError(f"Unknown architecture: {architecture}")


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": model_alias,
                "object": "model",
                "owned_by": "swarm_consolidated",
                "architecture": arch,
            }
            for model_alias, arch in SWARM_ARCHITECTURES.items()
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: dict):
    model = request.get("model", "")
    if model not in VALID_MODELS:
        raise HTTPException(status_code=400, detail=f"Unknown model: {model}. Valid: {sorted(VALID_MODELS)}")

    messages = request.get("messages", [])
    query = extract_text_from_messages(messages)
    model_hint = extract_model_from_messages(messages)

    architecture = SWARM_ARCHITECTURES[model]
    try:
        output = run_swarm(architecture, query, model_hint)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": output},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": len(query.split()),
            "completion_tokens": len(output.split()),
            "total_tokens": len(query.split()) + len(output.split()),
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Swarm Model Server")
    ap.add_argument("--port", type=int, default=8766, help="Port to listen on")
    ap.add_argument("--host", default="127.0.0.1", help="Host to bind")
    args = ap.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
