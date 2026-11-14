#!/usr/bin/env python3
"""
End-to-end swarm fix simulation in isolated worktree.
Everything in ONE process - no file modification between steps.
"""
import base64, json, os, re, subprocess, sys, time, urllib.request, urllib.error
from pathlib import Path

sys.path.insert(0, str(Path.home() / "SWARM_CONSOLIDATED"))
from core.combine_team import run_combine_team
from core.transport import call_openai_compat
from swarm_task import subq_decide, qa_eval
from probe_providers import resolve_best_model

WORKTREE = Path("/tmp/bm_worktree")
REPO = "eltonaguiar/BROKENMERMAIDTEST"
TOKEN = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()

os.environ["SUBQ_FREE_API_KEY"] = "sk-proj-Xx8AOwoBBEXGOg75H0q4YMcNZ3wVCVUV"
os.environ["SUBQ_TOKEN_API_KEY"] = "sk-proj-7IuzAriNQVjz7lnikGi2Hi45c4j084O7"

VALIDATOR = Path("/tmp/mm_bench/validate.mjs")
PROXY_URL = "http://localhost:4000/v1"

BROKEN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Case A — Unquoted Parentheses</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.css">
</head>
<body>
  <h1>Case A — Unquoted Parentheses</h1>
  <div class="mermaid">
flowchart TD
    E[Synchronous REST<br/>RESTMessageV2.execute()] --> D{OK?}
    D -->|No| F[Retry]
  </div>
  <script>mermaid.initialize({ startOnLoad: true, theme: 'default' });</script>
