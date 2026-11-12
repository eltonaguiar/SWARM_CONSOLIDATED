# FREEBUFF_SWARM_2026-11-12

**Agent:** Freebuff (Buffy) — CLI agent
**Project of record:** `findtorontoevents_antigravity.ca` (branch `job-search-2026-11-03-ledger`)
**Peer plan:** `OLLAMA_CLAUDE_2026-11-12.md` (Ollama/Claude agent)
**Status:** active — P0.1 done (secret gone), P1 PR open, P2–P4 open

---

## 1. Mission — what I own

Retire the **Inception Labs Mercury API** (vendor sunset **2026-12-28**) from every
`github.com/eltonaguiar` surface without breaking a dispatch path, and prove the
shared LiteLLM proxy still serves after the removal.

**Scope boundary vs the peer plan.** I do **not** own proxy architecture, the
"Core vs Domain" split, or the extraction roadmap — those belong to
`OLLAMA_CLAUDE_2026-11-12.md`. My single overlap with it is `localhost:4000`: I
remove the Mercury provider from the provider registry / pin list and restart the
unit through systemd. I change nothing about how the proxy is composed, supervised
or operated. If that agent needs a provider-level change, it goes through me; I will
not restructure the proxy to achieve my goal.

## 2. Territory — files I have touched (do not edit concurrently)

If you are also working in these paths, coordinate here first.

- **Proxy:** `tools/litellm_dynamic_models.py`, `tools/start_litellm_proxy.sh`, `litellm_config.yaml`
- **swarm v1:** `tools/swarm/{api_consult,swarm_run,worker_runner,swarm_followup,invent_personas,safety,ENGINE_KEY_ENVS}.py`
- **swarm v2:** `tools/swarm_v2/swarms/core/llm_client.py`
- **ruflo:** `.ruflo/orchestrator.py`, `.ruflo/wizard.py`
- **consult tooling:** `tools/{idea_harvest_mega,ai_consult_orchestrator,local_swarm_review,model_picks_research,model_capability_probe,free_provider_audit,free_model_discovery,verify_all_keys,api_model_roster,_graphify_docs_multibackend}.py`
- **skills:** `.claude/skills/second-opinion/{SKILL.md,scripts/ask.py}`, `.claude/skills/graphify-map/SKILL.md`
- **CI / config:** `.github/workflows/{research-orchestrator,ai-tournament-pipeline}.yml`, `.env.example`, `tools/swarm/{README,SPEC,PORTING}.md`, `tools/swarm/swarm.config.example.json`, `config/api_model_roster.json`
- **docs:** `config/model_persona_mapping.json` (read-only unless P2 is approved)

Everything else in the repo is untouched by me.

## 3. Done — verified locally, **not committed**

- 34 files edited. Provider **removed outright**, not aliased to a second name, so no
  group has two aliases to one dead backend and no list still names a removed provider.
- Replacements: `cerebras / gpt-oss-120b` for the second-opinion peer; `groq` for the
  ruflo `reviewer` role (keeps role diversity: researcher=cerebras, coder=deepseek).
- **Proxy restarted and verified** 2026-11-12 17:54 UTC: readiness 200 after 40s,
  PID 525411, `NRestarts=0`, single listener on `:4000`, **242 deployments / 36 groups,
  zero mercury/inception groups**.
- Discovery `PIN_SPECS` = 8 pins, no MERCURY; `_PIN_SOURCES` = cerebras, deepseek, kilo,
  moonshot, opencode, together, xai (inception absent). Served
  `litellm_config.runtime.yaml` has 0 mercury refs and shares the post-restart mtime.
- Verification run: `py_compile` × 22, `bash -n` × 1, YAML/JSON parse, provider-list
  import smoke, repo-wide reference sweep. All pass.
- Write-up: `updates/2026-11-12-inception-mercury-api-sunset-migration.md`.

## 4. Queue

**P0 — kill the credential (in flight)**
1. ~~Delete GitHub secret `INCEPTION_API_KEY`~~ — **DONE 2026-11-12**: the secret is
   absent from `eltonaguiar/TORONTOEVENTS_ANTIGRAVITY` (verified with `gh secret list`
   and `/actions/secrets`). It disappeared before my delete call, which returned 404.
2. `~/dbpasses.txt` line 293 (`INCEPTION_AI_KEY`) + the value exported in the shell.
3. `eltonaguiar/hermesbackup` → `auth.json` still holds the key under
   `"custom:api.inceptionlabs.ai"` (+ `config.yaml` `base_url`). This is **real
   credential material** — revoke at the dashboard before deleting copies.

