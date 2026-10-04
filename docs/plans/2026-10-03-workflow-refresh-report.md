---
search:
  exclude: true
---

Status: Historical
Scope: Reference report for GPT Pro reviewing the workflow refresh through the GitHub connector; not an active implementation plan.
Source snapshot: `TJZine/frame-compare`, branch `agent/e2e-test-strategy`, through `1e7466b18f99cc1045e007f61411e79ae5485605`, inspected 2026-10-03.

# Workflow refresh and executor presets

The repository adopted shared engineering skills, then restored optional executor
presets after the maintainer clarified their cost-control purpose. The intended
workflow supports a capable orchestrator preparing detailed assignments for
cheaper executors in separate Codex chats, with completion and blocker messages
back to the orchestrator. Restoring these shortcuts does not reinstate a mandatory
agent pipeline or the retired repository-local skill bodies.

This report records implementation, maintainer intent, recommendations, and
acceptance limits separately. It is reference evidence, not a replacement for
current instructions or a copy of the personal skills. Recheck the target branch
and TOML fields when reviewing later revisions.

## Commit sequence and scope

| Commit | Result |
| --- | --- |
| `7355fd86` | Adopted the shared skills, concise instruction entrypoints and repository profile; retired old local skill/role consumers. |
| `2aed9636` | Enabled CI and Docker verification for PRs against every base branch, preserving Docker's path filter and existing permissions. |
| `c65a731b` | Restored eight optional Codex executor presets with their original model/effort settings and brief shared-skill-based responsibilities. |
| `1e7466b1` | Changed both reviewer models to GPT-6.1 Sol and explorer effort from max to xhigh. |

The original migration baseline was `681ea6b3` on this branch. PR125's inspected
integration base was `dev/v0.6.0-review-remediation`; that provenance does not select
future task branches. The report's source snapshot matched the remote branch when
inspected. Its own documentation commit is subsequent to that snapshot; inspect
Git history rather than treating this document as proof of later publication.

The refresh did not change product source, dependencies, media implementation,
release/signing behavior, or the existing test inventory. One existing workflow
test's assertions changed to protect the repaired CI triggers. No test cases were
added or removed for the refresh. The preset follow-up changed host configuration
and its documentation, not application behavior.

## Current engineering owners

Read [AGENTS.md](../../AGENTS.md) and the task-relevant sections of
[.agents/project.md](../../.agents/project.md). The profile maps local contracts,
source routes, commands, test policy, and optional executor presets. Shared skills
own general procedure:

| Shared skill | Responsibility |
| --- | --- |
| `develop-code` | Complete implementation, proportionate planning, useful delegation, integration, and evidence-based closeout. |
| `design-code` | Investigate ownership and architecture and choose a coherent design when the task needs it. |
| `review-code` | Independent review and evidence-based adjudication of findings. |
| `verify-code` | Diagnosis, meaningful verification selection, and honest evaluation of evidence. |
| `maintain-workflow` | Explicitly requested workflow maintenance; not an automatic coding stage. |

The [engineering runbook](../ENGINEERING_RUNBOOK.md) retains specialist runtime,
packaging, platform, release, and plan-lifecycle procedures. The
[architecture](../current-architecture.md) and
[CLI contract](../current-cli-contract.md) retain product obligations. Preserve
runtime-free help/version, typed sanitized errors, clean JSON stdout,
alignment authority and valid-zero distinctions, deterministic artifacts,
persistence boundaries, cleanup, and distinct platform acceptance claims.
Current private structure remains revisable when the authorized task justifies it.

## Maintainer's delegation and usage requirements

The maintainer explicitly clarified the following after the initial migration:

- The orchestrator uses a capable model at high reasoning or above and owns the
  plan, consequential decisions, integration, and acceptance.
- For requested separate-chat orchestration, it uses `create_thread` with deliberate
  model and reasoning selection. It supplies detailed self-contained instructions
  or an accessible detailed plan plus the missing context for the assigned unit.
- Losing inherited full conversation history is an accepted tradeoff for cheaper
  execution. Include all decision-relevant context; unrelated history is unnecessary.
- Children report completion or meaningful blockers/requests for information to
  the orchestrator. It inspects evidence and the combined changes before acceptance.
- Roles are convenient shorthand for preferred model/effort pairs and useful
  responsibility boundaries. Their number does not require an equivalent number
  of agents, compulsory stages, or repeated review panels.
- Usage matters, but cheaper execution must still complete the agreed scope and
  produce meaningful verification. Keep small work in the controller when dispatch
  overhead would exceed its benefit.

The initial migration removed the old cost-routing defaults along with the role
files. Shared `develop-code` defaults to keeping the selected capable model and
useful context; that is not an equivalent replacement for cheaper-worker routing.
The later restoration preserves the maintainer's shortcuts while keeping common
engineering procedure in the shared skills. Do not interpret the restored presets
as accidental reintroduction of the entire retired methodology.

