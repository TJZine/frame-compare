---
name: bounded-worker-execution
description: Use when an approved Frame Compare plan contains concrete, disjoint implementation slices that can be delegated to worker agents without making the main session wait on the immediate critical path.
---

# Bounded Worker Execution

## Overview

Use this skill when a plan-approved implementation slice is concrete enough for a `worker` agent to execute without inventing seams, adapters, ownership, public contracts, or verification depth.

The controller still owns decomposition, integration, verification, and final judgment.

## Preconditions

All of these must already be true:

1. The task has an approved execution brief, tracked plan, or run bundle.
2. The slice names exact files in scope.
3. The slice has a clear verification target.
4. The write scope is disjoint from other active workers.
5. The worker does not need to invent owner seams, CLI/config contracts, or runtime verification policy.

If any precondition is false, keep the work local or re-plan first.

## Worker Slice Contract

Every delegated slice should specify:

- exact task
- exact files in scope
- files out of scope when ambiguity is likely
- constraints and invariants
- required verification
- expected return format

Do not make the worker infer the slice from a broad plan alone.

## Execution Pattern

1. Decide whether delegation is justified.
2. Cut one slice with one write owner.
3. Dispatch one `worker` per disjoint slice.
4. Continue useful non-overlapping local work.
5. Review worker output before integration.
6. Re-run required verification locally on the integrated result.
7. If the worker surfaces a blocker or seam question, stop and re-plan.

## Common Mistakes

- Delegating before the plan is execution-grade
- Running parallel workers against the same files or shared symbols
- Letting a worker decide public CLI/config behavior
- Treating worker output as done before local verification
