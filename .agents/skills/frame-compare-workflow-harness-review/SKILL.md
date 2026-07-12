---
name: frame-compare-workflow-harness-review
description: Use when the user explicitly asks for frame-compare-workflow-harness-review, invokes the matching Frame Compare workflow review, or wants a reusable review of workflow docs, skills, launchers, or control-plane rules.
---

# Frame Compare Workflow Harness Review

Use this skill to review the repo's agent workflow, runbook, skills, launcher surfaces, and verification policy.

## Load Order

Start with the smallest relevant set:

1. `AGENTS.md`
2. relevant sections of `docs/ENGINEERING_RUNBOOK.md`
3. the exact workflow diff, skills, or launchers in scope
4. `.codex/config.toml` and relevant role files when delegation is in scope

Read `docs/current-architecture.md`, `docs/current-cli-contract.md`,
`importlinter.ini`, or `pyproject.toml` only when the review actually evaluates
their architecture, CLI, import-layer, packaging, or tooling boundaries.

For a whole-system review, inventory every skill/role declaration, then deep-read
only overlapping, stale, or high-risk surfaces. Do not preload every full skill merely
to prove it exists.

## Review Focus

Lead with findings ordered by severity. Prioritize:

- conflicting authority or load-order rules
- skill trigger descriptions that are too broad, too narrow, or stale
- missing verification routing
- launchers pointing at nonexistent docs
- public-surface workflow gaps
- stale paths or source-repo residue
- missing or undefined delegated roles
- unnecessary role/skill proliferation or repeated generic instructions
- required-reading and verification-output context waste
- missing language-specific workflow coverage for Python, Typer CLI, or pytest changes
- instructions that would make agents overwrite user changes or claim unverified work
- PR/review-loop gaps where high-risk files can be reviewed without explicit
  checks for CLI validation errors, malformed runtime metadata, Windows
  subprocess timeouts, brittle workflow/test assertions, or typed-seam
  broadening in hotspots

Benchmark against current official OpenAI AGENTS.md, skills, subagent, and harness
guidance plus Anthropic's current harness, context-engineering, and eval guidance.
Prefer measured subtraction: every scaffold component should prevent a recurring
failure or be removed.

## Output

Report blockers first with exact files and lines. Then list non-blocking improvements and verification gaps.
