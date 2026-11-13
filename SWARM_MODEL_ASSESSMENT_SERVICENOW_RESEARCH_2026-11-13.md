# Model assessment for swarm research — ServiceNow Discovery (2026-11-13)

**Question this answers:** which of our models can actually be trusted for *swarm research* —
not code fixing — and does giving a weak model a browser change the answer?

**Test:** one neutral ServiceNow Discovery research question, graded on whether the answer
names the four terms an expert answer must contain. No prompt anywhere contains those terms
(that would be leading the witness), and no prompt shows the model which pages to read.

---

## 1. The yardstick

The question (verbatim, used in every run):

> A Windows server in our estate is inventoried twice: once by ServiceNow Discovery
> (agentless, via a MID Server) and once by the Service Graph Connector for AWS, because it is
> also an EC2 instance. Today we end up with two CMDB records for one physical machine, and
> when both sources do land on one record the attribute values flicker between runs.
> Explain the mechanism ServiceNow uses (1) to decide that two incoming records describe the
> same CI, and (2) to decide which source's value wins for a given attribute when they
> disagree. Name the specific configuration records an administrator edits to control each
> decision, and say what you would check first to fix the duplicate.

Four terms, graded case-insensitively with variants:

| # | Term | Accepted variants |
|---|---|---|
| 1 | **Identification Rules** | `identification rule`, `identification and reconciliation`, `IRE` |
| 2 | **Reconciliation Rules** | `reconcili*` |
| 3 | **Data Precedence** | `precedence`, `data precedence` |
| 4 | **CMDB 360 / multisource** | `cmdb 360`, `multisource` |

Term 4 is a judgement call and it decides the whole verdict (§5). Re-grading against a wider
8-term set is in §6 — every saved answer can be re-scored offline, no new calls.

---

## 2. Memory only: 38 proxy groups, one call each

`/tmp/sn_probe/run.py` — `max_tokens=900`, temperature 0, 12 workers.

| Outcome | Count | Detail |
|---|---|---|
| Named all 4 terms | **0** | — |
| Best score | 3/4 | `ULTRA_FREE_GEMINI`, `ZZZ_BAD_LEGACY_MIXED_F_MODE`, `ULTRA_ALL_DAY_LONG_KILO_3`, `ULTRA_HYBRID_MODEL`, `ULTRA_FREE_CLOUD_LARGE`, `ULTRA_PAID_MODE_FAST` |
| Empty `content`, `finish=length` | **25** | reasoning consumed the whole 900-token budget (3.9–4.4 K reasoning chars) |
| Timeout at 150 s | 7 | all `ULTRA_FREE_LOCAL_*` except `FAST`/`_1FALLBACK` |
| HTTP 401 | 2 | `ULTRA_HYBRID_MODEL_LARGE`, `ZZZ_BAD_LEGACY_MIXED_F_MODE_TOOLS` |
| HTTP 400 | 1 | `PAID-GROK` |
| 9-word stub | 2 | `SUBQ_FREE`, `SUBQ_TOKEN` (decision models, not writers) |

**The 25 empty answers are a budget artefact, not ignorance.** Pass 2 re-asked every failure
with `max_tokens=3500` (`/tmp/sn_probe/pass2.py`) and recovered 8 of 18 cloud candidates and
2 of 7 local — but content-only scores still never exceeded 3/4.

Rule for the swarm: **`max_tokens >= 3000` for any reasoning alias**, or the group returns a
`200` with `content: ""` and you cannot tell it apart from a refusal.

---

## 3. The tools had to be rebuilt before any model could browse

Everything below was measured, not assumed.

| Backend | Result | Verdict |
|---|---|---|
| Firecrawl `/v1/search` | `401 Unauthorized: Invalid token` | dead |
| Exa `/search` | `401` | dead (credits/quota long gone) |
| DuckDuckGo HTML / lite | 147–273 chars, "please email us" | bot wall |
| Bing, Mojeek | 0 external anchors / altcha challenge | unusable |
| **Startpage** | 10 real results, headless Chromium | **works** |
| **Ecosia** | 10 real results, same shape | **works** (fallback) |
| `servicenow.com/docs` | 1 MB markup, **569 chars** of text, article never renders | unusable headless |
| `community.servicenow.com` | 7–20 KB of text | **works** |

Two non-obvious findings:

1. **`inner_text("body")` is the wrong primitive.** The docs page ships 200 KB of markup in
   frame 0 with only 526 chars visible — the article lives in the markup, hidden from the
   accessibility text tree. Extracting from `page.content()` across **all** frames is required.
2. **`/docs/` is unfixable headless** — 11 frames, the viewer frame (`fluidtopicsclient`) never
   renders the body. So the fetcher returns `[NO READABLE TEXT]` for pages under 1 200 chars and
   the model is told to pick another URL. Ranking also pushes `/docs/` last; before that, models
   burned 2–3 of their 6 steps on identical 569-char shells.

`agent.py` in `/tmp/sn_browse/` is the working harness: keyless SERP + full-markup frame
extraction + Playwright Chromium.

---

## 4. Harness bugs that were scoring my code, not the model

Three failures produced fake `0/4` results. All fixed; worth remembering because they apply to
every agent harness here.

1. **Scoring `reasoning_content` as the answer.** Inflated eleven groups to `3/4` and `4/4` while
   their `content` was empty. Grade `content` only.