**P1 — `eltonaguiar/FREELLM`: PR OPEN, awaiting merge.** Branch
`inception-sunset-2026-11-12`, **PR #1** (6 files, MERGEABLE/CLEAN). Was present:
`PinSpec("PAID-MERCURY", "inception", count=1)` in `tools/litellm_dynamic_models.py`,
the `parse_key "INCEPTION_AI_KEY"` line in `tools/start_litellm_proxy.sh`,
`P("inception", "https://api.inceptionlabs.ai/v1", [...])` in `tools/free_provider_audit.py`,
plus `verify_all_keys.py`, `README.md`, `litellm_config.yaml`. Each file re-read from the
branch shows **0** remaining references; patched files pass `py_compile` / `bash -n`.
**Not merged** — left for the owner to review.

**P2 — `mercury` tournament persona.** `config/model_persona_mapping.json` routes
`inception/mercury-2` via `api.together.xyz` + `TOGETHER_API_KEY` — never the Inception
API. **Blocking evidence:** Together returned `401 Unauthorized` on every discovery
probe today, so the persona is probably already dead. Recommendation: repoint to
`cerebras/gpt-oss-120b` rather than wait for December. **Needs owner sign-off** (it has
tournament history attached).

**P3** — `audit_dashboard/inception_paper_trading.html` publishes `mercury-3` as the
underlying model id. Stale on 2026-12-28; needs a provenance rewording, not a code fix.

**P4** — `.env.example` is staged-for-deletion in the git index (pre-existing, not mine).
My cleanup exists on disk only and would be skipped by a commit until `git add`.

## 5. Coordination protocol I will follow

- Poll this repo (`gh api repos/eltonaguiar/SWARM_CONSOLIDATED/contents/`) at the start
  of every work block and after every merge; read new `*_<DATE>.md` plans before editing.
- I never edit another agent's plan file. I append status only to my own.
- I record every restart of the shared proxy here with UTC time + PID, because a
  concurrent proxy restart is the documented cause of random-port ghosts on this host.
- I do not touch `docker-compose*`, proxy supervision units, or the extraction/Core-Domain
  work — that is the peer agent's territory.

## 6. Open decisions for the owner

1. Repoint or retire the `mercury` tournament persona? (P2)
2. Commit the 34-file migration on a branch scoped to just those paths + the write-up?
   The tree has thousands of unrelated uncommitted changes from other sessions, so an
   unscoped commit is not safe.
3. Reword or remove the `inception_paper_trading.html` provenance claim? (P3)

## 7. Reproduce my verification

```bash
# proxy health + what it actually serves
curl -s localhost:4000/health/readiness
curl -s localhost:4000/model/info | python3 -c 'import json,sys; d=json.load(sys.stdin); i=d.get("data",d); print(len(i),"deployments")'
# pin list (authoritative, no network)
python3 -c "import sys; sys.path.insert(0,'tools'); import litellm_dynamic_models as m; print(m.PIN_SPECS)"
# sweep for live references
rg -n -i 'inceptionlabs|INCEPTION_AI_KEY|INCEPTION_API_KEY|"inception"' tools/ .ruflo/ .claude/ .github/ config/
```

---

## 8. Review of the peer plan (`OLLAMA_CLAUDE_2026-11-12.md`)

**Verdict:** directionally sound — one owner of orchestration logic, domain logic staying
in project repos — but it carries four collisions with work in flight and one technically
wrong assumption about how the proxy actually starts.

1. **"Proxy Management: `litellm_config.yaml` and proxy start scripts" cannot be a
   copy-into-core item.** On this host the proxy is a systemd user service
   (`litellm-4000.service`) whose `ExecStart` is an absolute path, and the file it
   actually serves is `litellm_config.runtime.yaml`, *generated at start* by
   `tools/litellm_dynamic_models.py`. Moving `litellm_config.yaml` into
   `SWARM_CONSOLIDATED` without moving the generator and rewriting the unit path leaves
   the service pointing at a file that does not exist there — a **hard startup failure**,
   not degraded routing. If the proxy config moves it must be one transaction: config +
   generator + unit path + a restart verified through `/health/readiness`.
2. **Extraction sequencing vs this migration — the real hazard.** Phase 1 harvests
   `api_consult.py` and `worker_runner.py` from `antigravity.ca` into the core library.
   Both files **contained the `inception` provider entry that I have removed locally but
   not yet committed**. Harvesting before my migration lands copies a dead vendor into the
   new "single source of truth", where it is far harder to find later. Ask: harvest from
   the post-migration state, or filter `inception`/`mercury` during extraction.
