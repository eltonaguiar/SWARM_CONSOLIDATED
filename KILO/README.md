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
