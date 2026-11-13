#!/usr/bin/env python3
"""
Swarm Acceptance Driver — BROKENMERMAIDTEST (Phase 2)

The swarm diagnoses + fixes the broken Mermaid pages itself.

Method:
  1. Fetch each case page from GitHub Pages (raw HTML).
  2. Extract the mermaid block; validate its syntax LOCALLY with mermaid@10.9.1
     (/tmp/mm_bench/validate.mjs). If ok:false -> broken. (Client-side JS render
     can't be seen in raw HTML, so local syntax validation is the ground truth.)
  3. For each broken page, ask the swarm (CombineTeam via consolidated core/
     transport, proxy-first, aliases from GET /v1/models) to diagnose the root
     cause and emit a COMPLETE fixed mermaid block (nodes + edges, valid at 10.9.1).
  4. Re-validate the fix locally (validate.mjs -> ok:true). Only then apply it.
  5. Push all fixed files via GitHub Contents API -> re-triggers Pages deploy.

No dbpasses.txt reads anywhere — proxy-first, alias + placeholder key only.
"""
from __future__ import annotations
import base64
import json
import re
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

REPO = "eltonaguiar/BROKENMERMAIDTEST"
BASE = f"https://eltonaguiar.github.io/{REPO.split('/')[-1]}"
PAGES = [
    "index.html",
    "case-a-unquoted-parens.html",
    "case-b-unbalanced-brackets.html",
    "case-c-unclosed-subgraph.html",
    "case-d-type-not-line1.html",
    "case-e-pipe-in-label.html",
    "case-f-raw-jekyll.html",
]
LOCAL = Path("/tmp/bmtest")
TOKEN = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()

sys.path.insert(0, str(Path.home() / "SWARM_CONSOLIDATED"))
from core.combine_team import run_combine_team  # noqa: E402

VALIDATOR = Path("/tmp/mm_bench/validate.mjs")


def api(method: str, path: str, data=None):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/{path}", method=method,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Authorization": f"token {TOKEN}",
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as x:
        return json.loads(x.read())


def current_sha(path: str) -> str:
    return api("GET", f"contents/{path}?ref=main")["sha"]


def push_file(path: str, content: str, message: str):
    body = {"message": message, "content": base64.b64encode(content.encode()).decode(), "branch": "main"}
    try:
        body["sha"] = current_sha(path)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    api("PUT", f"contents/{path}", body)
    print(f"  pushed {path}")


