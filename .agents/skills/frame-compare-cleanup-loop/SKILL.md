---
name: frame-compare-cleanup-loop
description: Use when the user explicitly asks for frame-compare-cleanup-loop, invokes a Frame Compare cleanup controller workflow, or wants a reusable multi-step cleanup/refactor loop as a skill.
---

# Frame Compare Cleanup Loop

Use this skill only for high-risk or repeated cleanup/refactor/remediation work
that demonstrably needs orchestration beyond one agent.

## Load Order

Read these files in order:

1. `AGENTS.md`
2. `docs/ENGINEERING_RUNBOOK.md`
3. the approved plan or execution brief
4. only the authority docs and boundary skills required by the changed surface

## Controller Workflow

1. Keep authoritative live state in `update_plan`.
2. Keep planning in the main agent unless ambiguity, cross-session scope, or a
   multi-boundary seam justifies a separate planner.
3. Execute one approved unit at a time.
4. Use one independent final review for high-risk work. Add another pass only
   after a material finding or material review-surface change.
5. Adjudicate findings through the `review-request` lifecycle.
6. Stop and re-plan when the owner, public contract, or proof surface changes.
7. Use `closeout-verification` for final status.

Do not use this loop for low/medium-risk work that one agent can safely complete.
Do not let it become a feature-delivery umbrella.
