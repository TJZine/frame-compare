# Agent Workflow Directory

This directory contains implementation artifacts produced by the 5-agent workflow.

## Structure

```
.agent-workflow/
├── index.md              # Run index (append by Verification; finalize by Review)
├── current-state.json    # Current workflow state
├── runs/                 # Versioned run directories (canonical)
│   └── <RUN_ID>/
│       ├── plan-vN.md         # Planning Agent output (v1, v2, ...)
│       ├── plan-review-vN.md  # Plan Review Agent output (v1, v2, ...)
│       ├── impl-vN.md         # Coding Agent output (v1, v2, ...)
│       ├── verify-vN.md       # Verification Agent output (v1, v2, ...)
│       └── review-vN.md       # Review Agent output (v1, v2, ...)
└── README.md             # This file
```

## Workflow Reference

See `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` for:

- Agent definitions and personas
- Handoff templates
- Process documentation
- The required `Workflow Consistency Checklist (STOP/VALIDATE)` section (artifact validation + stop conditions)

## Agent Prompts

See `docs/OPUS_REBUILD_FRAME_COMPARE/agent-prompts/` for:

- `01-planning-agent.md` — Planning Agent system prompt
- `02-plan-review-agent.md` — Plan Review Agent system prompt
- `03-coding-agent.md` — Coding Agent system prompt
- `04-verification-agent.md` — Verification Agent system prompt
- `05-review-agent.md` — Review Agent system prompt
