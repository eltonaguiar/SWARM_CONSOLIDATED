from __future__ import annotations
import concurrent.futures as cf
import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from .transport import call_openai_compat, _empty_meta

def run_combine_team(
    query: str, 
    n: int = 5, 
    aliases: Optional[List[str]] = None, 
    base_url: str = "http://localhost:4000/v1",
    api_key: str = "anything",
    results_dir: Optional[Path] = None,
    reply_mode: str = "files",
    show_source_labels: bool = True
) -> Dict[str, Any]:
    """
    Consensus aggregation: Ask N AIs the same question simultaneously.
    Refactored from tools/freellm.py to be library-first.
    """
    if not aliases:
        aliases = [
            "free-mode-fast", "free-mode", "free-mode-large",
            "paid-mode", "paid-mode-large", "nvidia-deepseek-v4-pro",
            "openrouter-ring-1t", "claude-haiku-direct", "deepseek-chat-direct",
        ]

    messages = [{"role": "user", "content": query}]
    results = []
    seen_upstream = set()

    def try_alias(alias: str):
        # Use the consolidated transport layer
        # Since we are routing through LiteLLM proxy, the provider is effectively 'openrouter' or 'openai'
        # but we use the alias as the 'model' override.
        try:
            content, meta = call_openai_compat(
                provider="openrouter", # Proxy usually maps to OpenAI-compat
                prompt=query,
                model_override=alias,
                sampling={"temperature": 0.4, "max_tokens": 1500}
            )
            return {"alias": alias, "content": content, "meta": meta, "status": 200}
        except Exception as e:
            return {"alias": alias, "error": str(e), "status": 500}

    with cf.ThreadPoolExecutor(max_workers=min(n, len(aliases))) as ex:
        futures = {ex.submit(try_alias, a): a for a in aliases}
        for fut in cf.as_completed(futures):
            res = fut.result()
            if res["status"] != 200 or not res.get("content", "").strip():
                continue
            
            upstream = res["meta"].get("model_fingerprint", "unknown")
            if upstream in seen_upstream:
                continue
            
            seen_upstream.add(upstream)
            results.append(res)
            if len(results) >= n:
                break

    # Handle output
    if results_dir and reply_mode == "files":
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_folder = results_dir / f"CombineTeam_{ts}"
        out_folder.mkdir(parents=True, exist_ok=True)
        
        summary_lines = [f"# CombineTeam Results\n\n**Query:** {query}\n\n**Date:** {datetime.datetime.now().isoformat()}\n"]
        for i, r in enumerate(results, 1):
            md_path = out_folder / f"response_{i:02d}_{r['alias'].replace('/', '_')}.md"
            md_path.write_text(
                f"# Response {i}: {r['alias']}\n\n**Upstream model:** {r['meta'].get('model_fingerprint', 'unknown')}\n\n---\n\n{r['content']}\n", 
                encoding="utf-8"
            )
            summary_lines.append(f"## AI {i}: {r['alias']} ({r['meta'].get('model_fingerprint', 'unknown')})\n\n{r['content']}\n\n---\n")
        
        (out_folder / "SUMMARY.md").write_text("\n".join(summary_lines), encoding="utf-8")

    return {
        "query": query,
        "results": results,
        "output_dir": out_folder if results_dir and reply_mode == "files" else None
    }
