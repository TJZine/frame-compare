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

Read the repository-root `AGENTS.md` and task-relevant sections of
`.agents/project.md` (source files outside the documentation site). The profile maps local contracts,
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

## Follow-up corrections — 2026-10-04 (Eastern time)

This section records implementation of the complete
`~/Downloads/Workflow_Followup_Prompts/01_FRAME_COMPARE_FIXES.txt` prompt. The
original report above remains a historical snapshot; its proposed model changes
and earlier verification limits do not override this follow-up.

The actual checkout was `/Users/tristan/Software/frame-compare`, branch
`agent/e2e-test-strategy`, HEAD
`689f8e8981b6a7b7ecf3b89370e6312aa6bd2bd2`, matching the reviewed baseline.
Initial staged, unstaged, and untracked state was clean, with no later commits to
reconcile. At verification closeout, seven owned files were modified, unstaged
and uncommitted, and HEAD was unchanged. The maintainer subsequently authorized a
local commit of these corrections and this report. The recorded test evidence
identifies the verified working state; committing it does not establish new hosted
proof. There were no already-correct/no-op items. One controller owned edits, integration,
Git inspection, and serialized Docker/media resources.

| Correction | Implemented result |
| --- | --- |
| Missed trigger consumer | The existing staging-sync test forbids both `branches` and `branches-ignore` for CI/Docker PRs. CI push, docs push/PR, and Release Please push assertions remain. Workflow YAML, Docker paths, and stronger workflow tests are unchanged. |
| Preset descriptions | Explorer, reviewer, and deep reviewer now use the specified neutral descriptions. TOML parsing and comparison to HEAD prove every other field/body unchanged; all eight presets remain. |
| Absent-runtime mock | The existing conditional global mock defines `YUV420P10 = 1`, distinct from `RGBS = 0`. Real VapourSynth preservation and all other constants remain. Existing HDR conversion assertions are unchanged. |
| U4 budget expectations | Both `budget` and `budget-7` retain every assertion preceding the former target table. Complete target membership, singleton identity/credibility, offsets, descending serialized PSR, three examined ranks, and twelve positions now replace incidental literal target ordering. |

The U4 change is test-only. The guide and production owner already specify
credible chunks in descending PSR, four positions each, twelve total, with
unexamined credible disagreement blocking acceptance. The test reads independently
serialized audio evidence; it does not call a private target builder for its
expected answer. Equal scores may appear in either order; unequal priority
inversions must fail. No production alignment, tonemapping, thresholds, media,
budgets, lag math, or public contract changed. A FFmpeg/NumPy defect was not
measured or asserted as the cause of the earlier ranking difference.

### Executed local evidence

The locked mock environment was provisioned with task-local
`UV_PROJECT_ENVIRONMENT`, `uv sync --python 3.13 --group dev --frozen`; both
VapourSynth and VSView specs were absent. The normal `.venv`, shell configuration,
real runtime, `pyproject.toml`, and `uv.lock` were preserved.

| Check | Result and limits |
| --- | --- |
| `uv run --no-sync pytest -q tests/workflows tests/vs/test_tonemap_extracted_modules.py` in mock environment | 95 passed, no skips; exercises the repaired import-time branch and both existing YUV conversion tests. |
| `uv run --no-sync pytest -q -n4 --dist loadgroup` in mock environment | Exit 0: 2,927 passed, 86 skipped case outcomes plus nine collection/module skips (95 skip-summary outcomes in total). Native VS/VSView, media opt-in, Windows/PowerShell, continuous-resource and live-service acceptance remain distinct. |
| Ruff check and format-check on the three edited Python paths | Passed. Only the supplied U4 generator-expression assertion needed formatting. |
| `uv run --no-sync pyright --warnings` | Zero errors/warnings in the existing VSView/PySide6/VapourSynth-enabled `.venv`; not run against the incomplete mock environment. |
| TOML and test inventory comparison | All three TOMLs parse and differ only in description. Function/decorator AST inventories equal HEAD, including both U4 name parameters; no test cases added, removed, or weakened. Relevant mock and Docker collection inspected; standalone Mac U4 collection skips because its real runtime lacks L-SMASH, while Docker collected and ran both parameters. |
| Focused canonical Docker verifier with both prescribed `--pytest-path` arguments | 16 passed, zero skips; native runtime and production application proof passed. |
| `bash tools/verify_docker_integration.sh` | 276 passed, zero skips in 404.61 seconds; complete native preflight and production application/artifact proof passed. Test/production images rebuilt by each canonical invocation; final identities retained. |
| Bounded negative controls | Workflow controls invoke the existing test against temporary workflow copies: both forbidden filter forms fail for both workflows; baseline/restored inputs pass. Both parameter invocations of the existing U4 integration function passed again against cached real Docker media, without a media rebuild. Against their captured actual evidence, the current assertion block rejected unequal-PSR inversions and erroneous 8-/16-position examined/unexamined budgets, then passed restored evidence. These mutants are assertion-level controls over native evidence, not execution of mutated production code. |
| Final complete owned diff | `git diff --check` passed; only the seven expected paths changed. Original report prefix preserved. |