3. **`.ruflo/orchestrator.py` is a shared edit target.** Phase 3 rewrites `HERMES_BIN`
   there; I have already changed that same file's provider set and `reviewer` engine.
   Whoever edits second silently drops the other's change unless the diff is rebased —
   this file needs a single owner.
4. **"Standardize on `~/dbpasses.txt`" collides with P0.2.** I am deleting the
   `INCEPTION_AI_KEY` entry (line 293). Any loader written afterwards must not assume that
   key exists, and missing-key behaviour should be exercised rather than assumed.
5. **Gap: the peer plan never mentions the Mercury sunset.** Every provider list it
   proposes to consolidate currently carries a dead vendor. Extraction is the cheapest
   moment to drop it; after consolidation the same string is scattered across a new repo.

**Not contested:** the Core-vs-Domain split, personas/tasks staying project-side, the
single CLI entry point, and `requirements.txt` hygiene. Those are the peer's call and my
work does not depend on them.

**Compatibility statement:** my patch is safe to extract *after* it merges — it only
deletes entries and rewrites one docstring, so any extraction that copies files verbatim
yields a core library with no Mercury reference in it.

## 9. Deployable swarm on other PCs — portability + non-conflict contract

This section exists because the swarm is useless if it only runs here. It defines what
"deployable" means, and the rules that keep it from colliding with the deployable LiteLLM
repo and with `http://localhost:4000/v1`.

### 9.1 The endpoint is a contract, not a dependency to copy

`http://localhost:4000/v1` is the only LLM URL any swarm component may know. Clients and
workers send an OpenAI-shaped request with a **placeholder** `api_key` (real auth happens
upstream) and a **model alias**, never a provider URL or a provider-specific model id.

- `hybrid-model present in served aliases: **no** (measured 2026-11-12T18:08Z)`. Do not document an alias to another machine without re-checking
  `GET /v1/models` on that machine; the alias set changes as free pools move.
- Alias names are the stable surface. `ULTRA_*` groups and their fallback chains live in the
  proxy config; a swarm that hardcodes `groq/llama-3.1-8b` has bypassed rotation and will rot.

### 9.2 Ownership: one proxy source, three consumers

| Artefact | Owner (single source) | Everyone else |
|---|---|---|
| `litellm_config.yaml`, `start_litellm_proxy.sh`, `litellm_dynamic_models.py` | the deployable LiteLLM repo (`eltonaguiar/FREELLM`) | **read-only consumers** — never vendor a copy |
| `~/.config/systemd/user/litellm-4000.service` | each machine, never in git | unit is per-host: `WorkingDirectory` is an absolute path and must be rewritten per PC |
| swarm engine code | `SWARM_CONSOLIDATED` | projects import it, do not fork it |
| persona/prompt/domain content | each project repo | core lib stays generic |

**This is why the peer plan's "move `litellm_config.yaml` into SWARM_CONSOLIDATED" is
wrong**: there would then be a *third* copy (FREELLM already holds one, antigravity holds
one). Two copies already drift — a config comment in antigravity still says the provider
set was verified 2026-05-25. Correct shape: `SWARM_CONSOLIDATED` pins a **commit sha** of
FREELLM and documents the contract; it does not carry the file.

### 9.3 Precedence rule when a swarm worker needs a model

1. **Local proxy `:4000`** — default. Rotation, cooldown and 429 handling happen once, in
   one place, for every agent on the box.
2. **Direct env key** — only for a provider the proxy does not front, or for a probe.
3. **CLI engine** (`claude`, `gemini`, `kilo`, `opencode`, `ollama`) — when the answer needs
   tool use / file access rather than a chat completion.

Never let (2) and (1) hold the same provider key by default: that turns one quota into two
independently-throttled consumers and makes "why am I rate-limited" unanswerable.

### 9.4 Portability contract (what already holds, what must hold)

Measured 2026-11-12 against the real deploy surface:

- **Zero** `/home/<user>` hardcodes in `start_litellm_proxy.sh`, `litellm_dynamic_models.py`,
  `litellm_config.yaml`, `.env.example`, `tools/swarm/*.py`. Paths derive from repo root.
- The **only** absolute path is the systemd unit's `WorkingDirectory` — per-machine by
  design, so a new PC writes its own unit rather than inheriting one.
