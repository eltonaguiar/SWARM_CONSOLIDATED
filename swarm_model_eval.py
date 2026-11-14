#!/usr/bin/env python3
"""
Multi-Model Mermaid Fix Evaluation Harness (FIXED).

Key fixes from first run:
1. Extract mermaid blocks from BOTH content AND reasoning_content (thinking models)
2. Remove SubQ QA (decision model, not code QA) — use mermaid validation + Playwright only
3. Higher max_tokens (1200) for thinking models
4. Track content vs reasoning_content source
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path.home() / "SWARM_CONSOLIDATED"))
from core.transport import call_openai_compat  # noqa: E402
from probe_providers import resolve_best_model  # noqa: E402

REPO = "eltonaguiar/BROKENMERMAIDTEST"
TOKEN = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()
VALIDATOR = Path("/tmp/mm_bench/validate.mjs")

os.environ["SUBQ_FREE_API_KEY"] = "sk-proj-Xx8AOwoBBEXGOg75H0q4YMcNZ3wVCVUV"
os.environ["SUBQ_TOKEN_API_KEY"] = "sk-proj-7IuzAriNQVjz7lnikGi2Hi45c4j084O7"

# Model candidates — grouped by tier
MODELS = [
    # Free tier
    ("ULTRA_FREE_CLOUD_FAST", "free"),
    ("ULTRA_FREE_CLOUD", "free"),
    ("ULTRA_FREE_NVIDIA", "free"),
    ("ULTRA_FREE_LOCAL_FAST", "free"),
    ("ULTRA_FREE_TOOLS", "free"),
    ("ULTRA_FREE_CLOUD_LARGE", "free"),
    ("ULTRA_FREE_CLOUD_TOOLS", "free"),
    ("ULTRA_FREE_OPENROUTER", "free"),
    ("ULTRA_FREE_GEMINI", "free"),
    ("ULTRA_FREE_KILO", "free"),
    ("ULTRA_FREE_LOCAL_CODE", "free"),
    ("ULTRA_FREE_LOCAL_CHAT", "free"),
    # Paid tier
    ("ULTRA_PAID_MODE", "paid"),
    ("PAID-DEEPSEEK-PRO", "paid"),
    ("PAID-DEEPSEEK-FLASH", "paid"),
    ("PAID-GROK", "paid"),
]

BROKEN_MMD = """flowchart TD
    E[Synchronous REST<br/>RESTMessageV2.execute()] --> D{OK?}
    D -->|No| F[Retry]
"""

BROKEN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Broken Mermaid Test — Case A</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.css">
</head>
<body>
  <h1>Case A — Unquoted Parentheses (broken)</h1>
  <div class="mermaid">
flowchart TD
    E[Synchronous REST<br/>RESTMessageV2.execute()] --> D{OK?}
    D -->|No| F[Retry]
  </div>
  <script>mermaid.initialize({ startOnLoad: true, theme: 'default' });</script>
</body>
</html>"""

FIXED_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Broken Mermaid Test — Case A (FIXED)</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.css">
</head>
<body>
  <h1>Case A — Unquoted Parentheses (FIXED)</h1>
  <div class="mermaid">
flowchart TD
    E["Synchronous REST<br/>RESTMessageV2.execute()"] --> D{OK?}
    D -->|No| F[Retry]
  </div>
  <script>mermaid.initialize({ startOnLoad: true, theme: 'default' });</script>
