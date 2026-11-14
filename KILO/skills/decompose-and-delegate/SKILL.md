---
name: decompose-and-delegate
description: Break multi-step work into a tracked todo list and dispatch independent items to subagents. Use when a request has 3+ distinct steps, independent workstreams, or subtasks that can run in parallel without shared state.
---

# Decompose & Delegate

## Trigger

Use when a request has at least three distinct steps, multiple independent workstreams, or
subtasks that can run concurrently without shared state. Skip trivial single-step requests.

## Todo rule

- Call `todowrite` first: one item per unit of work, with a `priority`
  (`high`/`medium`/`low`), status `pending`.
- Keep exactly one item `in_progress` at a time.
- Each `todowrite` call replaces the whole list — re-emit it on every change.
- Mark `completed` only after the work is verified; `cancelled` for dropped scope.

## Dispatch rule

- For independent items, delegate each to a `task` subagent.
- Use `background: true` for parallel/independent work; foreground when a later step depends on the result.
- Give each subagent a self-contained prompt: objective, constraints, inputs, and the exact deliverable.
- Never split one coherent item across subagents.
- The parent collects results, resolves conflicts, and produces the final synthesis.

## Stop conditions

- Do not dispatch dependent items — do them in sequence yourself.
- Skip delegation for small/quick items.
- Cap concurrent dispatch to a small budget.
- On repeated subagent failure, stop and do the work yourself.
- Keep nested dispatch to one level unless deeper delegation is explicitly justified.
- Finish by fully reconciling the todo list and consolidating all results into the final response.