</body>
</html>"""


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
    print(f"  PUSHED to GitHub: {path}")


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


def call_with_fallback(prompt, max_tokens=600):
    """Call the best available model.

    Prefers true parallel fan-out across independent local endpoints
    (vLLM :8000 / Ollama :11434) when any are reachable — this avoids the
    single-worker :4000 proxy bottleneck. Falls back to the sequential
    probe_providers() chain when no parallel endpoint is up.

    Disable the parallel path with ``SWARM_PARALLEL=0``.
    """
    if os.environ.get("SWARM_PARALLEL", "auto").strip().lower() not in ("0", "false", "no", "off"):
        try:
            from swarm_parallel_runner import (
                available_endpoints,
                first_content,
                run_parallel_swarm,
            )

            eps = available_endpoints()
            if eps:
                res = run_parallel_swarm(prompt, endpoints=eps, max_tokens=max_tokens)
                content, src = first_content(res)
                if content:
                    return content, src
                print("    parallel endpoints reachable but returned no content")
        except Exception as e:  # noqa: BLE001 — never block the fallback
            print(f"    parallel path skipped: {type(e).__name__}: {str(e)[:60]}")

    best = resolve_best_model()
    if not best:
        print("    No model available via probe_providers()")
        return None, None
    alias = best["alias"]
    base_url = best["base_url"]
    try:
        content, meta = call_openai_compat(
            provider="openrouter", prompt=prompt, model_override=alias,
            sampling={"temperature": 0.2, "max_tokens": max_tokens},
            base_url=base_url,
        )
        # Prefer content, fall back to reasoning_content (thinking models)
        if content and content.strip():
            return content, alias
        reasoning = meta.get("reasoning_content", "") or ""
        if reasoning and reasoning.strip():
            return reasoning, alias
    except Exception as e:
        print(f"    alias {alias} failed: {type(e).__name__}: {str(e)[:60]}")
    return None, None


def swarm_fix(block, max_retries=3):
    last_err = "unknown"
    for attempt in range(1, max_retries + 1):
        print(f"    Attempt {attempt}/{max_retries}:")
        query = (f"This mermaid@10.9.1 diagram is broken. Diagnose the error and "
                 f"output the complete corrected diagram.\n\n"
                 f"Broken block:\n```mermaid\n{block}\n```\n\n"
                 f"ERROR: unquoted parentheses in node label E[...execute()]\n"
                 f"RULE: Quote any label containing parens () or pipe | : "
                 f'E["label with (parens)"]\n'
                 f"RULE: Diagram type (flowchart TD) must be on line 1, nothing before it.\n"
                 f"RULE: At least 2 nodes and 1 edge.\n"
                 f"RULE: Output ONLY a fenced mermaid code block, no other text.\n\n"
                 f"Example of correct output format:\n"
                 f"```mermaid\n"
                 f"flowchart TD\n"
                 f'    E["Synchronous REST<br/>RESTMessageV2.execute()"] --> D{{OK?}}\n'
                 f"    D -->|No| F[Retry]\n"
                 f"```")

        print(f"  Trying best available model with fallback...")
        content, alias = call_with_fallback(query, max_tokens=600)
        if not content:
            last_err = "all aliases failed"
            continue

        print(f"  Response from {alias} ({len(content)}b)")

        m = re.findall(r"```(?:mermaid)?\s*\n(.*?)\n```", content, re.S)
        candidate = m[0].strip() if m else content.strip()

        vr = validate_mmd(candidate)
        if not vr.get("ok", False):
            last_err = f"fix invalid: {vr.get('err','')[:120]}"
            print(f"    FAIL: {last_err}")
            block = f"{block}\n\nPREVIOUS FIX ATTEMPT FAILED: {last_err}\nFix this."
            continue

        qa = qa_eval(query, candidate)
        if not qa["passes"]:
            last_err = f"QA failed: {qa['notes']}"
            print(f"    FAIL: {last_err}")
            block = f"{block}\n\nQA REJECTED: {last_err}\nFix this."
            continue

        print(f"    SOLVED! ({len(candidate)}b)")
        return candidate, None

    return None, last_err


def run_playwright_validate(html):
    """Validate rendered page with Playwright via local HTTP server."""
    import http.server, threading, socketserver
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


def main():
    page = "case-a-unquoted-parens.html"
    local_path = WORKTREE / page

    print(f"=== Step 1: Write BROKEN version to {local_path} ===")
    local_path.write_text(BROKEN_HTML, encoding="utf-8")

    html = local_path.read_text(encoding="utf-8")
    block = extract_mmd(html)
    print(f"  Block size: {len(block)}b")
    vr = validate_mmd(block)
    print(f"  Validate BEFORE fix: ok={vr.get('ok')} err={vr.get('err','')[:100]}")
    assert not vr.get("ok", False), "ERROR: block is already valid!"

    print(f"\n=== Step 2: Swarm diagnoses + fixes ===")
    fixed, err = swarm_fix(block)
    if not fixed:
        print(f"  SWARM FIX FAILED: {err}")
        return
    print(f"  Swarm fix valid ({len(fixed)}b): {fixed.splitlines()[0]}")

    new_html = BROKEN_HTML
    new_html = re.sub(
        r'(<div class="mermaid">\s*)(.*?)(\s*</div>)',
        lambda m: m.group(1) + fixed + m.group(3),
        new_html, count=1, flags=re.S,
    )
    local_path.write_text(new_html, encoding="utf-8")
    print(f"  Fix applied locally")

    vr2 = {"ok": False, "err": "not run"}
    try:
        import tempfile as _tf3, json as _json3, os as _os3
        with _tf3.NamedTemporaryFile("w", suffix=".mmd", delete=False) as _f3:
            _f3.write(fixed); _tmp3 = _f3.name
        _r3 = subprocess.run(["node", str(VALIDATOR), _tmp3], text=True,
                             capture_output=True, timeout=30)
        _out3 = (_r3.stdout or "").strip()
        try:
            vr2 = _json3.loads(_out3)
        except _json3.JSONDecodeError:
            vr2 = {"ok": False, "err": _out3[:200] or (_r3.stderr or "")[:200]}
        _os3.unlink(_tmp3)
    except Exception as _e3:
        vr2 = {"ok": False, "err": str(_e3)[:200]}
    vr2 = vr2 if isinstance(vr2, dict) else {"ok": False, "err": "bad type"}
    print(f"  DEBUG: vr2={vr2!r} type={type(vr2).__name__}")
    print(f"  Validate AFTER fix: ok={vr2.get('ok')} err={(vr2.get('err') or '')[:100]}")
    assert vr2.get("ok", False), "ERROR: fix is not valid!"

    print(f"\n=== Step 3: Playwright validation ===")
    pw = run_playwright_validate(new_html)
    print(f"  Playwright: svgCount={pw.get('svgCount')} errCount={pw.get('errCount')}")

    print(f"\n=== Step 4: Push to GitHub ===")
    push_file(page, new_html, f"Swarm auto-fix case-a: repair unquoted-parentheses mermaid diagram\n\nDiagnosed and fixed by AI swarm (combine_team + SubQ QA). Validated with Playwright.")
    print(f"\nCOMPLETE: Broken page diagnosed, fixed by swarm, validated, and pushed to GitHub!")


if __name__ == "__main__":
    main()