</body>
</html>"""


def gh_api(method: str, path: str, data=None):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/{path}", method=method,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Authorization": f"token {TOKEN}",
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"GitHub API {e.code} {method} {path}: {body}")


def model_branch(model_alias: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9]", "-", model_alias).lower()
    return f"eval/{safe}"


def ensure_branch(branch: str) -> str:
    try:
        ref = gh_api("GET", f"git/ref/heads/{branch}")
        return ref["object"]["sha"]
    except RuntimeError:
        main_sha = gh_api("GET", "git/ref/heads/main")["object"]["sha"]
        ref = gh_api("POST", "git/refs", {"ref": f"refs/heads/{branch}", "sha": main_sha})
        return ref["object"]["sha"]


def push_file_to_branch(branch: str, path: str, content: str, message: str):
    body = {"message": message, "content": base64.b64encode(content.encode()).decode(), "branch": branch}
    try:
        cur = gh_api("GET", f"contents/{path}?ref={branch}")
        body["sha"] = cur["sha"]
    except RuntimeError:
        pass
    gh_api("PUT", f"contents/{path}", body)


def validate_mmd(block: str) -> dict:
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".mmd", delete=False) as f:
        f.write(block); tmp = f.name
    try:
        proc = subprocess.run(["node", str(VALIDATOR), tmp], text=True,
                              capture_output=True, timeout=30)
        try:
            return json.loads((proc.stdout or "").strip())
        except json.JSONDecodeError:
            return {"ok": False, "err": (proc.stdout or proc.stderr or "")[:200]}
    finally:
        import os; os.unlink(tmp)


def extract_mmd_from_text(text: str) -> str | None:
    """Extract mermaid block from text (content or reasoning_content)."""
    m = re.findall(r"```(?:mermaid)?\s*\n(.*?)\n```", text, re.S)
    if m:
        return m[0].strip()
    # Fallback: if text starts with diagram keyword
    first = text.strip().splitlines()[0] if text.strip() else ""
    if first.split()[0] if first.split() else "" in ("flowchart", "graph", "sequenceDiagram", "classDiagram", "stateDiagram"):
        return text.strip()
    return None


DEFAULT_PROXY_URL = "http://localhost:4000/v1/chat/completions"


def call_model(model_alias: str, prompt: str, max_tokens: int = 1200,
               base_url: str | None = None) -> tuple[str, dict, str]:
    """Call a single model. Returns (content_or_reasoning, meta, source_type).

    ``base_url`` lets callers route to the resolved provider endpoint (e.g. a
    local vLLM/Ollama fallback) instead of always hitting the :4000 proxy.
    """
    content, meta = call_openai_compat(
        provider="openrouter",
        prompt=prompt,
        model_override=model_alias,
        sampling={"temperature": 0.2, "max_tokens": max_tokens},
        base_url=base_url or DEFAULT_PROXY_URL,
    )
    # Prefer content, fall back to reasoning_content (thinking models)
    if content and content.strip():
        return content, meta, "content"
    reasoning = meta.get("reasoning_content", "") or ""
    if reasoning and reasoning.strip():
        return reasoning, meta, "reasoning_content"
    return content or "", meta, "empty"


def run_playwright_validate(html: str) -> dict:
    """Validate rendered page with Playwright via local HTTP server."""
    import http.server, threading, socketserver, os
    import tempfile

    result = {"svgCount": 0, "errCount": 1}
    with tempfile.TemporaryDirectory() as tmpdir:
        html_path = Path(tmpdir) / "index.html"
        html_path.write_text(html, encoding="utf-8")

        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        httpd = None
        try:
            handler = http.server.SimpleHTTPRequestHandler
            httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
            port = httpd.server_address[1]
            t = threading.Thread(target=httpd.serve_forever, daemon=True)
            t.start()
            try:
                js = f"""
