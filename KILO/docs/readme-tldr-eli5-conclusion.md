## TL;DR

Four complementary tools give you the same core workflow — break big work into a checklist, delegate independent pieces to helper agents in parallel, and stitch the results back together — with different defaults for when each kicks in.

- **`decomposer` mode** — you pick it explicitly (agent/mode picker). Full-capability executor that builds a todo list (`todowrite`) and dispatches independent items to subagents (`task`). **Use when:** a multi-step task with parallel workstreams, and you want tracking + parallelism by default.
- **`decompose-and-delegate` skill** — auto-used by the agent when a task matches its description (or forced by name / slash command). Same behavior as the mode, packaged as an on-demand skill. **Use when:** you're already in another mode and want the behavior occasionally without switching.
- **`closeout-loop` mode** — same decompose-and-delegate core, but it **promises to keep going**: it re-plans and re-dispatches until every checklist item is actually closed out. **Use when:** you want a guarantee that the loop won't stop early — the work isn't done until all items are done.
- **`todo-closeout-loop` skill** — the closeout-loop behavior as an auto-triggered skill (name / slash command also work). **Use when:** you want the keep-going-until-closed behavior on demand inside your current agent.

**Key point:** modes are chosen by you; skills are invoked by the agent (auto on description match) or by you via name/slash command. Simple single-step tasks match neither — just do them.

## ELI5

Think of the biggest task as a big messy pile of work, like cleaning a whole house. These tools turn that pile into a written checklist of smaller, separate jobs — vacuum the living room, scrub the kitchen, take out the trash — and then hand each independent job to its own helper so they all happen at the same time instead of one after another. The main agent keeps the checklist, gathers everyone's finished work, and puts the whole result together. It exists so big jobs get done faster and nothing is forgotten.

The "closeout-loop" versions take that one step further: instead of stopping when things get hard or a helper gets stuck, they promise to keep going — re-planning and re-sending the work — until every single tick on the checklist is genuinely checked off. Same helpers, same checklist, but a guarantee that the job is followed through to the end.

## Overall Conclusion

This project researched how modern agent frameworks structure complex work, then shipped it as two interchangeable ways of working — a chosen **mode** and an auto-triggered **skill** — each covering both a standard decompose-and-delegate pattern and a more persistent closeout-loop variant that keeps re-planning until every checklist item is closed. The packaged artifacts are reusable and documented, with a closing caveat: hands-on testing in real projects remains, since a written tool can only prove itself once it is installed, exercised, and refined against actual multi-step tasks.
