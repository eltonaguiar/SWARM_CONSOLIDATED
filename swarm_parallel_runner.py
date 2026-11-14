#!/usr/bin/env python3
"""
Parallel Swarm Runner — Multi-Endpoint Architecture

Each agent hits its own independent inference endpoint, so N agents run
truly in parallel with no shared proxy queue (the :4000 LiteLLM proxy with
``--num_workers 1`` serializes every request — see
SWARM_CONCURRENCY_RESEARCH_2026-11-13.md).

Default endpoints (all local, accept a placeholder key):
  - Agent 1 → vLLM   :8000   → qwen3-8b
  - Agent 2 → Ollama :11434  → qwen2.5-coder:7b
  - Agent 3 → Ollama :11434  → qwen3:30b-a3b

Usage:
    python3 swarm_parallel_runner.py "your query"
    echo "your query" | python3 swarm_parallel_runner.py

Programmatic:
    from swarm_parallel_runner import (
        run_parallel_swarm, available_endpoints, first_content,
    )
    res = run_parallel_swarm("query", endpoints=available_endpoints())
    content, source = first_content(res)
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import socket
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# Repo root is this file's directory; import core.transport directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.transport import call_openai_compat  # noqa: E402

# Three independent endpoints — no shared proxy bottleneck.
DEFAULT_ENDPOINTS: list[dict[str, str]] = [
    {
        "name": "vllm-qwen3-8b",
        "url": "http://localhost:8000/v1",
        "model": "qwen3-8b",
        "api_key": "anything",
    },
    {
        "name": "ollama-qwen2.5-coder-7b",
        "url": "http://localhost:11434/v1",
        "model": "qwen2.5-coder:7b",
        "api_key": "anything",
    },
    {
        "name": "ollama-qwen3-30b-a3b",
        "url": "http://localhost:11434/v1",
        "model": "qwen3:30b-a3b",
        "api_key": "anything",
    },
]


def _chat_url(base: str) -> str:
    """Accept a base URL with or without /chat/completions and normalise."""
    base = base.rstrip("/")
    return base if base.endswith("/chat/completions") else base + "/chat/completions"


def endpoint_up(url: str, timeout: float = 0.5) -> bool:
    """Cheap TCP reachability probe so we never block on a dead endpoint."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return False
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def available_endpoints(
    endpoints: list[dict[str, str]] | None = None,
    timeout: float = 0.5,
) -> list[dict[str, str]]:
    """Return only endpoints whose host:port accepts a TCP connection."""
    endpoints = endpoints if endpoints is not None else DEFAULT_ENDPOINTS
    return [e for e in endpoints if endpoint_up(e["url"], timeout=timeout)]


def call_model(agent: dict[str, str], prompt: str, max_tokens: int = 2000) -> dict[str, Any]:
    """Call one endpoint. Never raises — returns an ok=False record on failure."""
    name = agent["name"]
    try:
        content, meta = call_openai_compat(
            provider="openrouter",
            prompt=prompt,
            model_override=agent["model"],
            sampling={"temperature": 0.2, "max_tokens": max_tokens},
            base_url=_chat_url(agent["url"]),
        )
        reasoning = (meta or {}).get("reasoning_content", "") or ""
        text = content if (content and content.strip()) else reasoning
        return {
            "name": name,
            "model": agent["model"],
            "content": text or "",
            "meta": meta or {},
            "ok": bool((text or "").strip()),
        }
    except Exception as e:  # noqa: BLE001 — endpoint isolation
        return {
            "name": name,
            "model": agent.get("model", "?"),
            "content": "",
            "meta": {},
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
        }


def run_parallel_swarm(
    query: str,
    endpoints: list[dict[str, str]] | None = None,
    max_tokens: int = 2000,
    max_workers: int | None = None,
) -> dict[str, Any]:
    """Fan a query out to every endpoint concurrently and collect results.

    Returns ``{query, agents, results, any_ok}`` where each result is a dict
    from :func:`call_model`. Ordering is deterministic (sorted by name).
    """
    eps = endpoints if endpoints is not None else DEFAULT_ENDPOINTS
    if not eps:
        return {"query": query, "agents": [], "results": [], "any_ok": False}

    workers = max_workers or len(eps)
    results: list[dict[str, Any]] = []
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(call_model, a, query, max_tokens): a for a in eps}
        for fut in cf.as_completed(futures):
            results.append(fut.result())
    results.sort(key=lambda r: r["name"])
    return {
        "query": query,
        "agents": [e["name"] for e in eps],
        "results": results,
        "any_ok": any(r.get("ok") for r in results),
    }


def first_content(result: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (content, source_name) of the first non-empty successful agent."""
    for r in result.get("results", []):
        if r.get("ok") and r.get("content"):
            return r["content"], r["name"]
    return None, None


def _main() -> int:
    usage = 'usage: python3 swarm_parallel_runner.py "<query>"'
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        print(usage)
        return 0
    query = " ".join(sys.argv[1:]).strip()
    if not query and not sys.stdin.isatty():
        query = sys.stdin.read().strip()
    if not query:
        print(usage, file=sys.stderr)
        return 2
    eps = available_endpoints()
    if not eps:
        print("No reachable endpoints (vLLM :8000 / Ollama :11434).", file=sys.stderr)
        return 1
    result = run_parallel_swarm(query, endpoints=eps)
    printable = {
        "query": result["query"],
        "agents": result["agents"],
        "any_ok": result["any_ok"],
        "results": [
            {k: v for k, v in r.items() if k != "meta"} for r in result["results"]
        ],
    }
    print(json.dumps(printable, indent=2))
    return 0 if result["any_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(_main())