No unchanged passing full Python suite was repeated after formatting/report work.
The full Docker gate uses the formatted integrated test source. Early temporary
capture launches stalled before container start, including a no-mount start probe;
only task-owned containers/processes were removed. The canonical full verifier
subsequently started normally. No host configuration, product timeout, failure/skip
handling, framework, or persistent test inventory was changed to work around it.

### Hosted source and remaining acceptance

One closeout read of current runs/jobs, checkout logs, PR125 metadata, and artifact
metadata found the relevant published head still at `689f8e8981b6a7b7ecf3b89370e6312aa6bd2bd2`,
base `2102da630c8f1ab75b1d179a7cfac6050aa537db`. All three checkout logs verify actual
merge checkout `c402584fe4d51886722622715c4aab7121482b29`; each is completed attempt 1.

| Existing hosted run | Result and artifact limits |
| --- | --- |
| [CI 37169367090](https://github.com/TJZine/frame-compare/actions/runs/37169367090) | Failed: the old workflow assertion and two missing mock-format lookups; 68 logged skip-summary outcomes. Other component jobs passed, aggregate failed. No uploaded artifacts. |
| [Windows portable 37169367456](https://github.com/TJZine/frame-compare/actions/runs/37169367456) | Unsigned verification/build failed at the old workflow assertion; 70 logged skip-summary outcomes. Signed validation/release/verification jobs skipped. No uploaded portable artifacts or candidate signing/physical-host proof. |
| [Docker 37169367119](https://github.com/TJZine/frame-compare/actions/runs/37169367119) | Failed: both fixed-order U4 cases, with 274 passed and zero skips. One nonexpired `docker-e2e-artifacts` artifact is listed; its contents were not downloaded/validated and cannot prove these edits. |

The latest PR-title run succeeded, but it is not product/runtime acceptance.
These old hosted runs remain diagnosis evidence. New hosted CI/Windows/Docker
acceptance awaits user publication of the local edits; no push, dispatch, PR
metadata/comment, merge, release, or external message was performed. Physical
Windows/GPU/signing and other distinct platform claims are not established here.

The separate global follow-up receipt is
`~/Downloads/Workflow_Refresh_Results/followup-2026-10-03/global/COMPLETION.md`, with
`followup-receipt.json` and `source-cutover.json`. It records unchanged core skills,
Codex CLI/bundled-wrapper discovery, native canonical suggestion review, and
projectless create/callback checks with accepted preset arguments. Runtime
model/effort and child sandbox guarantees were not independently established;
manual alias was rejected, fresh desktop UI acceptance was untested, Claude OAuth
was expired, and Windows/WSL/cloud were untested. Those host-specific claims are
cited without repeating global acceptance or claiming measured savings.

Detailed commands, logs, structural/negative controls, hosted excerpts, source and
image identities, and the final local diff are outside Git at
`~/Downloads/Workflow_Refresh_Results/followup-2026-10-03/frame-compare/`.
`final-state.json` identifies HEAD plus the hashes of the actual uncommitted files;
`local-changes.diff` is the reviewable complete change. Temporary environments,
capture scripts, and logs were kept outside the repository.