- The launcher is **fully env-overridable**: `PORT` (default 4000), `CONFIG`, `KEYS_FILE`
  (default `$HOME/dbpasses.txt`), `PROXY_LOG`, `DYNAMIC_LOG`, `LITELLM_DYNAMIC_MODELS`,
  `LITELLM_DYNAMIC_PROVIDERS`, `LITELLM_START_LOCK`, `VERIFY_BOUND_PORT`,
  `VERIFY_BOUND_PORT_TIMEOUT`, `WARM_LOCAL_FAST`, `ALLOW_PAID_SPILLOVER`. No flag is
  required to run it on a second machine.
- Keys resolve in this order: **process env → repo-root `.env`** (`config_loader.load_dotenv`,
  supports `${VAR}` substitution) **→ `~/dbpasses.txt`** (launcher only). A new PC therefore
  needs only a `.env`; the dbpasses file is a local convenience, not a requirement.
- `systemd` is a **convenience supervisor, not a dependency**: `--background` and foreground
  both work. Do not let the plan assume systemd exists on Windows/macOS.
- The generated `litellm_config.runtime.yaml` must stay **per-checkout and gitignored**.
  It is written into the repo root on purpose (LiteLLM resolves `callbacks:` relative to the
  config's directory, so a `/tmp` config breaks the import and the proxy exits), which means
  two PCs sharing a synced checkout will thrash that file.

**Known gaps that block a clean second-PC deploy** (from `tools/swarm/PORTING.md`, still open):

- `port_in_use()` shells out to `ss` — Linux only. Needs a Python `socket.connect_ex` fallback
  so the "port bound but unhealthy → refuse to start" guard works on macOS/Windows.
- `flock` serialization is `command -v`-guarded: on a machine **without** flock the guard is
  silently skipped, restoring the exact double-start race that produced random-port ghosts.
  Needs a lockfile + stale-pid fallback.
- Logs default to `/tmp/*` — fine on POSIX, wrong on Windows. Drive them from `PROXY_LOG`/
  `DYNAMIC_LOG`/`RESTART_HISTORY` in the deploy doc instead of assuming `/tmp`.
- The PR pipeline (`swarm_dispatch.ps1`, `comment_poster.ps1`) is PowerShell-only; the bash
  port is unwritten. Python drivers are already cross-platform.
- `swarm_runs/` and the sqlite session sidecar are per-checkout (path derived from
  `Path(__file__).resolve().parents[N]`); do not sync them between machines.

### 9.5 Multi-PC topology — how machines cooperate without fighting

- **Every PC runs its own proxy on its own `:4000`.** Loopback only. No machine starts a
  proxy on behalf of another, and no proxy is exposed on the LAN — that would put one key
  pool and one cooldown table in the path of several machines and make failures
  unattributable.
- **Cross-machine fan-out goes over the existing cross-PC gateway skills**
  (`cross-pc-sendmsg`, `cross-pc-checkmsg`, `cross-pc-health`), not by sharing a proxy port.
  The swarm must degrade gracefully when the gateway is absent: it is an optional transport.
- **One start per host.** The launcher's lock is per-port, so two agents on the *same* PC
  serialize correctly; two PCs cannot collide by construction.
- **Restart discipline** (learned the hard way today): a proxy restart is a 40s+ outage while
  discovery runs. Any agent restarting `:4000` announces it in `SWARM_CONSOLIDATED` with UTC
  time + PID first, because a concurrent restart is the documented cause of ghost instances.

### 9.6 Deploy checklist — new PC in ~10 minutes

```bash
# 1. clone the deployable LiteLLM repo (the single source for proxy files)
git clone <FREELLM> && cd FREELLM
python3 -m venv .venv && .venv/bin/python -m pip install 'litellm[proxy]'
# 2. keys: repo-root .env is enough; dbpasses.txt is optional
cp .env.example .env && $EDITOR .env        # fill only the providers you have
# 3. start (no systemd required)
PORT=4000 bash tools/start_litellm_proxy.sh --background
# 4. verify by contract, not by vibes
curl -s localhost:4000/health/readiness                      # 200
curl -s localhost:4000/v1/models | grep -c '"id"'            # alias count
# 5. only then point the swarm at it
export OPENAI_BASE_URL=http://localhost:4000/v1
python tools/swarm/config_loader.py                          # shows which key each engine resolved
python tools/swarm/swarm_run.py --prompt-file probe.md --engines deepseek,cerebras
```

Acceptance for "works on another PC": step 4 returns 200 **and** a real completion returns
non-empty content, **and** `config_loader.py` reports no missing keys for the engines used.
A 200 readiness alone is not acceptance — readiness only proves the router booted.

### 9.7 What my Mercury patch changes for deployability: nothing

The patch deletes provider entries and rewrites one docstring. It does not touch the port,
the alias names, the fallback chains, the key-resolution order, or any client-facing name.
A second PC deployed from the post-merge state behaves identically to one deployed today —
except that it never probes a vendor that will not exist after 2026-12-28.

## 10. Status log (append-only)

### 2026-11-12 18:04 UTC (commit 69ba04ac)
- **P0.1 DONE — GitHub secret is gone.** `eltonaguiar/TORONTOEVENTS_ANTIGRAVITY` lists 25 secrets,
  **zero** matching inception/mercury, and `GET /actions/secrets` confirms. Note: my `gh secret
  delete` returned **404 because the secret was already absent** — either the owner or the peer
  agent removed it first. I did not remove it; it is simply gone.
- **P1 IN FLIGHT — `eltonaguiar/FREELLM` PR #1** (`inception-sunset-2026-11-12`), 6 files,
  each re-read from the branch and showing **0** remaining inception/mercury references:
  `tools/litellm_dynamic_models.py` (PinSpec, `_PIN_SOURCES`, `_pin_rank` tuple + docstring, pin
  comment), `tools/start_litellm_proxy.sh` (`parse_key` + export), `tools/free_provider_audit.py`,
  `tools/verify_all_keys.py` (key pair, `t_inception`, registry row), `litellm_config.yaml`,
  `README.md`. All patched files pass `py_compile` / `bash -n`.
- **NEW RISK — `hermesbackup` holds the key in plaintext.** Repo is **private**, so this is not a
  public leak, but `config.yaml` carries the Inception key on a `base_url: https://api.inceptionlabs.ai/v1`
  block, and `auth.json` → `credential_pool["custom:api.inceptionlabs.ai"][0].access_token`
  (35-char `sk_` token, `last_error_code: 429`). Scrubbing the file will **not** un-leak it —
  git history keeps it — so revocation at the dashboard must come first.

### Still open
`~/dbpasses.txt` line 293 · hermesbackup scrub · P2 mercury persona (Together 401s) ·
P3 `inception_paper_trading.html` provenance · P4 `.env.example` index state ·
uncommitted 34-file local migration.

### 2026-11-12 18:06 UTC (commit 90219166) — peer review pass
- Read `OLLAMA_CLAUDE_2026-11-12.md` end to end; added §8. One assumption is technically
  wrong (`litellm_config.yaml` cannot move alone — the served file is generated and the
  unit path is absolute) and one is a live sequencing hazard (harvesting
  `api_consult.py` / `worker_runner.py` before my migration lands copies the dead provider
  into the core library).
- Repo state: `main` is the only branch; no new peer files since commit `86726334`.
- Corrected my own P0/P1 status above rather than only appending: P0.1 is done, P1 is a
  PR awaiting merge. Leaving stale "in flight" text in a coordination doc is how two
  agents end up doing the same work twice.
- `hermesbackup` detail for the record: the plaintext key sits on `config.yaml` line 435
  in the `base_url: https://api.inceptionlabs.ai/v1` block, and the same value appears in
  `auth.json` → `credential_pool["custom:api.inceptionlabs.ai"][0].access_token`.
  Revocation still has to come first; git history keeps both copies.

### Still open (post-review, 18:06 UTC)
`~/dbpasses.txt` line 293 · `hermesbackup` revoke-then-scrub · P2 `mercury` persona
(Together 401s) · P3 `inception_paper_trading.html` provenance · P4 `.env.example` index
state · **34-file local migration still uncommitted** · FREELLM PR #1 awaiting owner merge.

### 2026-11-12 18:2x UTC — portability / non-conflict section added (§9)
- Added §9: endpoint-as-contract, proxy ownership (FREELLM is the single source), the
  1→2→3 precedence rule for model access, the measured portability contract (zero `/home/...`
  hardcodes; only the systemd `WorkingDirectory` is absolute; fully env-overridable launcher),
  the four known gaps that block a clean second-PC deploy (`ss`, unguarded `flock`, `/tmp`
  logs, PowerShell-only PR pipeline), multi-PC topology, and a 10-minute deploy checklist.
- **Consequence for the peer plan:** moving `litellm_config.yaml` into `SWARM_CONSOLIDATED`
  would create a *third* copy of a file FREELLM already owns. §9.2 proposes the correct shape
  instead — pin a FREELLM commit sha and document the contract, do not carry the file.
- Measured, not assumed: alias set re-read live from `GET /v1/models` at publish time rather
  than trusting the `hybrid-model` name in `.claude/skills/litellm-proxy/SKILL.md`.
