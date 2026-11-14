# KILO — Reusable Kilo Code Agents & Skills

Curated, reusable [Kilo Code](https://kilo.ai/docs) customizations. Install into your project's `.kilo/` directory (or `~/.kilo/` for global availability) and start a new session, or run `/reload`.

## Layout

- `agents/` — custom agent/mode files (`<name>.md` with YAML frontmatter). Copy into `.kilo/agents/`. The filename becomes the agent name.
- `skills/` — [Agent Skills](https://agentskills.io/home) (`<name>/SKILL.md`). Copy into `.kilo/skills/`.

## Contents

| Item | Type | What it does |
|------|------|--------------|
| `agents/decomposer.md` | Agent / mode (primary) | Full-capability (code-like) executor that decomposes multi-step work into a tracked todo list (`todowrite`) and delegates independent items to subagents (`task`) for parallelism, without stalling in a plan-only mode. |
| `skills/decompose-and-delegate/SKILL.md` | Skill | Same decompose-and-delegate behavior, packaged as an on-demand, framework-agnostic skill. |

## Notes

- Subagents share your project directory but run in their own session; they cannot ask the user questions.
- Background subagents require the experimental flag `KILO_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true`.
- The default subagent recursion depth is 1; keep nested dispatch to one level unless raised.

---

## New Features — TL;DR

Two complementary ways to get decompose-and-delegate behavior. Both exist so you can use the same workflow either as a default behavior or as an on-demand tool.

### The `decomposer` mode (agent) — pick it explicitly

- **What/why:** A full-capability mode like `code` that *also* builds a todo list and dispatches subagents for parallel work. It exists to get the benefits of structuring + parallelizing without being stuck in a read-only plan mode that waits for approval before anything happens.
- **When to use:** You have a multi-step task (several distinct steps or independent workstreams) and you want progress tracking + parallelism built in by default.
- **How:** Select it in the agent/mode picker (like Code/Plan) at the start of the task. It is not triggered automatically — you choose it.

### The `decompose-and-delegate` skill — auto-used, name-triggered, or slash command

- **What/why:** The same decompose-and-delegate behavior as a skill. Skills are **auto-used**: when a task matches the skill's `description`, the agent decides to load it itself — no command needed. So with the skill installed, your current agent (e.g. `code`) will usually self-trigger it on complex multi-step work.
- **How to force/control it:**
  - Explicit: just say "use the decompose-and-delegate skill".
  - Slash command: it also appears as `/decompose-and-delegate:skill` in the command menu.
  - Skip it: simple/single-step tasks won't match, so it stays out of the way.
- **When to prefer it over the mode:** you're already in `code`/`debug` (or a custom agent) and just want the behavior on demand, without switching modes.

### Quick decision guide

| Situation | Use |
|-----------|-----|
| Multi-step task, want todos + parallel subagents by default | `decomposer` mode |
| Already working in another mode, want the same behavior occasionally | `decompose-and-delegate` skill (auto / by name / slash) |
| Simple single-step task | Neither — just do it |

**Key point:** modes are chosen by you; skills are invoked by the agent (auto on description match) or by you via name/slash command.