def fetch_page(page: str) -> str:
    url_path = "" if page == "index.html" else page
    url = f"{BASE}/{url_path}" if url_path else BASE + "/"
    req = urllib.request.Request(url, headers={"User-Agent": "swarm-driver/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def extract_mmd_blocks(html: str) -> list[str]:
    return re.findall(r'<div class="mermaid">\s*(.*?)\s*</div>', html, re.S)


def validate_mmd(block: str) -> dict:
    import tempfile, os as _os
    with tempfile.NamedTemporaryFile("w", suffix=".mmd", delete=False) as f:
        f.write(block); tmp = f.name
    try:
        proc = subprocess.run(["node", str(VALIDATOR), tmp], text=True,
                              capture_output=True, timeout=30)
        out = (proc.stdout or "").strip()
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return {"ok": False, "err": out[:200] or (proc.stderr or "")[:200]}
    finally:
        _os.unlink(tmp)


FIX_PROMPT_TEMPLATE = """You are a mermaid@10.9.1 expert. A GitHub Pages file renders a broken
mermaid diagram (mermaid 10.9.1 reports 'Syntax error in text' or no SVG).

Broken mermaid block:
------------------
{block}
------------------

Task:
1. State the root cause in one short sentence.
2. Then output a SINGLE fenced code block (```mermaid ... ```) containing the
   COMPLETE corrected mermaid diagram. Requirements:
   - At least 2 nodes and 1 edge (an empty `flowchart TD` is NOT acceptable).
   - Diagram type keyword (flowchart/graph) on line 1, no leading blank line/comment.
   - ASCII text only; balanced brackets/parens; labels with parens `()` or pipe `|`
     must be QUOTED: `E["label with (parens) or | pipe"]`.
   - Must parse cleanly under mermaid@10.9.1 and render a visible diagram.
Output ONLY the fence + diagram. No prose after the fence."""


def extract_fence(answer: str) -> str | None:
    m = re.findall(r"```(?:mermaid)?\s*\n(.*?)\n```", answer, re.S)
    if m:
        return m[0].strip()
    for line in answer.strip().splitlines():
        first = line.strip().split()[0] if line.strip() else ""
        if first in ("flowchart", "graph", "sequenceDiagram", "classDiagram", "stateDiagram"):
            return answer.strip()
        break
    return None


def swarm_fix(page: str, block: str) -> str | None:
    query = FIX_PROMPT_TEMPLATE.format(block=block)
    print(f"  {page}: asking swarm to diagnose + fix...", flush=True)
    result = run_combine_team(query, n=3, max_tokens=500)
    if not result["results"]:
        print(f"  {page}: swarm returned no usable answer", flush=True)
        return None
    best = result["results"][0]["content"]
    fixed = extract_fence(best)
    if not fixed:
        print(f"  {page}: swarm answer had no mermaid block:\n{best[:300]}", flush=True)
        return None
    print(f"  {page}: swarm fix candidate ({len(fixed)}b): {fixed.splitlines()[0]}", flush=True)
    return fixed


def apply_fix(page: str, fixed_block: str) -> str:
    html = (LOCAL / page).read_text(encoding="utf-8")
    new_html, n = re.subn(
        r'(<div class="mermaid">\s*)(.*?)(\s*</div>)',
        lambda m: m.group(1) + fixed_block + m.group(3),
        html, count=1, flags=re.S,
    )
    if n != 1:
        raise RuntimeError(f"could not replace mermaid block in {page}")
    (LOCAL / page).write_text(new_html, encoding="utf-8")
    return new_html


def main():
    fixed_pages = []
    for page in PAGES:
        print(f"\n== {page} ==", flush=True)
        html = fetch_page(page)
        blocks = extract_mmd_blocks(html)
        if not blocks:
            print(f"  no mermaid block, skipping", flush=True)
            continue
        block = blocks[0].strip()
        vr = validate_mmd(block)
        broken = not vr.get("ok", False)
        print(f"  local validate: ok={vr.get('ok')} err={vr.get('err','')[:90]}", flush=True)
        if not broken:
            print(f"  {page}: already valid, skipping", flush=True)
            continue
        fixed_block = swarm_fix(page, block)
        if not fixed_block:
            print(f"  {page}: FIX FAILED", flush=True)
            continue
        fvr = validate_mmd(fixed_block)
        if not fvr.get("ok", False):
            print(f"  {page}: swarm fix INVALID at 10.9.1 ({fvr.get('err','')[:90]}), skipping", flush=True)
            continue
        apply_fix(page, fixed_block)
        fixed_pages.append(page)
        print(f"  {page}: FIX APPLIED (valid at 10.9.1)", flush=True)

    if not fixed_pages:
        print("\nNo fixes applied.", flush=True)
        return

    msg = """Swarm auto-fix: diagnose + repair broken mermaid diagrams

The swarm fetched each broken case page, validated mermaid syntax locally at
mermaid@10.9.1, diagnosed the root cause (unquoted parens / unbalanced brackets /
unclosed subgraph / type not on line 1 / pipe in label / Jekyll shim skip),
emitted a complete corrected diagram, re-validated it locally, and applied the
fixes. Re-deploys GitHub Pages for end-to-end validation."""
    for page in fixed_pages:
        push_file(page, (LOCAL / page).read_text(encoding="utf-8"), msg)
    print(f"\nFixed {len(fixed_pages)} page(s) — Pages redeploy triggered.")


if __name__ == "__main__":
    main()
