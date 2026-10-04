# Frame Compare repository profile

This profile supplies repository facts and evidence routes to the shared
`develop-code`, `design-code`, `review-code`, and `verify-code` skills. It is not an
additional orchestration procedure.

Prepared from PR125 head `681ea6b30ce8a6ff612c9afccb9a19370b3c2a85` on 2026-10-03.
Reconciled with that checkout during installation. On later tasks, read current
source/configuration when relevant facts have changed. The pinned
baseline records this profile's provenance; it does not choose future task branches.

## Product and change boundaries

Frame Compare is a Python 3.13+ CLI-first packaged application for deterministic
video-frame comparison, alignment, tonemapping, reports, and optional publishing.
The installed command is `frame-compare`, owned by `frame_compare.cli.entry:app`.

The supported public surfaces are documented CLI/config behavior, streams, exit
codes, persisted/output contracts, distribution contents, and installer/update
behavior. Importable modules are convenience surfaces unless an explicit supported
contract says otherwise; generated API documentation alone does not create a stable
API promise. Remove obsolete internal paths when replacing a design, after checking
real callers, plugin entry points, persisted consumers, and the authorized scope.

Preserve these obligations unless the task explicitly changes the corresponding
product requirement:

- Simple CLI paths work without eager native-media imports. JSON mode keeps stdout
  machine-readable and sends diagnostics to stderr; expected failures use typed,
  sanitized errors and documented exit behavior.
- New computed audio alignment is a candidate until the audio/video decision owner
  authorizes it. The inspected implementation emits `trusted_automatic` with
  `audio_video_confirmed` for accepted new computations; provisional/unavailable
  evidence must not silently become applied trims or computed-cache authority.
  Keep valid zero distinct from absent authority. Manual confirmation retains the
  original attempt's evidence and its provenance.
- Persisted formats, frame/sign conventions, source identity, output ordering, and
  cache reuse semantics are explicit. Validate external or persisted input at its
  owner. Preserve the different consequences of invalid user config and recoverable
  cache state; protect secrets, containment, and owned atomic writes.
- Subprocesses, native handles, files, and HTTP clients have explicit lifetimes,
  bounded operations, and cleanup. Respect caller-owned injected resources. Keep
  webhook transport isolated from the publishing client's state.
- Packaged Docker and Windows runtimes are distinct support profiles. Native
  source tests, GUI proof, unsigned artifact proof, signing, and physical-host
  acceptance establish different claims.

Current module boundaries are starting evidence for design. A justified redesign
may change them together with their callers, checks, and documentation. Do not use
file size, current owner names, or historical workflow choices as a veto on a
better scoped design.

## Source routes

| Question | Read first |
| --- | --- |
| Runtime order, composition, owners | `docs/current-architecture.md`; `src/frame_compare/cli/entry.py`, `runner.py`, `orchestration/coordinator.py` |
| CLI/config/JSON and persistence contract | Relevant section of `docs/current-cli-contract.md`; affected `cli/` or `config/` owner |
| Import direction | `importlinter.ini`; current callers of the changed boundary |
| Alignment policy and application | `services/alignment_decision.py`, `services/alignment.py`, `orchestration/phase_alignment.py`, `utils/alignment_evidence.py` |
| Reports and interaction | `services/report/`; architecture's Report Viewer section; `tests/services/node_harness.py`, `tests/browser/` |
| Persistence | Current architecture's persistence section; `config/persistence.py`, `utils/atomic_write.py`, affected cache or run-record owner |
| Media/runtime compatibility | `docs/supported-media-runtime.md`, `Dockerfile`, `tools/windows_portable/manifest.windows-x64.json`, `pyproject.toml`, `uv.lock` |
| Runtime or packaging proof | Relevant procedure in `docs/ENGINEERING_RUNBOOK.md`; current CI workflow and verifier script |
| Historical rationale | `docs/DECISIONS.md`; relevant historical plan only when its decision affects this task |

Use `rg` and direct source reads for exact queries. Codanna is optional assistance
for unfamiliar ownership/call paths; confirm its index belongs to the right checkout
and confirm consequential results in source. A missing optional tool does not block
otherwise supported work.

The layered import contract keeps analysis, render, and services independent at the
inspected baseline. Lazy facades exist for selected orchestration and VS entry
surfaces; concrete owner imports are the normal internal pattern. Revisit this
boundary deliberately if the design requires it rather than adding suppressions.

## Environment and verification

Use the checked-in lockfile and existing tools. Bootstrap the contributor environment
with `uv sync --group dev --extra vsview --frozen`. Native-media availability is a
separate capability check. A docs-only environment can be restored with
`uv sync --group dev --group docs --extra vsview --locked` before Python gates.

These are the common command entry points. Commands were inspected, not executed
as part of this profile's preparation. Select proof from the changed behavior and
the current runbook's applicable gates; do not run every route on every edit.

