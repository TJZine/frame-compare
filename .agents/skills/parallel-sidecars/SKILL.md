---
name: parallel-sidecars
description: Use when Frame Compare work may benefit from delegated read-heavy research, review, test/log analysis, waits, or a disjoint approved write unit.
---

# Delegation Routing

Default to one agent. Delegate only when the work is independent and the expected
benefit exceeds coordination cost.

- Read-heavy exploration, official-doc research, review, log analysis, and waits may
  run in parallel and should return concise evidence, not raw transcripts.
- Write work requires an approved unit with exact files, invariants, verification,
  stop conditions, and no overlap with another writer.
- Route decision-complete implementation through `bounded-worker-execution` when
  `worker_sol_low` or `worker_luna` is explicitly selected.
- The controller owns integration and reruns verification.

Keep delegation shallow. Do not delegate an immediate critical-path task merely to
use a role.

For a genuinely large program with multiple work units, dependency ordering, and
repeated integration checkpoints, explicitly use `large-task-orchestration`. This
skill routes individual sidecars and bounded units; it does not own a program.
