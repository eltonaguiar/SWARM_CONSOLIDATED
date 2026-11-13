#!/usr/bin/env python3
"""
probe_providers.py — Probe and rank available LLM providers for fallback.

Checks (in priority order):
  1. vLLM :8000 — direct inference engine, concurrent capable (qwen3-8b)
  2. LiteLLM proxy (:4000) — consolidated free aliases (serial bottleneck)
  3. SubQ translation proxy (:8765) — decision model
  4. Ollama :11434 — keyless local models (qwen3:30b-a3b, qwen2.5-coder:7b, etc.)
  5. Pollinations (zero-key OpenAI-compatible)
  6. OpenRouter (paid key from dbpasses.txt)
  7. Local ollama CLI (last resort - slow)

Returns a ranked list of (alias, base_url, key_env, tier) tuples that are
currently reachable. Results are cached with a TTL so we don't re-probe
every call.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

VLLM_URL = "http://localhost:8000/v1"
PROXY_URL = "http://localhost:4000/v1"
SUBQ_URL = "http://localhost:127.0.0.1:8765/v1"
OLLAMA_URL = "http://localhost:11434"
POLLINATIONS_URL = "https://text.pollinations.ai/v1"

# Cache: (timestamp, list of (alias, base_url, key_env, tier))
_PROBE_CACHE: tuple[float, list[dict[str, str]]] | None = None
_PROBE_TTL = 60  # seconds


def _read_dbpasses_key(label_prefix: str) -> str | None:
    """Read a key from ~/dbpasses.txt by label prefix."""
    dbpasses = Path.home() / "dbpasses.txt"
    if not dbpasses.exists():
        return None
    try:
        text = dbpasses.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    for line in text.splitlines():
        if line.startswith(label_prefix):
            parts = line.split(None, 1)
            if len(parts) == 2:
                return parts[1].strip()
    return None


def _probe_json_get(url: str, timeout: int = 5) -> bool:
    """Quick GET probe — returns True if the endpoint responds with JSON."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "swarm-probe/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status == 200:
                r.read(1)
                return True
    except Exception:
        pass
    return False