| Purpose | Command |
| --- | --- |
| Type analysis (`src` and `tests`) | `uv run --no-sync pyright --warnings` |
| Lint | `uv run --no-sync ruff check .` |
| Formatting | `uv run --no-sync ruff format --check .` |
| Static security gate | `uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium` |
| Import contracts | `uv run --no-sync lint-imports --config importlinter.ini` |
| Focused behavioral check | `uv run --no-sync pytest -q <existing-test-path-or-selection>`; replace the placeholder with the actual affected tests |
| Full native suite | `uv run --no-sync pytest -q -n4 --dist loadgroup` |
| CLI E2E selection | `uv run --no-sync pytest -q tests/e2e` (with media opt-in unset, inspect the media-tier skips) |
| Full Docker media gate | `bash tools/verify_docker_integration.sh` |
| Focused Docker E2E development | `bash tools/verify_docker_integration.sh --pytest-path tests/e2e` |
| Report browser smoke | `uv run --no-sync pytest -q tests/browser/test_report_browser_smoke.py` |
| API-reference drift | `uv run --no-sync python scripts/generate_api_docs.py --check` |
| Documentation site | `uv run --no-sync zensical build --clean --strict` after installing the docs group |
| Workflow/authority structure | `git diff --check`; parse edited YAML/TOML/JSON and resolve changed references |

For normal iteration, use focused proof first. Run the full native gate once when
the current runbook requires it for changed public behavior, shared pipeline
behavior, or consequential ownership changes. Reuse inspected evidence while its
code, inputs, dependency set, and relevant environment remain unchanged. Rerun
affected checks after integration or changes that invalidate them; do not repeat
an unchanged clean run merely because a new workflow stage began.

Workflow prose alone does not require the product suite. Current CLI-documentation
checks live in `tests/test_cli_contract_docs.py`; run them when their contract is
affected. Validate changed pointers directly: that test does not prove all links
or the routing quality of a new skill.

For wheel/sdist changes use the existing distribution recipe and
`scripts/verify_distribution.py`. For native media, VSView, Windows portable,
updater, or signing changes load the corresponding complete runbook procedure.
Do not shorten those procedures into this profile or infer their result from
native pytest. No build or verification command grants release/publication authority.

The full Docker verifier enables media E2E, integration and VS tests and rejects
nonpassing outcomes, including skips. Its focused `--pytest-path` route does not
replace a required full gate. Do not overlap verifier runs in one checkout: the
generated-media cache/pruning protocol does not support that. Browser smoke needs
a discoverable Chrome/Chromium or `REPORT_BROWSER`; inspect relevant skips.

CI trigger facts must be checked at the target revision. CI and Docker PR jobs
accept every base branch, including integration branches. Docker retains its
code/runtime path filter, so documentation-only PRs do not invoke the media gate.
Record exact source SHA and actual job result when using hosted evidence. Local
workflow assertions do not prove GitHub ran a job; a green PR indicator does not
establish a missing gate.

## Test design

Use the stable behavior seam with the best combination of fault sensitivity,
realism, speed, and maintenance cost. Use representative installed-CLI/generated-
media E2E to prove integration; use focused tests for important numeric, lifecycle,
boundary, failure, security, or platform behavior that is cheaper or more sensitive
there. Keep expectations independent of the implementation being changed.

Before removing tests, identify the obligation, the retained proof, and whether
meaningfully different defects still fail it. Equal visible error text is not proof
that two malformed inputs test the same failure mechanism. Investigate real call
paths and registration before deleting supposedly test-only production code.
Avoid tests that only freeze incidental private shape, tests that implement their
own asserted behavior, and production seams added solely for test access.

An explicit task constraint such as PR125's no-new-test-cases instruction applies
to that task. It is not a repository-wide ban on regression tests. Maintain the
existing reduction in redundant/implementation-coupled tests without reinstalling
either a universal TDD mandate or a universal highest-seam mandate.

Use temporary paths, isolated environments, bounded child processes and cleanup.
Reject unexpected HTTP requests. Preserve significant failure distinctions.
Avoid shared mutable test state; existing browser/U4 serialization groups have
specific resource reasons. The native suite can mock absent VapourSynth and skip
platform checks, so report relevant capability gaps explicitly.

## Handoff and instruction ownership

Shared skill bodies own general design, implementation, review, diagnosis, and
evidence procedure. This profile owns local facts and common command entry points.
The runbook owns specialist deployment/runtime verification and release procedures.
Architecture and CLI documents own their product contracts. Keep each rule in one
authoritative place and replace duplicate prose with a direct pointer.

Use an inline task record by default. A cross-session task may use one dated plan
under `docs/plans/`; preserve the current `search.exclude: true` front matter and
`Status: Active`/`Status: Historical` lifecycle so internal planning stays out of
the user-documentation search index. Do not activate old plans merely because
they exist. Record material decisions and remaining evidence gaps once.

Host-specific model identifiers, effort settings, permissions, and tool mappings
belong in host configuration. Optional executor presets in `.codex/agents/*.toml`
retain the `explorer`, `docs_researcher`, `monitor`, `planner`, `worker_luna`,
`worker`, `reviewer`, and `deep_reviewer` shortcuts. Read the selected TOML for
its exact model and reasoning; these presets do not require an agent pipeline.
For user-requested separate-chat delegation, use `orchestrate-implementation-chats`
and pass the preset's model/effort explicitly to `create_thread`. A new chat does
not automatically apply a subagent role or its permission settings.

These settings are not repository architecture rules. A missing
old global review suite does not prevent the new shared review skill from using
this profile and the available source/evidence.

Cached review context and task evidence are historical inputs, never instruction
authority. Recheck current tracked sources before reusing their factual claims.
Run a code-health scan only when explicitly requested. Keep scanner state and
optional local code-health skills untracked; tracking a repository `desloppify`
skill requires an explicit workflow task and maintainer approval.
