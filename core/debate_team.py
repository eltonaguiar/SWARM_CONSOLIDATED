from __future__ import annotations
import concurrent.futures as cf
import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from .transport import call_openai_compat

def run_debate_team(
    query: str, 
    rounds: int = 3, 
    n: int = 4, 
    aliases: Optional[List[str]] = None, 
    base_url: str = "http://localhost:4000/v1",
    api_key: str = "anything",
    results_dir: Optional[Path] = None,
    reply_mode: str = "files",
    show_source_labels: bool = True
) -> Dict[str, Any]:
    """
    Multi-round structured AI debate.
    Refactored from tools/freellm.py to be library-first.
    """
    if not aliases:
        aliases = [
            "free-mode-fast", "free-mode", "free-mode-large",
            "paid-mode", "paid-mode-large", "nvidia-deepseek-v4-pro",
            "openrouter-ring-1t", "claude-haiku-direct", "deepseek-chat-direct",
        ][:n]
    
    if len(aliases) < n:
        aliases = (aliases * ((n // len(aliases)) + 1))[:n]

    out_base = None
    if results_dir and reply_mode == "files":
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_base = results_dir / f"DebateTeam_{ts}"
        out_base.mkdir(parents=True, exist_ok=True)
        (out_base / "PROMPT.txt").write_text(
            f"topic: {query}\nrounds: {rounds}\ndebaters: {n}\naliases: {','.join(aliases)}\n",
            encoding="utf-8"
        )

    # Initialize history for each debater
    history: List[List[Dict[str, str]]] = [
        [
            {"role": "system", "content": (
                f"You are Debater {i+1} in a structured AI debate. "
                "Give clear, well-reasoned arguments. "
                "In critique rounds you MUST directly address the other responses shown to you."
            )},
            {"role": "user", "content": f"Debate topic: {query}\n\nPlease give your OPENING position."}
        ]
        for i in range(n)
    ]

    round_results: Dict[int, List[Dict[str, Any]]] = {}

    for rnd in range(1, rounds + 1):
        rnd_dir = None
        if out_base:
            rnd_dir = out_base / f"Round_{rnd:02d}"
            rnd_dir.mkdir(exist_ok=True)
        
        # Build cross-review context for rounds > 1
        if rnd > 1:
            prev_replies = "\n\n".join(
                f"=== Debater {j+1} ({r['alias']}) ===\n{r['content']}"
                for j, r in enumerate(round_results[rnd - 1])
            )
            for i in range(n):
                if rnd == rounds:
                    new_msg = (
                        "All debaters have now responded. "
                        "As a judge/summarizer, synthesize the key points from all sides, "
                        "identify the strongest arguments, and declare what the debate consensus is (or explain remaining disagreement)."
                        f"\n\nAll responses so far:\n{prev_replies}"
                    )
                else:
                    new_msg = (
                        f"Round {rnd}: Review the other debaters' Round {rnd-1} responses below "
                        "and write your critique and rebuttal.\n\n"
                        f"{prev_replies}"
                    )
                history[i].append({"role": "user", "content": new_msg})

        def run_debater(i: int) -> Dict[str, Any]:
            alias = aliases[i % len(aliases)]
            # Reconstruct messages for the specific debater
            msgs = history[i]
            try:
                content, meta = call_openai_compat(
                    provider="openrouter", 
                    prompt="\n\n".join([m["content"] for m in msgs]), # Simplified for transport
                    model_override=alias,
                    sampling={"temperature": 0.6, "max_tokens": 1500}
                )
                return {"alias": alias, "content": content, "meta": meta, "status": 200}
            except Exception as e:
                return {"alias": alias, "error": str(e), "status": 500}

        with cf.ThreadPoolExecutor(max_workers=n) as ex:
            futs = list(ex.map(run_debater, range(n)))
        
        round_results[rnd] = futs

        if rnd_dir:
            for i, res in enumerate(futs):
                if res["status"] == 200:
                    md_path = rnd_dir / f"debater_{i+1:02d}_{res['alias'].replace('/', '_')}.md"
                    md_path.write_text(
                        f"# Round {rnd} — Debater {i+1}: {res['alias']}\n\n"
                        f"**Upstream:** {res['meta'].get('model_fingerprint', 'unknown')}\n\n---\n\n{res['content']}\n",
                        encoding="utf-8"
                    )
        
        # Append response to history
        for i, res in enumerate(futs):
            content = res.get("content", "") if res["status"] == 200 else "[Error response]"
            history[i].append({"role": "assistant", "content": content})

    # Summary
    summary = [f"# DebateTeam Summary\n\n**Topic:** {query}\n**Rounds:** {rounds}  **Debaters:** {n}\n\n---\n"]
    for rnd in range(1, rounds + 1):
        summary.append(f"## Round {rnd}\n")
        for j, r in enumerate(round_results[rnd]):
            res_content = r.get("content", "") if r["status"] == 200 else "[Error]"
            summary.append(f"### Debater {j+1} ({r['alias']})\n\n{res_content}\n\n")

    if out_base:
        (out_base / "DEBATE_SUMMARY.md").write_text("\n".join(summary), encoding="utf-8")

    return {
        "query": query,
        "round_results": round_results,
        "output_dir": out_base
    }
