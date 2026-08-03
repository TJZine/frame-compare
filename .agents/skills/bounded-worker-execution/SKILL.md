---
name: bounded-worker-execution
description: Use when Frame Compare has a bounded implementation unit suitable for the cost-efficient worker_luna role.
---

# Bounded Worker Execution

Use `worker_luna` by default for delegated implementation when the outcome, owner
seam, contracts, acceptance criteria, verification, and stop conditions are clear.
The unit may require substantial repository comprehension, exact-file discovery,
routine local design choices, focused test design, and diagnosis of failures caused
by its implementation. It must remain bounded and disjoint from other writers.

The worker may choose files and implementation details within the approved owner
seam, but must stop when evidence exposes unresolved product intent, ownership,
public CLI/config behavior, architecture, proof depth, a new dependency or
compatibility policy, or scope expansion. The controller reviews the diff,
integrates it, and reruns the required proof. Use `worker` instead when a settled
bounded unit needs material local design judgment, cross-boundary comprehension,
complex diagnosis, or proof interpretation; return unresolved product, owner,
contract, architecture, or proof decisions to planning. Route other delegation
through `parallel-sidecars`.
