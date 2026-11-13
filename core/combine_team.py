from __future__ import annotations
import concurrent.futures as cf
import datetime
import json
import time
import urllib.request
from pathlib import Path
from typing import Optional, List, Dict, Any
from .transport import call_openai_compat, _empty_meta

DEFAULT_PROXY_URL = "http://localhost:4000/v1"
COST_CAP_USD = 0.05  # hard ceiling per SwarmTask run (free-tier-only default)


def fetch_live_aliases(base_url: str = DEFAULT_PROXY_URL) -> List[str]:
    """Resolve live aliases from GET /v1/models at runtime (never hardcode).

    If the proxy is down, falls back to probe_providers() which probes
    alternative endpoints (ollama local, pollinations, openrouter, etc.).
    """
    url = base_url.rstrip("/") + "/models"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "swarm-combine/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
        models = data.get("data", [])
        aliases = [m.get("id") for m in models if isinstance(m, dict) and m.get("id")]
        # Drop known legacy/dead and paid-only names that must not be defaults.
        drop = {"ZZZ_BAD_LEGACY_MIXED_F_MODE", "ZZZ_BAD_LEGACY_MIXED_F_MODE_FAST",
                "ZZZ_BAD_LEGACY_MIXED_F_MODE_LARGE", "ULTRA_PAID_MODE",
                "ULTRA_PAID_MODE_FAST", "ULTRA_PAID_MODE_LARGE", "PAID-DEEPSEEK-PRO",
                "PAID-DEEPSEEK-FLASH", "PAID-GROK"}
        aliases = [a for a in aliases if a not in drop]
        return aliases
    except Exception:
        # Proxy is down — fall back to probe_providers() which checks
        # alternative endpoints (ollama local, pollinations, openrouter, etc.).
        from probe_providers import resolve_best_model  # noqa: E402
        best = resolve_best_model(tier="free-proxy")
        if best:
            return [best["alias"]]
        return []


def is_live(res: Dict[str, Any]) -> bool:
    """Health gate: status 200 AND non-empty content OR reasoning_content (thinking models
    like LOCAL_CHAT/LOCAL_CODE return 0 chars of content at low max_tokens)."""
    if res.get("status") != 200:
        return False
    content = res.get("content") or ""
    if content.strip():
        return True
    meta = res.get("meta") or {}
    reasoning = meta.get("reasoning_content") or ""
    return bool(reasoning.strip())


def run_combine_team(
    query: str,
    n: int = 5,
    aliases: Optional[List[str]] = None,
    base_url: str = DEFAULT_PROXY_URL,
    api_key: str = "anything",
    results_dir: Optional[Path] = None,
    reply_mode: str = "files",
    show_source_labels: bool = True,
    cost_cap_usd: float = COST_CAP_USD,
    max_tokens: int = 300,  # >=300 so reasoning models emit content, not just reasoning
) -> Dict[str, Any]:
    """
    Consensus aggregation: Ask N AIs the same question simultaneously.
    Proxy-first: aliases resolved from GET /v1/models at runtime. Health gate counts
    reasoning_content as liveness so thinking models aren't misreported as dead.
    """
    if aliases is None:
        aliases = fetch_live_aliases(base_url)

    results = []
    seen_upstream = set()
    total_cost = 0.0
    start = time.monotonic()
    OVERALL_DEADLINE = 25  # seconds — swarm must answer fast or bail

    def try_alias(alias: str):
        try:
            content, meta = call_openai_compat(
                provider="openrouter",  # OpenAI-compat shape; proxy owns routing/auth
                prompt=query,
                model_override=alias,
                sampling={"temperature": 0.4, "max_tokens": max_tokens},
                base_url=base_url.rstrip("/") + "/chat/completions",  # LiteLLM proxy chat endpoint
            )
            # Prefer content, fall back to reasoning_content (thinking models)
            if not content or not content.strip():
                reasoning = meta.get("reasoning_content", "") or ""
                if reasoning and reasoning.strip():
                    content = reasoning
            return {"alias": alias, "content": content, "meta": meta, "status": 200}
        except Exception as e:
            return {"alias": alias, "error": str(e), "status": 500}

    with cf.ThreadPoolExecutor(max_workers=min(n, len(aliases))) as ex:
        futures = {ex.submit(try_alias, a): a for a in aliases}
        pending = set(futures)
        while pending and len(results) < n:
            # Respect the overall deadline.
            remaining = OVERALL_DEADLINE - (time.monotonic() - start)
            if remaining <= 0:
                break
            done, pending = cf.wait(pending, timeout=min(4.0, remaining),
                                    return_when=cf.FIRST_COMPLETED)
            for fut in done:
                res = fut.result()
                if not is_live(res):
                    continue
                meta = res.get("meta") or {}
                toks = int(meta.get("tokens_out", 0) or 0) + int(meta.get("tokens_in", 0) or 0)
                total_cost += toks * 0.000002
                if total_cost > cost_cap_usd:
                    continue
                upstream = meta.get("model_fingerprint", "unknown")
                if upstream in seen_upstream:
                    continue
                seen_upstream.add(upstream)
                results.append(res)
                if len(results) >= n:
                    break
        # Cancel any futures still pending so the executor can exit promptly.
        for fut in pending:
            fut.cancel()

    # Handle output
    output_dir = None
    if results_dir and reply_mode == "files":
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = results_dir / f"CombineTeam_{ts}"
        output_dir.mkdir(parents=True, exist_ok=True)

        summary_lines = [f"# CombineTeam Results\n\n**Query:** {query}\n\n**Date:** {datetime.datetime.now().isoformat()}\n"]
        for i, r in enumerate(results, 1):
            md_path = output_dir / f"response_{i:02d}_{r['alias'].replace('/', '_')}.md"
            md_path.write_text(
                f"# Response {i}: {r['alias']}\n\n**Upstream model:** {r['meta'].get('model_fingerprint', 'unknown')}\n\n---\n\n{r['content']}\n",
                encoding="utf-8",
            )
            summary_lines.append(f"## AI {i}: {r['alias']} ({r['meta'].get('model_fingerprint', 'unknown')})\n\n{r['content']}\n\n---\n")

        summary_lines.append(f"\n**Total cost est:** ${total_cost:.6f} (cap ${cost_cap_usd})\n")
        (output_dir / "SUMMARY.md").write_text("\n".join(summary_lines), encoding="utf-8")

    return {
        "query": query,
        "results": results,
        "output_dir": output_dir,
        "cost_usd": total_cost,
        "cost_cap_usd": cost_cap_usd,
    }
