---
name: model-selection
description: Use when choosing a model or reasoning effort for a Frame Compare task or handoff.
---

# Model Selection

Use configured role defaults unless current official guidance or representative
independent benchmarks justify a change:

- `explorer` and `monitor`: fast read-only work;
- `docs_researcher`: official-source research;
- `planner`: only when separate planning is justified;
- `worker`: normal bounded implementation;
- `worker_sol_low`: bounded implementation with frozen ownership and contracts that
  still needs repository comprehension or local coding judgment;
- `worker_luna`: lower-cost execution only for a low-ambiguity, cheap-to-verify,
  decision-complete unit explicitly planned by the `planner`;
- `reviewer`: independent read-only review.

Treat `.codex/agents/<role>.toml` as the sole authority for exact model,
reasoning-effort, sandbox, and fallback settings. Keep both bounded worker roles
behind exact scope, direct verification, and explicit stop conditions. Do not
duplicate exact settings in plans, prompts, or workflow prose, or add a tracked
role until current guidance and representative evidence justify the recurring
need and coordination cost.
