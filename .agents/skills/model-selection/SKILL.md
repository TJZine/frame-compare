---
name: model-selection
description: Use when choosing a model or reasoning effort for a Frame Compare task or handoff.
---

# Model Selection

Use configured role defaults unless current official guidance or representative
independent benchmarks justify a change:

- `explorer`: deep read-only source and ownership discovery;
- `monitor`: fast read-only waits and status checks;
- `docs_researcher`: official-source research;
- `planner`: only when separate planning is justified;
- `worker_luna`: default delegated implementation for a bounded unit whose outcome,
  owner seam, contracts, and direct proof are clear; repository comprehension and
  routine local coding judgment remain in scope;
- `worker`: Sol escalation implementation for a bounded unit with settled product,
  ownership, contracts, and proof that still needs material local design judgment,
  cross-boundary comprehension, complex diagnosis, or proof interpretation;
- `reviewer`: independent read-only review.

Treat `.codex/agents/<role>.toml` as the sole authority for exact model,
reasoning-effort, sandbox, and fallback settings. Choose implementation roles at
dispatch from current task risk rather than pinning a model in durable plans. Keep
delegated writes behind a clear owner boundary, direct verification, and explicit
stop conditions. Do not duplicate exact settings in plans, prompts, or workflow
prose, or add a tracked role until current guidance and representative evidence
justify the recurring need and coordination cost.
