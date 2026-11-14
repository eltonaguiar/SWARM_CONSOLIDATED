# Kilo Code Decomposition & Delegation — Research & Skill Spec

## Findings

- **Skill loading** — Skills are folders with a `SKILL.md` (YAML frontmatter + Markdown body). Required frontmatter: `name` (must match parent folder name) and `description`; optional license/compatibility/metadata. Only metadata is scanned at session start; full instructions load on-demand via the `skill` tool when the LLM judges the description matches. Locations: global `~/.kilo/skills/`, project `.kilo/skills/`, plus compatibility dirs (`~/.agents/skills/`, `.agents/skills/`, `~/.claude/skills/`, `.claude/skills/`) and `skills.paths` / `skills.urls` in `kilo.jsonc`. Project skills override global. — [Kilo docs: Skills](https://kilo.ai/docs/customize/skills) (official-docs)

- **Custom modes/agents** — Defined as Markdown files with YAML frontmatter (or the `agent` key in `kilo.jsonc`). Fields: `description`, `model` (provider/model), `prompt` (body = system prompt), `mode` (primary/subagent/all), `permission` (allow/deny/ask with glob patterns, last-match-wins), `color`, `steps` (max agentic iterations before forced text-only reply), `temperature`/`top_p`, `variant`, `hidden`, `disable`. Files live in `.kilo/agents/`, `.kilo/agent/` (legacy `.kilocode/agents/`), global `~/.config/kilo/agent/`. Precedence: built-in → global config → project config → `.kilo/`/legacy dirs → env. The `steps` field is the documented anti-runaway control. — [Kilo docs: Custom modes](https://kilo.ai/docs/customize/custom-modes) (official-docs)

- **Instruction files** — Project-root `AGENTS.md` (`AGENT.md` fallback), per-directory `AGENTS.md` injected as `<system-reminder>` when reading files in that dir, global `~/.config/kilo/AGENTS.md`; `CLAUDE.md` and `CONTEXT.md` auto-discovered at root. Precedence (highest→lowest): agent prompt → project `instructions` config → `AGENTS.md` → global `instructions` config. — [Kilo docs: AGENTS.md](https://kilo.ai/docs/customize/agents-md), [Kilo docs: Custom instructions](https://kilo.ai/docs/customize/custom-instructions) (official-docs)

- **Config** — `kilo.jsonc` (JSONC). Global `~/.config/kilo/kilo.jsonc`; project `kilo.jsonc` at root or `.kilo/kilo.jsonc`. Documented top-level keys: `agent`, `instructions`, `skills`, `provider`, `experimental`, display toggles, `shared_agent_board`. Full set via auto-generated `$schema`. — [Kilo docs: Settings](https://kilo.ai/docs/getting-started/settings) (official-docs)

- **Task tracking** — Native tool `todowrite` (create/update) + `todoread` (read). Input: `todos` array of items, each exactly three fields: `content` (string), `status` (pending/in_progress/completed/cancelled), `priority` (high/medium/low). Each call **REPLACES** the entire checklist. Auto-triggered for complex/multi-step tasks; manual trigger by asking for the tool. "Exactly one in_progress" is a usage convention, not an enforced rule. — [Kilo docs: Task/todo list](https://kilo.ai/docs/code-with-ai/features/task-todo-list), [Kilo docs: Tools](https://kilo.ai/docs/automate/tools) (official-docs); schema: [`packages/schema/src/session-todo.ts`](https://github.com/Kilo-Org/kilocode/blob/main/packages/schema/src/session-todo.ts) (github-repo)

- **Delegation** — Native tool `task` spawns a sub-agent session. Parameters: `description`, `prompt`, `subagent_type` (general/explore/custom), `task_id` (resume), `background` (bool). Child runs in a separate transcript but shares the parent's project directory/worktree; non-interactive (cannot ask the user). Foreground returns before parent continues; `background: true` returns immediately and delivers result later (requires experimental flag `KILO_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true`). Recursion allowed but bounded by `subagent_depth` config (default 1); exceeding fails with "Subagent depth limit reached". Other guardrails: task disabled unless `canTask` permission; children cannot use `question`; primary agents rejected as `subagent_type`; cross-session resume blocked; `permission.task` can restrict spawnable subagents. — [Kilo docs: Orchestrator mode](https://kilo.ai/docs/code-with-ai/agents/orchestrator-mode), [Kilo docs: Custom subagents](https://kilo.ai/docs/customize/custom-subagents), [Kilo docs: Tools — task](https://kilo.ai/docs/automate/tools#task-tool) (official-docs); implementation: [`packages/opencode/src/tool/task.ts`](https://github.com/Kilo-Org/kilocode/blob/main/packages/opencode/src/tool/task.ts) (github-repo)

- **Orchestrator legacy** — The dedicated `orchestrator` agent is deprecated; full-tool agents (Code/Plan/Debug) delegate to subagents natively. Kilo Swarm (`board_post`/`board_read`) is the shared board for a main session and its task descendants. — [Kilo docs: Using agents](https://kilo.ai/docs/code-with-ai/agents/using-agents) (official-docs)

- **Prior art (outside Kilo lineage)** — Anthropic's multi-agent research pattern (lead agent + parallel subagents, self-contained prompts) and the plan-and-execute pattern (separate planner + executor). — [Anthropic: Built a multi-agent research system](https://www.anthropic.com/engineering/built-multi-agent-research-system), [LangChain: Plan-and-execute agents](https://blog.langchain.dev/plan-and-execute-agents/) (community)

## Skill Spec

Use this skill when a request has at least three distinct steps, multiple independent workstreams, or subtasks that can run concurrently without shared state. Skip trivial single-step requests.

On triggering, call `todowrite` first: one item per unit of work, each with a `priority` (`high`/`medium`/`low`) and status `pending`. Keep exactly one item `in_progress` at a time. Every `todowrite` call replaces the whole list, so re-emit it on each change. Mark items `completed` only after the work is verified; `cancelled` for dropped scope.

For independent items, delegate each to a `task` subagent. Use `background: true` for parallel/independent work; use foreground when a later step depends on the result. Give every subagent a self-contained prompt: objective, constraints, relevant inputs, and the exact deliverable to return. Never split one coherent item across subagents. The parent collects results, resolves conflicts, and produces the final synthesis.

Stop conditions: do not dispatch dependent items — do them in sequence yourself. Skip delegation for small/quick items. Cap concurrent dispatch to a small budget. On repeated subagent failure, stop delegating that item and do it yourself. Keep nested dispatch to one level unless deeper delegation is explicitly justified. Finish by fully reconciling the todo list (all items completed or cancelled) and consolidating every subagent result into the final response.

## Packaging

The spec is packaged two ways: as a custom agent mode file (`.kilo/agents/decomposer.md`) and as a `SKILL.md`.

- **Agent mode** (`decomposer.md`): `mode: primary`, `description` summarizing the executor role, `permission` with all tools allow-listed (read, edit, bash, glob, grep, task, todowrite, todoread, webfetch, skill, question), and `steps: 30` as the anti-runaway cap.
- **Skill** (`SKILL.md`): `name: decompose-and-delegate` (matches folder name) plus a trigger-oriented `description`.

## Gaps

Only hands-on testing can confirm:

- Exact `todoread` return schema (undocumented even at source level).
- Whether the running build has background subagents enabled (needs experimental flag).
- Default `subagent_depth` value at runtime.
- How reliably the LLM self-triggers todos.
- Behavior of per-call model/variant overrides on `task`.
