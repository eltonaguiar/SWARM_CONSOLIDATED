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
| `agents/closeout-loop.md` | Agent / mode (primary) | Same decompose-and-delegate core, but re-plans and re-dispatches until every todo item is closed out. |
| `skills/todo-closeout-loop/SKILL.md` | Skill | Closeout-loop behavior (keep going until all items are done) as an auto-triggered skill. |

## Notes

- Subagents share your project directory but run in their own session; they cannot ask the user questions.
- Background subagents require the experimental flag `KILO_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true`.
- The default subagent recursion depth is 1; keep nested dispatch to one level unless raised.

---

## TL;DR

Four complementary tools give the same core workflow — break big work into a checklist, delegate independent pieces to helper agents in parallel, and stitch the results back together — with different defaults for when each kicks in.

- **`decomposer` mode** — you pick it explicitly (agent/mode picker). Full-capability executor that builds a todo list (`todowrite`) and dispatches independent items to subagents (`task`). Use when: a multi-step task with parallel workstreams, and you want tracking + parallelism by default.
- **`decompose-and-delegate` skill** — auto-used by the agent when a task matches its description (or forced by name / slash command). Same behavior as the mode, packaged as an on-demand skill. Use when: you're already in another mode and want the behavior occasionally without switching.
- **`closeout-loop` mode** — same decompose-and-delegate core, but it promises to keep going: it re-plans and re-dispatches until every checklist item is actually closed out. Use when: you want a guarantee that the loop won't stop early — the work isn't done until all items are done.
- **`todo-closeout-loop` skill** — the closeout-loop behavior as an auto-triggered skill (name / slash command also work). Use when: you want the keep-going-until-closed behavior on demand inside your current agent.

**Key point:** modes are chosen by you; skills are invoked by the agent (auto on description match) or by you via name/slash command. Simple single-step tasks match neither — just do them.

## ELI5

Think of the biggest task as a big messy pile of work, like cleaning a whole house. These tools turn that pile into a written checklist of smaller, separate jobs — vacuum the living room, scrub the kitchen, take out the trash — and then hand each independent job to its own helper so they all happen at the same time instead of one after another. The main agent keeps the checklist, gathers everyone's finished work, and puts the whole result together. It exists so big jobs get done faster and nothing is forgotten.

The "closeout-loop" versions take that one step further: instead of stopping when things get hard or a helper gets stuck, they promise to keep going — re-planning and re-sending the work — until every single tick on the checklist is genuinely checked off. Same helpers, same checklist, but a guarantee that the job is followed through to the end.

## Overall Conclusion

This project researched how modern agent frameworks structure complex work, then shipped it as two interchangeable ways of working — a chosen **mode** and an auto-triggered **skill** — each covering both a standard decompose-and-delegate pattern and a more persistent closeout-loop variant that keeps re-planning until every checklist item is closed. The packaged artifacts are reusable and documented, with a closing caveat: hands-on testing in real projects remains, since a written tool can only prove itself once it is installed, exercised, and refined against actual multi-step tasks.

---

## Summary — TL;DR & ELI5

*Added 2026-11-14 03:27 EST*

**TL;DR:** This folder ships four reusable Kilo Code tools that all follow one workflow — break big work into a tracked checklist, send independent items to parallel subagents, then stitch results together. `decomposer` (mode) and `decompose-and-delegate` (skill) do the standard version; `closeout-loop` (mode) and `todo-closeout-loop` (skill) keep re-planning until every item is closed. Modes are picked by you; skills are auto-triggered on a description match (or by name / slash command).

**ELI5:** Imagine cleaning a whole house. These tools write a checklist of separate chores and hand each to its own helper working at the same time, then the main person gathers everything and finishes up. The closeout-loop versions promise not to stop until every box on the checklist is genuinely ticked.
