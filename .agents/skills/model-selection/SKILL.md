---
name: model-selection
description: Use when choosing a model or reasoning effort for a Frame Compare task or handoff.
---

# Model Selection

Use configured role defaults unless representative evals justify a change:

- `explorer` and `monitor`: fast read-only work;
- `docs_researcher`: official-source research;
- `planner`: only when separate planning is justified;
- `worker`: bounded implementation;
- `worker_luna`: lower-cost execution only for a decision-complete unit explicitly
  planned by the Sol planner;
- `reviewer`: independent read-only review.

Use medium reasoning for routine bounded work and high for ambiguous planning or
adversarial review. Keep Luna behind exact scope, direct verification, and explicit
stop conditions. Increase effort only when measured quality improves enough to
justify cost.
