---
name: bounded-worker-execution
description: Use when Frame Compare has a decision-complete implementation unit suitable for worker_sol_low or the lower-cost worker_luna role.
---

# Bounded Worker Execution

Use `worker_sol_low` when ownership and contracts are frozen but implementation
still needs repository comprehension or local coding judgment. Use `worker_luna`
only after the configured Sol planner freezes exact files, invariants, verification,
and stop conditions for a low-ambiguity, repeatable, cheap-to-verify unit. Both units
must be bounded and disjoint from other writers.

Do not use either role to discover ownership, design public CLI/config behavior,
diagnose failures, change architecture, or repair an incomplete plan. The controller
reviews the diff, integrates it, and reruns the required proof. Route other
delegation through `parallel-sidecars`.
