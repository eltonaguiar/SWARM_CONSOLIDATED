---
name: todo-closeout-loop
description: Run multi-step work to full completion by building a tracked todo list and dispatching independent items to subagents, re-planning until every item is closed out. Use for long or complex efforts you must finish completely, not partially.
---

# Todo Closeout Loop

## Trigger

Use when a request has multiple distinct steps or independent workstreams and the goal is
FULL completion — not partial progress. Also use when earlier attempts left items unfinished.

## Todo rule

- Call `todowrite` up front: one item per unit of work, with a `priority`
  (`high`/`medium`/`low`), status `pending`.
- Keep exactly one item `in_progress` at a time.
- Re-emit the whole list on every change — each `todowrite` call replaces it.
- Mark `completed` only after verifying the work; `cancelled` only for explicitly dropped scope.

## Dispatch rule

- Delegate each independent item to a `task` subagent. Use `background: true` for parallel
  work; foreground when a later item depends on the result.
- Every subagent gets a self-contained prompt: objective, constraints, relevant inputs, and
  the exact deliverable to return.
- Never split one coherent item across subagents. The parent collects results, resolves
  conflicts, and synthesizes.

## Re-plan rule (the closeout loop)

- After each batch, reassess. Turn newly discovered work into new todos; split stuck items;
  adjust priorities — then dispatch again.
- Repeat until the todo list has zero open items.

## Stop conditions

- Stop only when zero open items remain (all `completed` or `cancelled`).
- If an item is irreducibly blocked, do not spin: record the blocker, mark it
  `cancelled`-with-reason, and keep moving.
- Cap concurrent dispatch; keep nested dispatch to one level.
- Finish by reconciling the list and consolidating every subagent result into the final response.
