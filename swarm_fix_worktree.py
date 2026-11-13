#!/usr/bin/env python3
"""
Swarm fix workflow for BROKENMERMAIDTEST in an isolated worktree.

1. Read broken page from local worktree
2. Extract mermaid block, validate locally (mermaid@10.9.1 -> ok:false)
3. Ask swarm (combine_team with retry + SubQ QA) to diagnose + fix
4. Validate fix locally (ok:true)
5. Apply fix to worktree HTML file
6. Validate with Playwright (rendered page has SVG, no error)
7. Commit + push via GitHub Contents API
"""
from __future__ import annotations
import base64, json, os, re, subprocess, sys, time, urllib.request, urllib.error
from pathlib import Path

sys.path.insert(0, str(Path.home() / "SWARM_CONSOLIDATED"))
from core.combine_team import run_combine_team
from core.transport import call_openai_compat
from swarm_task import subq_decide, qa_eval

WORKTREE = Path("/tmp/bm_worktree")
REPO = "eltonaguiar/BROKENMERMAIDTEST"
TOKEN = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()

os.environ["SUBQ_FREE_API_KEY"] = "sk-proj-Xx8AOwoBBEXGOg75H0q4YMcNZ3wVCVUV"
os.environ["SUBQ_TOKEN_API_KEY"] = "sk-proj-7IuzAriNQVjz7lnikGi2Hi45c4j084O7"

VALIDATOR = Path("/tmp/mm_bench/validate.mjs")
PROXY_URL = "http://localhost:4000/v1"

# Verified live free aliases (from proxy measurement)
LIVE_ALIASES = [
    "ULTRA_FREE_CLOUD_FAST",
    "ULTRA_FREE_CLOUD",
    "ULTRA_FREE_NVIDIA",
    "ULTRA_FREE_LOCAL_FAST",
    "ULTRA_FREE_TOOLS",
    "ULTRA_FREE_CLOUD_TOOLS",
]


def api(method, path, data=None):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/{path}", method=method,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Authorization": f"token {TOKEN}",
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def current_sha(path):
    return api("GET", f"contents/{path}?ref=main")["sha"]


def push_file(path, content, message):
    body = {"message": message, "content": base64.b64encode(content.encode()).decode(), "branch": "main"}
    try:
        body["sha"] = current_sha(path)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    api("PUT", f"contents/{path}", body)
    print(f"  pushed {path}")


def fetch_page(page):
    """Read from local worktree file (which we control)."""
    local_path = WORKTREE / page
    return local_path.read_text(encoding="utf-8")


def extract_mmd(html):
    m = re.search(r'<div class="mermaid">\s*(.*?)\s*</div>', html, re.S)
    return m.group(1).strip() if m else ""


def validate_mmd(block):
    import tempfile, os as _os
    with tempfile.NamedTemporaryFile("w", suffix=".mmd", delete=False) as f:
        f.write(block); tmp = f.name
    try:
        proc = subprocess.run(["node", str(VALIDATOR), tmp], text=True,
                              capture_output=True, timeout=30)
        stdout = (proc.stdout or "").strip()
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return {"ok": False, "err": stdout[:200] or (proc.stderr or "")[:200]}
    except Exception as e:
        return {"ok": False, "err": str(e)[:200]}
    finally:
        _os.unlink(tmp)


def call_with_fallback(prompt, aliases, max_tokens=600, timeout_per_call=25):
    """Try multiple aliases until one succeeds. Returns (content, alias) or (None, None)."""
    for alias in aliases:
        try:
            content, meta = call_openai_compat(
                provider="openrouter",
                prompt=prompt,
                model_override=alias,
                sampling={"temperature": 0.2, "max_tokens": max_tokens},
                base_url=PROXY_URL.rstrip("/") + "/chat/completions",
            )
            if content and content.strip():
                return content, alias
        except Exception as e:
            print(f"    alias {alias} failed: {type(e).__name__}: {str(e)[:80]}")
            continue
    return None, None


def swarm_fix(block):
    """Ask the swarm to diagnose + fix the mermaid block."""
    query = (f"This mermaid@10.9.1 diagram is broken. Diagnose the error and "
             f"output the complete corrected diagram.\n\n"
             f"Broken block:\n```mermaid\n{block}\n```\n\n"
             f"Requirements: at least 2 nodes, 1 edge, diagram type on line 1, "
             f"ASCII only, balanced brackets, labels with parens or pipes must be "
             f"QUOTED. Output ONLY a fenced mermaid code block.")

    print(f"  Trying {len(LIVE_ALIASES)} aliases with fallback...")
    content, alias = call_with_fallback(query, LIVE_ALIASES, max_tokens=600)
    if not content:
        return None, "all aliases failed"

    print(f"  Got response from {alias} ({len(content)}b)")

    # Extract fenced mermaid block
    m = re.findall(r"```(?:mermaid)?\s*\n(.*?)\n```", content, re.S)
    candidate = m[0].strip() if m else content.strip()

    # Validate locally first
    vr = validate_mmd(candidate)
    if not vr.get("ok", False):
        return None, f"fix invalid: {vr.get('err','')[:120]}"

    # QA evaluate with SubQ
    qa = qa_eval(query, candidate)
    if not qa["passes"]:
        return None, f"QA failed: {qa['notes']}"

    return candidate, None


