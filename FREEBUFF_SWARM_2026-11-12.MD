# FREEBUFF_SWARM_2026-11-12

**Agent:** Freebuff (Buffy) — CLI agent
**Project of record:** `findtorontoevents_antigravity.ca` (branch `job-search-2026-11-03-ledger`)
**Peer plan:** `OLLAMA_CLAUDE_2026-11-12.md` (Ollama/Claude agent)
**Status:** active — P0 in progress, P1 queued

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
1. Delete GitHub secret `INCEPTION_API_KEY` from
   `eltonaguiar/TORONTOEVENTS_ANTIGRAVITY` — *owner approved 2026-11-12*. No workflow
   references it any more, so removal is inert.
2. `~/dbpasses.txt` line 293 (`INCEPTION_AI_KEY`) + the value exported in the shell.
3. `eltonaguiar/hermesbackup` → `auth.json` still holds the key under
   `"custom:api.inceptionlabs.ai"` (+ `config.yaml` `base_url`). This is **real
   credential material** — revoke at the dashboard before deleting copies.

**P1 — `eltonaguiar/FREELLM` carries the same bug.** Confirmed still present:
`PinSpec("PAID-MERCURY", "inception", count=1)` in `tools/litellm_dynamic_models.py`,
the `parse_key "INCEPTION_AI_KEY"` line in `tools/start_litellm_proxy.sh`,
`P("inception", "https://api.inceptionlabs.ai/v1", [...])` in `tools/free_provider_audit.py`,
plus `verify_all_keys.py`, `README.md`, `litellm_config.yaml`. Same patch set applies.

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

## 8. Status log (append-only)

### 2026-11-12 18:05 UTC
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
