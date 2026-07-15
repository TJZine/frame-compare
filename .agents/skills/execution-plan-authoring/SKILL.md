---
name: execution-plan-authoring
description: Use when Frame Compare needs a decision-complete execution brief or durable cross-session plan.
---

# Execution Plan Authoring

Choose `update_plan` only, a light single-session brief, or a tracked plan for
durable cross-session memory. Do not promote routine work into `docs/plans/`.

Freeze goal/non-goals, owner seam, files in/out, public contracts, invariants,
verification, rollback, and stop conditions. Leave helper names, local control flow,
and test organization to implementation. Stop if ownership, product behavior, or
proof depth remains unresolved.

Select `worker_sol_low` for a bounded unit with frozen ownership and contracts that
still needs repository comprehension or local coding judgment. Select `worker_luna`
only for an approved Sol-planned unit whose files, invariants, verification, and stop
conditions are frozen; state why it is low ambiguity and cheap to verify. The
controller integrates either result and reruns the required proof; otherwise use the
normal Sol worker.

Tracked plans begin with `Status: Active`, `Scope`, and `Owner`; mark them historical
when complete.
