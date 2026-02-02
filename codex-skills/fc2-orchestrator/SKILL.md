---
name: fc2-orchestrator
description: Use when running or streamlining the Frame Compare 2.0 5-agent run loop (Planning → Plan Review → Coding → Verification → Review), including RUN_ID confirmation, NEXT AGENT PROMPT handoffs, and low-touch human operator flow.
---

# FC-2.0 Orchestrator Skill

## Goal

Minimize the human operator role to: **confirm** → **paste NEXT** → **repeat**.

If you want to reduce (or eliminate) manual NEXT copy/paste by using **local collab subagents** with per-role model/effort, use `fc2-collab-autopilot` instead.

## Canonical Sources (read-only)

- `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md` (read first — curated quick reference)
- `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` (canonical SSOT for templates/appendices)
- `docs/OPUS_REBUILD_FRAME_COMPARE/agent-prompts/`
- `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md`
- `.agent-workflow/index.md`
- `.agent-workflow/runs/README.md`

## Operating Rules

1. **One run = one checklist item.** Keep the plan scope to a single item (or an explicitly-scoped sub-slice).
2. **RUN_ID protocol is mandatory.**
   - If RUN_ID is not provided, Planning proposes; human replies `CONFIRM RUN_ID: <RUN_ID>`.
3. **NEXT blocks are the handoff mechanism.**
   - The human copies the `## NEXT AGENT PROMPT (COPY/PASTE)` block from the end of the latest artifact file and pastes it into the next agent.
4. **Plan Review gate is non-negotiable.**
   - Coding must not begin unless Plan Review is APPROVED and includes `Implementation Agent Decision Points Remaining: NONE`.
5. **Validation is STOP-grade.**
   - After writing/updating any artifact, validate per `11-agent-workflow.md` (STOP on failure).
6. **Contract freshness hygiene.**
   - Coding must run `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` (regen if needed) before handing off to Verification.

## Low-Touch Orchestration Template (what to ask the human for)

Ask only:

- “Minimal mode or directed mode?”
- “Confirm RUN_ID?”
- “Proceed to next agent?” (paste NEXT block)

## When to Reset Agent Threads

Follow the “Agent Reset Policy (Context Hygiene)” in `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md`.
