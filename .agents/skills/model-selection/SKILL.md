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
  decision-complete unit explicitly planned by the Sol planner;
- `reviewer`: independent read-only review.

Use Sol medium for routine bounded work, Sol low for smaller decision-complete code
units, Luna high for clear repeatable work, and Sol high for ambiguous planning or
adversarial review. Keep both bounded roles behind exact scope, direct verification,
and explicit stop conditions. Do not add Luna max as a tracked role; use higher
effort only when current evidence justifies its token and coordination cost.
