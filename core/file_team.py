from __future__ import annotations
import concurrent.futures as cf
from pathlib import Path
from typing import Optional, List, Dict, Any
from .transport import call_openai_compat

CHAR_LIMIT_LARGE = 8_000

def _pick_alias_for_size(char_count: int, tier: str, aliases: List[str]) -> str:
    if tier == "large" or char_count > CHAR_LIMIT_LARGE:
        for a in aliases:
            if "large" in a:
                return a
    if tier == "paid":
        for a in aliases:
            if "paid" in a:
                return a
    return aliases[0]

def run_file_team(
    files: List[str], 
    prompt: str = "Summarize and extract key insights from the following document.", 
    chunk: int = 3, 
    tier: str = "auto", 
    aliases: Optional[List[str]] = None, 
    results_dir: Optional[Path] = None,
    base_url: str = "http://localhost:4000/v1",
    api_key: str = "anything"
) -> Dict[str, Any]:
    """
    Divide a list of files across multiple AIs in parallel.
    Refactored from tools/freellm.py to be library-first.
    """
    if not aliases:
        aliases = [
            "free-mode-fast", "free-mode", "free-mode-large",
            "paid-mode", "paid-mode-large", "nvidia-deepseek-v4-pro",
            "openrouter-ring-1t", "claude-haiku-direct", "deepseek-chat-direct",
        ]

    resolved: List[Path] = []
    for f in files:
        p = Path(f)
        if p.exists():
            resolved.append(p)

    if not resolved:
        return {"error": "No valid files provided", "results": []}

    out_dir = results_dir if results_dir else Path("tools/FREELLM/RESULTS")
    # Create a timestamped subfolder
    import datetime
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_folder = out_dir / f"FileTeam_{ts}"
    out_folder.mkdir(parents=True, exist_ok=True)

    def process_file(fp: Path):
        content = fp.read_text(encoding="utf-8", errors="replace")
        char_count = len(content)
        alias = _pick_alias_for_size(char_count, tier, aliases)

        sections = [content]
        if char_count > 12_000:
            size = 8_000
            sections = [content[i:i+size] for i in range(0, char_count, size)]
        
        parts = []
        for idx, section in enumerate(sections, 1):
            msg_content = f"{prompt}\n\n---\n\nFile: {fp.name}"
            if len(sections) > 1:
                msg_content += f" (section {idx}/{len(sections)})"
            msg_content += f"\n\n{section}"
            
            try:
                content_res, meta = call_openai_compat(
                    provider="openrouter",
                    prompt=msg_content,
                    model_override=alias,
                    sampling={"temperature": 0.2, "max_tokens": 2000}
                )
                parts.append(content_res)
            except Exception as e:
                parts.append(f"[ERROR section {idx}: {e}]")
        
        combined = "\n\n---\n\n".join(parts)
        out_file = out_folder / (fp.stem + "_result.md")
        out_file.write_text(
            f"# FileTeam Result: {fp.name}\n\n"
            f"**Instruction:** {prompt}\n\n"
            f"**Model alias:** {alias}\n\n---\n\n{combined}\n",
            encoding="utf-8"
        )
        return fp, combined

    all_results = []
    for batch_start in range(0, len(resolved), chunk):
        batch = resolved[batch_start: batch_start + chunk]
        with cf.ThreadPoolExecutor(max_workers=len(batch)) as ex:
            batch_results = list(ex.map(process_file, batch))
        all_results.extend(batch_results)

    index_lines = [f"# FileTeam Index\n\n**Instruction:** {prompt}\n\n"]
    for fp, reply in all_results:
        index_lines.append(f"## {fp.name}\n\n{reply[:400]}{'...' if len(reply) > 400 else ''}\n\n---\n")
    
    (out_folder / "INDEX.md").write_text("\n".join(index_lines), encoding="utf-8")

    return {
        "results": all_results,
        "output_dir": out_folder
    }
