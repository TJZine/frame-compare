---
name: bounded-worker-execution
description: Use when a Sol planner has produced a decision-complete Frame Compare implementation unit suitable for the lower-cost worker_luna role.
---

# Bounded Worker Execution

Use `worker_luna` only after the configured Sol planner freezes exact files,
invariants, verification, and stop conditions. The unit must be bounded,
low-ambiguity, disjoint from other writers, and cheap to verify.

Do not use Luna to discover ownership, design public CLI/config behavior, diagnose
failures, change architecture, or repair an incomplete plan. The controller reviews
the diff, integrates it, and reruns the required proof. Route other delegation
through `parallel-sidecars`.