const {{ chromium }} = require('playwright');
(async () => {{
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('http://127.0.0.1:{port}/index.html', {{ waitUntil: 'networkidle', timeout: 30000 }});
  await page.waitForTimeout(5000);
  const svgCount = await page.locator('svg').count();
  const errCount = await page.locator('text:has-text("Syntax error")').count();
  console.log(JSON.stringify({{svgCount, errCount}}));
  await browser.close();
}})();
"""
                proc = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=60,
                                      env={**os.environ, "NODE_PATH": "/home/eaguiar2015/findtorontoevents_antigravity.ca/node_modules"})
                try:
                    result = json.loads(proc.stdout.strip())
                except json.JSONDecodeError:
                    result = {"svgCount": 0, "errCount": 1, "stderr": proc.stderr[:200]}
            finally:
                httpd.shutdown()
        finally:
            os.chdir(old_cwd)
    return result


def evaluate_model(model_alias: str, tier: str) -> dict:
    result = {
        "model": model_alias,
        "tier": tier,
        "solved": False,
        "attempts": 0,
        "context_chars": 0,
        "cost_est": 0.0,
        "fix_mmd": "",
        "content_source": "",
        "errors": [],
        "playwright": {"svgCount": 0, "errCount": 1},
        "pushed": False,
        "branch": model_branch(model_alias),
    }

    print(f"\n{'='*60}")
    print(f"EVALUATING: {model_alias} ({tier})")
    print(f"{'='*60}")

    ensure_branch(result["branch"])

    broken_block = BROKEN_MMD
    last_err = "no attempts made"

    for attempt in range(1, 4):
        result["attempts"] = attempt
        print(f"  Attempt {attempt}/3...")

        query = (f"This mermaid@10.9.1 diagram is broken. Diagnose the error and "
                 f"output the complete corrected diagram.\n\n"
                 f"Broken block:\n```mermaid\n{broken_block}\n```\n\n"
                 f"RULE: Quote labels containing parens () or pipe | : E[\"label\"]\n"
                 f"RULE: Diagram type on line 1, nothing before it.\n"
                 f"RULE: At least 2 nodes, 1 edge.\n"
                 f"RULE: Output ONLY a fenced mermaid code block.\n\n"
                 f"Example:\n```mermaid\nflowchart TD\n    E[\"Synchronous REST<br/>RESTMessageV2.execute()\"] --> D{{OK?}}\n    D -->|No| F[Retry]\n```")

        # Try preferred alias first, then fall back to best available
        alias_to_try = model_alias
        try:
            content, meta, source = call_model(alias_to_try, query, max_tokens=1200)
        except Exception as e:
            # Try fallback model (use its resolved endpoint, not the proxy)
            best = resolve_best_model(tier=tier)
            if best and best["alias"] != model_alias:
                print(f"    Preferred alias {model_alias} failed ({e}), trying {best['alias']}")
                try:
                    content, meta, source = call_model(
                        best["alias"], query, max_tokens=1200,
                        base_url=best.get("base_url"),
                    )
                    result["model_used"] = best["alias"]
                except Exception as e2:
                    result["errors"].append(f"call error: {e2}")
                    print(f"    call error: {e2}")
                    continue
            else:
                result["errors"].append(f"call error: {e}")
                print(f"    call error: {e}")
                continue

        result["context_chars"] = len(query) + len(content)
        result["content_source"] = source
        toks = int(meta.get("tokens_out", 0)) + int(meta.get("tokens_in", 0))
        result["cost_est"] += toks * 0.000002

        candidate = extract_mmd_from_text(content)
        if not candidate:
            err = "no mermaid block found in response"
            result["errors"].append(f"attempt {attempt}: {err}")
            print(f"    FAIL: {err} (content source: {source})")
            print(f"    Raw content preview: {content[:200]!r}")
            last_err = err
            broken_block = f"{broken_block}\n\nPREVIOUS ATTEMPT FAILED: {err}\nFix this."
            continue

        vr = validate_mmd(candidate)
        if not vr.get("ok", False):
            err = f"invalid fix: {vr.get('err','')[:120]}"
            result["errors"].append(f"attempt {attempt}: {err}")
            print(f"    FAIL: {err}")
            last_err = err
            broken_block = f"{broken_block}\n\nPREVIOUS FIX FAILED: {err}\nFix this."
            continue

        result["solved"] = True
        result["fix_mmd"] = candidate
        print(f"    SOLVED! ({len(candidate)}b) from {source}")
        break

    if not result["solved"]:
        print(f"  UNSOLVED after {result['attempts']} attempts. Last error: {last_err}")
        return result

    # Apply fix to HTML
    fixed_html = re.sub(
        r'(<div class="mermaid">\s*)(.*?)(\s*</div>)',
        lambda m: m.group(1) + result["fix_mmd"] + m.group(3),
        FIXED_HTML, count=1, flags=re.S,
    )

    # Playwright validation
    print("  Running Playwright validation...")
    pw = run_playwright_validate(fixed_html)
    result["playwright"] = pw
    print(f"    Playwright: svgCount={pw.get('svgCount')} errCount={pw.get('errCount')}")

    # Push to model's branch
    try:
        push_file_to_branch(result["branch"], "case-a-unquoted-parens.html", fixed_html,
                            f"Swarm auto-fix case-a by {model_alias}\n\nDiagnosed and fixed by {model_alias} ({tier}).")
        result["pushed"] = True
        print(f"  Pushed to branch {result['branch']}")
    except Exception as e:
        result["errors"].append(f"push error: {e}")
        print(f"    Push error: {e}")

    return result


def main():
    results = []
    for model_alias, tier in MODELS:
        try:
            r = evaluate_model(model_alias, tier)
            results.append(r)
        except Exception as e:
            print(f"\n{'='*60}")
            print(f"EVALUATING: {model_alias} ({tier}) — CRASHED: {e}")
            print(f"{'='*60}")
            results.append({
                "model": model_alias, "tier": tier,
                "solved": False, "attempts": 0, "errors": [f"crash: {e}"],
                "context_chars": 0, "cost_est": 0.0, "fix_mmd": "",
                "content_source": "",
                "playwright": {"svgCount": 0, "errCount": 1},
                "pushed": False, "branch": model_branch(model_alias),
            })

    # Summary
    print("\n" + "="*75)
    print("MERMAID FIX EVALUATION SUMMARY")
    print("="*75)
    solved = [r for r in results if r["solved"]]
    print(f"Total models tested: {len(results)}")
    print(f"Solved: {len(solved)}/{len(results)}")
    print(f"\n{'Model':<28} {'Tier':<6} {'Solved':<7} {'Attempts':<9} {'CtxChars':<10} {'Source':<16} {'SVG':<5} {'Err':<5} {'Pushed':<7}")
    print("-" * 75)
    for r in results:
        print(f"{r['model']:<28} {r['tier']:<6} {str(r['solved']):<7} {r['attempts']:<9} "
              f"{r['context_chars']:<10} {r['content_source']:<16} "
              f"{r['playwright']['svgCount']:<5} {r['playwright']['errCount']:<5} "
              f"{str(r['pushed']):<7}")

    if solved:
        print("\n--- SOLVED MODELS ---")
        for r in solved:
            print(f"  ✓ {r['model']} ({r['tier']}) — {r['attempts']} attempt(s), "
                  f"{r['context_chars']} ctx chars, source={r['content_source']}, "
                  f"svg={r['playwright']['svgCount']}, cost=${r['cost_est']:.4f}")

    unsolved = [r for r in results if not r["solved"]]
    if unsolved:
        print("\n--- UNSOLVED MODELS ---")
        for r in unsolved:
            err = r["errors"][-1] if r["errors"] else "unknown"
            print(f"  ✗ {r['model']} ({r['tier']}) — {err[:80]}")

    out_path = Path("/tmp/mermaid_eval_results.json")
    out_path.write_text(json.dumps({"timestamp": time.time(), "total": len(results),
                                     "solved": len(solved), "results": results}, indent=2))
    print(f"\nResults saved to {out_path}")

    return results


if __name__ == "__main__":
    main()