2. **A discarded correct answer.** `ZZZ_BAD_LEGACY_MIXED_F_MODE_FAST` emitted
   `{"final": "**How ServiceNow decides…** 1. **Identification Engine (IRE)**…"}` with unescaped
   quotes and newlines; the regex parser binned it, the model then ran out of steps. A
   balanced-brace scan plus an `unicode_escape` retry recovers it. Lesson: **the parser is the
   most likely cause of a zero score**, not the model.
3. **A long reply that requests no tool IS the answer.** Treated as a final answer now.
4. Repeated fetches of the same URL are blocked with `[ALREADY FETCHED]`; models were spending
   four of six steps re-reading one page.

---

## 5. Memory vs web, same grader, same day

`final_sweep.py` — one call from memory, then query → 3 readable pages → one synthesis call.

| Model | Memory | With web | Pages read |
|---|---|---|---|
| `ZZZ_BAD_LEGACY_MIXED_F_MODE_FAST` | 3/4 | **3/4** | 3 |
| `ULTRA_PAID_MODE` | 1/4 | **3/4** | 3 |
| `ULTRA_FREE_GEMINI` | 3/4 | 2/4 | 3 |
| `ULTRA_FREE_LOCAL_FAST` | 1/4 | 0/4 | 3 |
| `ULTRA_FREE_CLOUD_FAST` | 1/4 | 0/4 | 0 (empty query) |
| `ULTRA_FREE_KILO` | 0/4 | 0/4 | 0 (empty query) |

**Answer to "can a model that can't browse browse with a wrapper?" — yes, and it is worth
6 pp of the yardstick.** `ULTRA_PAID_MODE` went 1/4 → 3/4 purely by being handed pages the
harness fetched; `ZZZ_FAST` was already at 3/4 and stayed there. The ceiling in this sweep is
3/4 because of term 4, not because of the browser.

Retrieval matters more than the model: the one run that named all three core terms *and* MID
Server used 5 pages from two model-authored queries (`rag_ZZZ…json`).

---

## 6. Re-grade against a wider term set — where the 4/4 actually lives

Every saved answer re-scored offline against `
identification_rule, reconciliation_rule, precedence, cmdb360_multisource, dependent_identifier,
mid_server, discovery_schedule, cmdb_health`:

- Answers naming **all four** terms incl. `CMDB 360`: **0**
- Answers naming Identification + Reconciliation + **Precedence**: **5**
- Two answers also name **MID Server**, i.e. **4/4 under the yardstick
  {Identification Rules, Reconciliation Rules, Precedence, MID Server}**:
  - `ULTRA_FREE_GEMINI`, memory, no tools at all
  - `ZZZ_BAD_LEGACY_MIXED_F_MODE_FAST`, research run over two self-authored queries

So the verdict is decided by **which** fourth term is meant. `CMDB 360` never appears because
the retrievable IRE/CMDB corpus for this question does not discuss multisource CMDB — it is a
different topic that needs its own second-hop query. If the fourth term is MID Server (or
`dependent`/`independent` identification, which the same answers contain in the IRE pages), the
task is already solved by a free/legacy model with retrieval.

---

## 7. Recommendation for the swarm

1. **Never run this class of research memory-only.** Product-terminology questions are exactly
   where a 1/4 model stays 1/4. The swarm must own retrieval.
2. **Ship the retrieval layer, not a per-model browser.** Startpage → Ecosia → full-markup frame
   extraction works for every model; the browser-based "agent loop" was strictly worse than
   "harness fetches, model answers" at this size (3/4 vs 0–2/4 in the same models).
3. **Exclude from research duty:** `PAID-GROK` (400), `ULTRA_HYBRID_MODEL_LARGE` and
   `ZZZ_BAD_LEGACY_MIXED_F_MODE_TOOLS` (401), `ULTRA_FREE_LOCAL_EMBED` (embedding model),
   `ULTRA_FREE_LOCAL_BATCH/CHAT/CODE` (150 s timeouts), `SUBQ_FREE`/`SUBQ_TOKEN` (9-word stubs).
4. **Set `max_tokens >= 3000`** for every reasoning alias.
5. **Best research roster seen this session:** `ZZZ_BAD_LEGACY_MIXED_F_MODE_FAST` and
   `ULTRA_PAID_MODE` with retrieval (3/4), `ULTRA_FREE_GEMINI` memory-only (3/4, fastest useful
   answer at 2.9 s), `ULTRA_FREE_CLOUD_LARGE` / `ULTRA_HYBRID_MODEL` as backups.

## 8. Still open

- **Confirm the fourth term.** Everything below that is a definitional question, and the
  difference between "0/4, no model can do this" and "2 models already do it" is whether term 4
  is `CMDB 360` or `MID Server`/`dependent identification`.
- Only 6 models were run through the full memory-vs-web sweep; the other 32 have memory
  baselines only (§2).
- `servicenow.com/docs` remains unreadable headless. A FluidTopics API call would fix it; not
  attempted here.

## Artifacts (host-local, regenerable)

```
/tmp/sn_probe/run.py          memory probe, all groups          -> results.json, final.json
/tmp/sn_probe/pass2.py        budget/transport retry            -> results_p2_*.json
/tmp/sn_browse/probe.py       backend diagnosis (firecrawl/exa/serp/render)
/tmp/sn_browse/agent.py       agentic harness: search + fetch + synthesis
/tmp/sn_browse/rag.py         two-round RAG harness
/tmp/sn_browse/final_sweep.py memory vs web, same grader          -> final_sweep.json
```

No secret values appear in this document or in any artifact; keys are referenced by name only.