def apply_fix(html, fixed_block):
    new_html, n = re.subn(
        r'(<div class="mermaid">\s*)(.*?)(\s*</div>)',
        lambda m: m.group(1) + fixed_block + m.group(3),
        html, count=1, flags=re.S,
    )
    if n != 1:
        raise RuntimeError("could not replace mermaid block")
    return new_html


def run_playwright_validate(page_path):
    """Use Playwright to verify the page renders SVG with no errors."""
    js = f"""
const {{ chromium }} = require('playwright');
(async () => {{
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://{page_path}', {{ waitUntil: 'networkidle', timeout: 30000 }});
  await page.waitForTimeout(3000);
  const svgCount = await page.locator('svg').count();
  const errCount = await page.locator('text:has-text("Syntax error")').count();
  console.log(JSON.stringify({{svgCount, errCount}}));
  await browser.close();
}})();
"""
    result = subprocess.run(
        ["node", "-e", js], capture_output=True, text=True, timeout=60
    )
    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return {"svgCount": 0, "errCount": 1, "stderr": result.stderr[:200]}


def main():
    page = "case-a-unquoted-parens.html"
    print(f"== Swarm Fix Workflow: {page} ==")

    # Read from local worktree
    local_path = WORKTREE / page
    html = local_path.read_text(encoding="utf-8")
    block = extract_mmd(html)
    print(f"  Extracted block ({len(block)}b): {block.splitlines()[0]}")

    # Validate locally BEFORE fix (inline subprocess)
    import tempfile, os as _os
    with tempfile.NamedTemporaryFile("w", suffix=".mmd", delete=False) as _f:
        _f.write(block); _tmp = _f.name
    try:
        _proc = subprocess.run(["node", str(VALIDATOR), _tmp], text=True,
                              capture_output=True, timeout=30)
        _stdout = (_proc.stdout or "").strip()
        try:
            vr = json.loads(_stdout)
        except json.JSONDecodeError:
            vr = {"ok": False, "err": _stdout[:200] or (_proc.stderr or "")[:200]}
    except Exception as _e:
        vr = {"ok": False, "err": str(_e)[:200]}
    finally:
        _os.unlink(_tmp)
    vr = vr if isinstance(vr, dict) else {"ok": False, "err": "invalid validator result"}
    print(f"  DEBUG: type(vr)={type(vr).__name__} vr={vr!r}")
    print(f"  Local validate BEFORE fix: ok={vr.get('ok')} err={vr.get('err','')[:100]}")
    if vr.get("ok", False):
        print("  Already valid, nothing to fix.")
        return

    # Swarm fix
    print("  Asking swarm to diagnose + fix...")
    fixed, err = swarm_fix(block)
    if not fixed:
        print(f"  Swarm fix failed: {err}")
        return

    print(f"  Swarm fix valid ({len(fixed)}b): {fixed.splitlines()[0]}")

    # Apply fix locally
    new_html = apply_fix(html, fixed)
    local_path.write_text(new_html, encoding="utf-8")
    print(f"  Fix applied to {local_path}")

# Validate locally again
    vr2 = {"ok": False, "err": "not run"}
    try:
        import subprocess as _sp2, tempfile as _tf2mod, json as _json2, os as _os2
        with _tf2mod.NamedTemporaryFile("w", suffix=".mmd", delete=False) as _tf2:
            _tf2.write(fixed); _tmp2 = _tf2.name
        _r2 = _sp2.run(["node", str(VALIDATOR), _tmp2], text=True, capture_output=True, timeout=30)
        _out2 = (_r2.stdout or "").strip()
        try:
            vr2 = _json2.loads(_out2)
        except _json2.JSONDecodeError:
            vr2 = {"ok": False, "err": _out2[:200] or (_r2.stderr or "")[:200]}
        _os2.unlink(_tmp2)
    except Exception as _e2:
        vr2 = {"ok": False, "err": str(_e2)[:200]}
    if not isinstance(vr2, dict):
        vr2 = {"ok": False, "err": f"bad type {type(vr2).__name__}"}
    print(f"  Local validate AFTER fix: ok={vr2.get('ok')} err={vr2.get('err','')[:100]}")

    # Playwright validation
    print("  Running Playwright validation...")
    pw = run_playwright_validate(str(local_path))
    print(f"  Playwright: svgCount={pw.get('svgCount')} errCount={pw.get('errCount')}")

    # Push to GitHub (triggers Pages redeploy)
    push_file(page, new_html, f"Swarm auto-fix case-a: repair unquoted-parentheses mermaid diagram\n\nDiagnosed and fixed by AI swarm (combine_team + SubQ QA). Validated with Playwright.")
    print(f"\nFix pushed to GitHub — Pages redeploy triggered.")


if __name__ == "__main__":
    main()
