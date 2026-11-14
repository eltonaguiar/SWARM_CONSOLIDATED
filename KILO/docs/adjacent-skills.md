# Adjacent Skills — Shortlist

Proposals only. None are verified mechanisms; value claims are uncertain (<uncertain>). Each is a plausible Kilo Code skill surfaced by the `decompose-and-delegate` / `todo-closeout-loop` pattern.

- **review-gate-before-merge** — Trigger: an implementation is complete and all tests pass, before merging or opening a PR. Value: enforces an explicit validation checkpoint so unreviewed work doesn't silently reach main <uncertain>.
- **release-notes-from-git-log** — Trigger: a release/tag is cut, or a changelog is requested. Value: auto-generates a human-readable changelog from commit history, saving manual retrofit <uncertain>.
- **mirrored-test-scaffold** — Trigger: a new module/feature is added with no test file present. Value: scaffolds tests that mirror the repo's existing test patterns, keeping coverage conventions consistent <uncertain>.
- **docs-code-reconciliation-audit** — Trigger: README/AGENTS/docs drift from the actual code, or after a meaningful refactor. Value: flags stale claims and undocumented behavior so docs stay trustworthy <uncertain>.
- **duplicate-consolidation-finder** — Trigger: the repo grows, or a sweep/consolidation is planned. Value: finds near-identical logic/files to merge, shrinking maintenance surface <uncertain>.
- **dependency-health-scan** — Trigger: setting up the repo, upgrading deps, or after a breakage. Value: reports outdated/conflicting/vulnerable dependencies in one pass <uncertain>.
- **deep-dive-research** — Trigger: an open-ended question needs triangulation across many sources/files. Value: fans out investigation to subagents and merges findings, mirroring decompose-and-delegate for research instead of editing <uncertain>.
