---
name: large-task-orchestration
description: Explicit controller workflow for very large Frame Compare features, refactors, migrations, or remediation programs that require multiple bounded subagents; do not use for routine work or a single delegated unit.
---

# Large Task Orchestration

Use this skill only when the work has multiple dependent or independently useful
units and one agent would otherwise accumulate excessive context or serialize work
that can safely proceed in parallel. Size alone is not enough. For one sidecar or
one bounded write unit, use `parallel-sidecars` instead.

## Freeze The Program

Before any write delegation, the controller must establish:

- goal, non-goals, risk, public contracts, and final proof;
- an ownership map and dependency order for the work units;
- shared files, symbols, and invariants that permit only one writer at a time;
- for each unit: objective, exact files in scope, dependencies, invariants,
  verification, output format, effort budget, and stop conditions.

Bounded read-only discovery may precede this freeze when ownership is unclear. Its
packet still needs a specific objective, read scope, output, effort budget, and stop
conditions. Explorers gather evidence; they do not decide or implement contracts.

Keep live state in `update_plan`. Use `execution-plan-authoring` and a Sol planner
only when unresolved seams, multiple boundaries, or a durable handoff justify the
extra pass. Do not delegate an unresolved ownership or contract decision.

## Keep One Authoritative Controller

The main task owns scope, decisions, user communication, integration order,
conflict resolution, final verification, and all staging, commits, and pushes.
Subagents must not broaden scope, delegate again, or perform git operations. Keep
`max_depth = 1`; treat `max_threads = 6` as a ceiling, not a target.

Route work deliberately:

- use read-only explorers, documentation researchers, test/log analysts, and
  monitors for independent evidence or waits;
- use the normal Sol worker for bounded implementation that still needs judgment;
- use `worker_sol_low` for a decision-complete unit with frozen ownership and
  contracts that still needs repository comprehension or local coding judgment;
- use `worker_luna` only through `bounded-worker-execution` for an exact,
  Sol-planned, low-ambiguity, cheap-to-verify unit;
- use a fresh read-only reviewer for the final independent review when the work is
  high risk, novel, broad, or supported by weak verification evidence.

Parallel writers must own disjoint files and non-overlapping symbols. Serialize
changes to shared files, composition roots, public contracts, generated authority,
the same test file or fixture, or tests of a contract that is not yet frozen.

## Reuse Context Selectively

Send a follow-up unit to an existing completed worker only when the next unit is
adjacent, has the same owner and contracts, and the worker's assumptions remain
current. Send only the delta, retained invariants, and new proof; do not replay the
full transcript.

Start a fresh worker when ownership, contract, file neighborhood, or task mode
changes; when independent parallel work is needed; or when stale assumptions or a
failed approach could bias the result. Always use a fresh agent for independent
final review rather than asking an implementer to review its own work.

Start final review with no inherited turns when the tooling permits. Send only a
bounded packet containing the task, exact review paths or diff, invariants,
non-goals, observed proof, and known risks. Omit implementer rationale and raw
transcripts so the reviewer remains independent and context-efficient.

The same reviewer may verify closure after a material fix. Do not add a second
clean reviewer for an unchanged surface by habit.

## Execute In Checkpointed Waves

1. Dispatch independent read-heavy work first and ask for concise evidence.
2. Dispatch only decision-complete write units, respecting dependency order and
   exclusive ownership.
3. Continue useful, non-overlapping controller work while subagents run.
4. On each result, inspect the actual diff, rerun the unit's focused proof, record
   material decisions, and update the plan before releasing dependent work.
5. Stop and replan if a worker finds an ownership conflict, unplanned
   public-contract change, invalid invariant, unexpected dependency, or proof it
   cannot run. A worker may report the evidence but must not choose the new contract.
6. After integration, run the runbook's risk-matched final gate and the independent
   review when required. Adjudicate findings through `review-request`.

For Frame Compare, load only the boundary skills implicated by each unit. Changes
to CLI/config, runtime integrations, Docker, Windows portable, persistence, or
architecture authority still require their runbook proof; delegation never lowers
the verification tier.

## Compact Handoff Contract

Give each worker a packet with these fields:

```text
UNIT | ROLE | OBJECTIVE | FILES | DEPENDENCIES
INVARIANTS | VERIFICATION | OUTPUT | EFFORT BUDGET | STOP CONDITIONS
```

Require this concise return:

```text
RESULT | FILES CHANGED | PROOF | ASSUMPTIONS | BLOCKERS
```

Prefer file paths, commands, and short conclusions over raw logs. The repository
diff and verification output remain the ground truth.

## Avoid

- spawning agents merely because capacity exists;
- overlapping writers or delegating the controller's immediate critical path;
- making every worker reread the whole repository or full runbook;
- duplicating worker output in the main context;
- per-unit reviewer loops or repeated clean gates without a material change;
- reusing a worker after its context becomes stale or its ownership changes;
- nested fan-out, unbounded retries, or continuing after a stop condition.