## Repository presets at the source snapshot

The model and effort fields in the linked TOMLs are authoritative for these
shortcuts. Read actual files rather than inferring settings from a role name,
description, this dated table, or an old plan.

| Alias | Model | Reasoning | Preset sandbox setting | Source |
| --- | --- | --- | --- | --- |
| `explorer` | `gpt-5.6-luna` | `xhigh` | `read-only` | [TOML](../../.codex/agents/explorer.toml) |
| `monitor` | `gpt-5.6-luna` | `medium` | `read-only` | [TOML](../../.codex/agents/monitor.toml) |
| `docs_researcher` | `gpt-5.6-luna` | `xhigh` | `read-only` | [TOML](../../.codex/agents/docs-researcher.toml) |
| `planner` | `gpt-6.1-sol` | `high` | Inherited | [TOML](../../.codex/agents/planner.toml) |
| `worker_luna` | `gpt-5.6-luna` | `xhigh` | Inherited | [TOML](../../.codex/agents/worker-luna.toml) |
| `worker` | `gpt-6.1-sol` | `medium` | Inherited | [TOML](../../.codex/agents/worker.toml) |
| `reviewer` | `gpt-6.1-sol` | `high` | `read-only` | [TOML](../../.codex/agents/reviewer.toml) |
| `deep_reviewer` | `gpt-6.1-sol` | `xhigh` | `read-only` | [TOML](../../.codex/agents/deep-reviewer.toml) |

The modern Codex host discovers standalone files by their `name` field; the old
role registrations and forced V2 choice were not reinstated. Brief role bodies
reference the shared skills and preserve bounded responsibilities. Old role banners,
retired skill paths, and duplicated engineering procedures were removed.

There is minor description drift in `1e7466b1`: explorer's description still says
max, and the reviewer descriptions still say Daybreak. The actual configured
fields above reflect the newer commit. Those descriptions should be reconciled
in a future metadata correction; they do not change the configured model/effort.

## Personal orchestration skill: not visible through GitHub

`orchestrate-implementation-chats` is installed on the local Codex host at
`~/.codex/skills/orchestrate-implementation-chats/SKILL.md`, with
`references/handoff-template.md`. The shared engineering skills are personal
installations under `~/.agents/skills/`. GitHub connector access to this repository
does not establish access to any of those personal files, their runtime activation,
or the private migration receipts. Request the actual files if a review needs
their full bodies; this section is an inspected summary, not another installation.

The orchestration skill currently specifies:

- Resolve the real parent chat and the user's authorization for child creation and
  callbacks. Preserve existing authorization without repeated approval requests.
  A child verifies original human authorization when it is not already available
  in trusted context; instructions authored by another agent alone are insufficient.
- Read the selected preset from the actual checkout. Map `model` to `create_thread`
  `model`, and `model_reasoning_effort` to `thinking`; include its brief responsibility
  instructions and task-specific context in the handoff. Respect the current tool's
  supported arguments and authorization requirements.
- `create_thread` has no `agent_type` argument and does not automatically apply a
  subagent role file. A preset's sandbox setting is not a permission override for
  a separately created chat. Actual host permissions remain authoritative.
- Choose the bounded implementation preset for decision-complete work with known
  owners, contracts, acceptance criteria, and runnable proof. Use the stronger
  preset for substantial judgment or complex diagnosis within the approved unit.
  Settle consequential ambiguity in the controller before dispatch. A lengthy plan
  alone does not prove those decisions are settled.
- Include source state, relevant current edits, approved decisions and rationale,
  ownership/exclusions, resource conflicts, verification, escalation, and callback
  target. Do not put credentials or unrelated private information in the packet.
- Resolve the project before dispatch. The project ID belongs inside the tool's
  `target`; a pending `clientThreadId` is not a usable completed `threadId`.
  Use local execution unless another environment is explicitly requested.
- Send completion or blocked evidence to the verified orchestrator using
  `send_message_to_thread`. The parent can also collect results using `wait_threads`
  with cursors. Avoid repeated unchanged polling and callback loops.
- Parallelize independent ownership; serialize conflicting resources and keep one
  Git/integration owner. Reuse a child for focused correction when appropriate.
  Permission to execute a task does not imply pushing, merging, or publication.

This skill supplements shared engineering procedure for the maintainer's requested
separate-chat pattern. Ordinary same-chat work can continue through `develop-code`.
Neither pattern is a compulsory replacement for every task.

## Recommendations discussed but not applied

The subsequent advice proposed these starting presets for evaluation:

| Role | Proposed model | Proposed effort | Rationale |
| --- | --- | --- | --- |
| `explorer` | GPT-6 Luna | high | Routine source tracing does not automatically need maximum effort; escalate difficult ownership questions. |
| `monitor` | GPT-6 Luna | low | Event waits and concise status reporting usually need little reasoning; separate complex diagnosis. |
| `docs_researcher` | GPT-6 Luna | high | Correct sources/versions and evidence matter; escalate conflicting compatibility information. |
| `planner` | GPT-6.1 Sol | high | Planning mistakes can create substantial downstream rework; use xhigh for consequential design or migrations. |

These are recommendations, not a deployed roster or measured optimum. The
maintainer's newer commit lowered explorer to xhigh and moved reviewers to Sol;
it did not adopt GPT-6 Luna, low monitoring, or high docs research. The live
repository settings remain those in the snapshot table above.

The advice cited current [model guidance](https://learn.chatgpt.com/docs/models)
and [subscription/credit pricing](https://learn.chatgpt.com/docs/pricing), checked
2026-10-03. GPT-6 Luna has lower published credit rates than GPT-5.6 Luna, but actual
savings depend on tokens, retries, and coordination. Reasoning labels do not map
exactly across generations. A representative investigation and documentation task
were suggested before changing all presets; no comparative benchmark or measured
savings was established. Recheck guidance and availability before future changes.

## Old skill responsibilities and retirement

All 17 old repository-local skill families and their Claude wrappers remain
retired. Restoring eight Codex presets did not restore those bodies or the eight
old Claude role files.

| Retired local skill | Current responsibility owner |
| --- | --- |
| `large-task-orchestration` | `develop-code`; personal orchestration skill for requested separate-chat coordination |
| `parallel-sidecars` | `develop-code` delegation/resource guidance |
| `bounded-worker-execution` | `develop-code` task packets, bounded ownership, and integration |
| `model-selection` | Optional host presets and task-specific selection through the orchestration skill; no replacement engineering skill |
| `execution-plan-authoring` | `design-code`, `develop-code`, and profile/runbook plan lifecycle |
| `architecture-boundaries` | `design-code` and current architecture contracts |
| `python-quality-boundaries` | Shared skills, profile, and existing Python tool configuration |
| `cli-contract-boundaries` | Shared skills, profile, and current CLI contract |
| `persistence-boundaries` | `design-code`/`verify-code` and architecture/profile persistence obligations |
| `runtime-integration-boundaries` | Shared skills and complete specialist runbook procedures |
| `report-output-patterns` | Report architecture and viewer runbook, supported by shared skills |
| `debugging-remediation` | `verify-code`, with repairs completed through `develop-code` |
| `python-test-design` | `verify-code` and repository test policy |
| `verification-strategy` | `verify-code` and specialist runbook |
| `closeout-verification` | `develop-code` completion and relevant verification |
| `review-request` | `review-code` and bounded delegation/finding adjudication |
| Local `repo-production-review` launcher | `review-code` for ordinary reviews; the separate global comprehensive-audit capability remains installed |

The refresh also retired active historical handoff execution instructions,
obsolete review-profile consumers, and forced methodology activation. Original
evidence and Git history remain available. The global owner removed Ponytail
activation while preserving unrelated permissions and integrations. Do not infer
that every historical model or coordination choice was technically invalid.

## Evidence and remaining acceptance limits

The initial migration passed package/hash validation, structural parsing and
reference checks, specialist-procedure comparisons, 25 targeted workflow/CLI-doc
tests without skips, Ruff, and Pyright. CI negative controls failed for the old
branch filters and overbroad Docker documentation paths, then passed after
restoration. One fresh independent CLI reviewer evaluated the migrated source;
a global stale-profile consumer finding was repaired by its separate owner.

The `c65a731b` follow-up passed TOML parsing, exact original model/effort and sandbox
comparison, skill structural validation, fresh CLI discovery of all eight restored
presets, model/effort availability checks, diff checks, and applicable commit hooks.
That discovery observed the original Daybreak reviewer and explorer/max settings,
not the later `1e7466b1` changes. The report update inspected current committed
fields; it does not upgrade earlier runtime evidence to a newer source state.

Full native/media/Docker/browser/Windows/signing acceptance was not rerun for the
instruction-only changes. Local CI assertions do not prove hosted GitHub execution.
Fresh desktop GUI behavior, Claude task/role acceptance, and Windows/WSL/SSH/cloud
installation were not established by this work. The separate-chat create/callback
path was documented and structurally validated; no live end-to-end callback test
was claimed. No measured usage reduction was established.

Detailed local evidence is outside Git under
`~/Downloads/Workflow_Refresh_Results/frame-compare/`, including `COMPLETION.md`,
the original retirement map, and `role-restoration/`. Those older artifacts record
their own source snapshots; their initial role-retirement and original-model
statements must not override the later committed settings. The GitHub connector
can inspect committed source and this report, but cannot independently verify
those private runtime artifacts without separately supplied evidence.