def _probe_chat_completion(url: str, model: str, key: str | None,
                           timeout: int = 10) -> bool:
    """Quick chat/completions POST probe."""
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 5,
    }).encode()
    headers = {"Content-Type": "application/json", "User-Agent": "swarm-probe/1.0"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        pass
    return False


def probe_providers(force_refresh: bool = False) -> list[dict[str, str]]:
    """Return a ranked list of currently reachable providers.

    Each entry: {alias, base_url, key_env, tier, priority}
    Lower priority number = tried first.
    """
    global _PROBE_CACHE
    now = time.time()
    if _PROBE_CACHE and not force_refresh and (now - _PROBE_CACHE[0]) < _PROBE_TTL:
        return _PROBE_CACHE[1]

    providers: list[dict[str, str]] = []

    # ---- Tier 0: vLLM :8000 — direct inference engine, concurrent capable ----
    try:
        req = urllib.request.Request(
            f"{VLLM_URL}/models", headers={"User-Agent": "swarm-probe/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        for m in data.get("data", []):
            if isinstance(m, dict) and m.get("id"):
                providers.append({
                    "alias": m["id"],
                    "base_url": f"{VLLM_URL}/chat/completions",
                    "key_env": "none (vLLM keyless)",
                    "tier": "vllm-direct",
                    "priority": 0,
                })
    except Exception:
        pass

    # ---- Tier 1: LiteLLM proxy (:4000) - consolidated free aliases ----
    try:
        req = urllib.request.Request(
            f"{PROXY_URL}/models", headers={"User-Agent": "swarm-probe/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        aliases = [m.get("id") for m in data.get("data", [])
                   if isinstance(m, dict) and m.get("id")]
        dead = {"ZZZ_BAD_LEGACY_MIXED_F_MODE", "ZZZ_BAD_LEGACY_MIXED_F_MODE_FAST",
                "ZZZ_BAD_LEGACY_MIXED_F_MODE_LARGE", "ULTRA_PAID_MODE",
                "ULTRA_PAID_MODE_FAST", "ULTRA_PAID_MODE_LARGE",
                "PAID-DEEPSEEK-PRO", "PAID-DEEPSEEK-FLASH", "PAID-GROK"}
        for i, alias in enumerate([a for a in aliases if a not in dead]):
            providers.append({
                "alias": alias,
                "base_url": f"{PROXY_URL}/chat/completions",
                "key_env": "SWARM_PROXY_KEY (placeholder)",
                "tier": "free-proxy",
                "priority": 10 + i,
            })
    except Exception:
        pass

    # ---- Tier 2: SubQ translation proxy (:8765) - decision model ----
    try:
        req = urllib.request.Request(
            f"{SUBQ_URL}/models", headers={"User-Agent": "swarm-probe/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        for m in data.get("data", []):
            if isinstance(m, dict) and m.get("id"):
                providers.append({
                    "alias": m["id"],
                    "base_url": f"{SUBQ_URL}/chat/completions",
                    "key_env": "SUBQ_FREE_API_KEY / SUBQ_TOKEN_API_KEY",
                    "tier": "subq-decision",
                    "priority": 20,
                })
                break
    except Exception:
        pass

    # ---- Tier 3: Ollama :11434 — keyless local models ----
    try:
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/tags", headers={"User-Agent": "swarm-probe/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        models = [m.get("name", "") for m in data.get("models", [])]
        preferred = ["qwen2.5-coder:7b", "llama3.2:3b",
                     "qwen2.5:7b-instruct-fp16", "gemma4:31b-cloud"]
        chosen = None
        for p in preferred:
            if any(p in m for m in models):
                chosen = p
                break
        if not chosen and models:
            chosen = models[0]
        if chosen:
            providers.append({
                "alias": chosen,
                "base_url": f"{OLLAMA_URL}/api/chat",
                "key_env": "none (ollama keyless)",
                "tier": "ollama-local",
                "priority": 30,
            })
    except Exception:
        pass

    # ---- Tier 4: Pollinations (zero-key OpenAI-compatible) ----
    try:
        if _probe_chat_completion(f"{POLLINATIONS_URL}/chat/completions",
                                  "openai", None, timeout=8):
            providers.append({
                "alias": "pollinations/openai",
                "base_url": f"{POLLINATIONS_URL}/chat/completions",
                "key_env": "none (zero-key)",
                "tier": "pollinations-free",
                "priority": 40,
            })
    except Exception:
        pass

    # ---- Tier 5: OpenRouter (paid key from dbpasses.txt) ----
    openrouter_key = _read_dbpasses_key("OPENROUTER_API_KEY")
    if openrouter_key:
        try:
            if _probe_chat_completion(
                    "https://openrouter.ai/api/v1/chat/completions",
                    "openai/gpt-4o-mini", openrouter_key, timeout=10):
                providers.append({
                    "alias": "openrouter/gpt-4o-mini",
                    "base_url": "https://openrouter.ai/api/v1/chat/completions",
                    "key_env": "OPENROUTER_API_KEY (from dbpasses.txt)",
                    "tier": "openrouter-paid",
                    "priority": 50,
                })
        except Exception:
            pass

    # ---- Tier 6: Local ollama CLI (last resort - slow) ----
    try:
        import shutil
        if shutil.which("ollama"):
            providers.append({
                "alias": "ollama/local (llama3.2:3b)",
                "base_url": "ollama-cli",
                "key_env": "none (local CLI)",
                "tier": "ollama-local-cli",
                "priority": 90,
            })
    except Exception:
        pass

    _PROBE_CACHE = (now, providers)
    return providers


def resolve_best_model(preferred_alias: str | None = None,
                       tier: str | None = None) -> dict[str, str] | None:
    """Resolve the best available model alias.

    Args:
        preferred_alias: Try this alias first if it's available.
        tier: Filter by tier (vllm-direct, free-proxy, subq-decision,
              ollama-local, pollinations-free, openrouter-paid,
              ollama-local-cli).
    Returns:
        dict with alias, base_url, key_env, tier, priority — or None.
    """
    providers = probe_providers()
    if not providers:
        return None

    if tier:
        tiered = [p for p in providers if p["tier"] == tier]
        if tiered:
            providers = tiered

    if preferred_alias:
        for p in providers:
            if p["alias"] == preferred_alias:
                return p

    return providers[0]


def get_best_alias() -> str | None:
    """Return just the best available alias string."""
    p = resolve_best_model()
    return p["alias"] if p else None


if __name__ == "__main__":
    providers = probe_providers(force_refresh=True)
    print(f"Probed {len(providers)} available providers:")
    for p in sorted(providers, key=lambda x: x["priority"]):
        print(f"  {p['priority']:3d}  {p['alias']:<35}  {p['tier']:<20}  "
              f"{p['base_url']}  ({p['key_env']})")
