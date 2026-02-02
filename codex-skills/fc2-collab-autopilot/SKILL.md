---
name: fc2-collab-autopilot
description: Use when you want to run the Frame Compare 2.0 workflow end-to-end using local collab subagents (per-role model + reasoning effort), including selecting the next checklist slice and enforcing FC2 STOP gates/artifact ownership.
---

# FC-2.0 Collab Autopilot (Local Subagents)

This skill is for running the FC-2.0 loop with **local** subagents (separate Codex sessions) while preserving FC-2.0’s workflow invariants:

- STOP gates (no coding before APPROVED plan review + Decision Points Remaining = NONE)
- Strict artifact versioning (`plan-vN`, `plan-review-vN`, `impl-vN`, `verify-vN`, `review-vN`)
- Artifact ownership boundaries (Coding must not touch checklist/index; Verification/Review must)

## Canonical SSOT (Read, Don’t Duplicate)

- Workflow SSOT: `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md`
- Workflow quick ref: `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md`
- Role prompts: `docs/OPUS_REBUILD_FRAME_COMPARE/agent-prompts/`

## Prereqs (Repo Setup)

- Team config exists at `.codex/config.toml` and defines these CLI profiles:
  - `fc2_planning` (gpt-5.2, high)
  - `fc2_plan_review` (gpt-5.2, high)
  - `fc2_coding` (gpt-5.2-codex, medium)
  - `fc2_verify_review` (gpt-5.2-codex, high)

## Operating Model (Controller + Role Subagents)

Treat FC-2.0 as a **state machine** with a thin controller that:

- Selects the next action (resume pending run vs start next checklist slice)
- Ensures only **one writer role** is active at a time
- Enforces STOP gates between roles

Role subagents do the work and write their owned artifacts/code.

## Quick Start

1. Determine the next action / suggested RUN_ID:

```bash
python3 codex-skills/fc2-collab-autopilot/scripts/next_fc2_action.py
```

By default, this skips Phase 0 items (assumes the repo is already initialized). To include Phase 0, pass `--include-phase0`.
By default, this also skips checklist tasks marked optional. To include optional tasks, pass `--include-optional`.

2. Fully automated (recommended): run the local controller, which shells out to role-specific `codex exec --profile ...` sessions:

```bash
python3 scripts/fc2_autopilot.py
```

Useful flags:
- `--dry-run` (print the intended commands and versions)
- `--include-phase0`
- `--include-optional`

3. Manual mode: run each role as a separate local session (Codex CLI examples):

```bash
codex exec --profile fc2_planning -C . "Run FC2 Planning for RUN_ID=<RUN_ID>. Write/modify only the plan artifact per SSOT and include NEXT block."
codex exec --profile fc2_plan_review -C . "Run FC2 Plan Review for RUN_ID=<RUN_ID>. Write/modify only the plan-review artifact per SSOT and include NEXT block."
codex exec --profile fc2_coding -C . "Run FC2 Coding for RUN_ID=<RUN_ID>. Implement per plan. Write impl-vN.md. Do not touch checklist/index."
codex exec --profile fc2_verify_review -C . "Run FC2 Verification then Review for RUN_ID=<RUN_ID>. Run gates, write verify-vN.md, update checklist/index, then write review-vN.md and finalize index row."
```

Notes:
- `--profile` is CLI-only (not supported in the IDE extension). Use it for deterministic per-role model/effort.
- If you are using the Codex app to launch local subagents, mirror the same profile intent by selecting the same model + reasoning effort manually per role.

## Hard Constraints (Enforced By Prompt)

Every role prompt must include:

- **Allowed writes** (file allowlist) for that role
- **STOP conditions** (do not proceed when violated)
- **Exact inputs/outputs** (RUN_ID and artifact versions; no “latest”)

Suggested allowlists:

- Planning: `.agent-workflow/runs/<RUN_ID>/plan-vN.md` only
- Plan Review: `.agent-workflow/runs/<RUN_ID>/plan-review-vN.md` only
- Coding: repo code + tests + `.agent-workflow/runs/<RUN_ID>/impl-vN.md` only
- Verification: `.agent-workflow/runs/<RUN_ID>/verify-vN.md` + checklist + `.agent-workflow/index.md`
- Review: `.agent-workflow/runs/<RUN_ID>/review-vN.md` + `.agent-workflow/index.md`

## STOP Gates (Minimum)

- Missing required input artifact → STOP
- Plan Review verdict ≠ APPROVED → STOP (no coding)
- Decision Points Remaining ≠ NONE → STOP (no coding)
- Any validator/gate fails → STOP (no advance)
