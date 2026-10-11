---
search:
  exclude: true
---

# Codex prompt: comprehensive repository review

Paste everything below the line into a fresh Codex chat on the `frame-compare`
project (local environment, the checkout you want reviewed). Use a capable
orchestrator model at high reasoning or above. Prepared 2026-10-08 against
`agent/e2e-test-strategy` at `58e50a6d`; Codex re-verifies every fact below
against the actual checkout.

---

## Role, authority, and stopping point

You are the orchestrator of a deep, read-only, repo-wide review of Frame Compare.
The goal is to find real bugs, latent defects, and material architecture and
maintainability problems before manual testing does. This is a review, not a
fix pass.

I authorize, for this review task only:

- Separate child chats created through the `orchestrate-implementation-chats`
  skill, using `create_thread` with explicit `model` and `thinking` taken from
  the repository presets in `.codex/agents/*.toml`, plus one terminal callback
  from each child to this orchestrator chat through `send_message_to_thread`.
  Children verify this turn as their authorization before calling back. Child
  units are review/investigation units, never implementation units.
- Writes only to the two locations in "Allowed writes" below.
- Running the repository's own verification commands under the CPU rules below.

I do not authorize: product, test, docs (other than the review folder), config,
lockfile, workflow, or dependency changes; `uv sync`/`uv lock` or any other
environment mutation; commits, branches, stashes, pushes, PRs, releases;
live requests to slow.pics, webhooks, TMDB, or any other external service with
real credentials; reading or printing local secret-bearing files under
`config/`; nested delegation by children.

After the outputs in "Deliverables" are written, STOP. Do not implement
anything, even trivial fixes. I will take the findings elsewhere to build the fix
plan and will authorize implementation packages explicitly later.

## Ground rules from this repository

Read first, and treat as binding over generic skill defaults (except where this
prompt explicitly widens the write boundary):

- `AGENTS.md`, `CLAUDE.md` (imports `AGENTS.md`), `.agents/project.md`
- `docs/ENGINEERING_RUNBOOK.md` (verification policy, Docker and Windows procedures)
- `docs/current-architecture.md`, `docs/current-cli-contract.md`
- `importlinter.ini`, `pyproject.toml`, `.github/workflows/*.yml`

Do not import rules from any other repository. Use the shared `review-code`,
`design-code`, and `verify-code` skills for their responsibilities. Use
`repo-production-review` as the backbone (census, evidence ledger, specialist
dimensions with wide scan plus deep samples, adversarial calibration via
`repo-review-evidence-calibration`), and `repo-production-remediation-plan` for
the remediation draft. Its read-only boundary is widened only by "Allowed writes".
Codanna is optional; a stale or absent index must not narrow scope.

Product obligations to judge against (from `AGENTS.md` / `.agents/project.md`):
runtime-free CLI help/version; typed sanitized errors and documented exit codes;
machine-clean JSON stdout with diagnostics on stderr; deterministic artifacts and
stable ordering; owned resource cleanup and respect for caller-owned injected
resources; explicit persistence boundaries and atomic writes; audio/video authority
before computed alignment can affect trims or computed-cache authority; a valid zero
offset distinct from unavailable evidence; manual confirmation keeps original
evidence and provenance; webhook transport isolated from the publishing client;
Docker and Windows portable are distinct support profiles whose proofs are not
interchangeable.

## Allowed writes

Let `<DATE>` be the date you start, as `YYYY-MM-DD`.

1. Throwaway probes and scratch output: `.tmp/comprehensive-review-<DATE>/`
   only. `.tmp/` is gitignored (`.gitignore` line `.tmp/`), and pytest's
   `testpaths = ["tests"]` keeps the normal suite from collecting it. Confirm
   with `git check-ignore -v .tmp/comprehensive-review-<DATE>/probes/x.py`
   before writing. Children write only under
   `.tmp/comprehensive-review-<DATE>/probes/<unit-id>/`.
2. Deliverables: `docs/reviews/comprehensive-review-<DATE>/` (orchestrator only).

At the end, `git status --porcelain` must show nothing except the new untracked
review folder. If anything else changed (including a tool rewriting a tracked
file), report it and restore nothing silently — tell me.

## Evidence rules

Run probes with the repo's own tooling, e.g.
`uv run --no-sync pytest -q -p no:cacheprovider .tmp/comprehensive-review-<DATE>/probes/<unit>/test_x.py`
or `uv run --no-sync python .tmp/.../probe.py`. Probes may import production
modules and reuse helpers from `tests/` (note `tests/conftest.py` fixtures do not
apply outside `tests/`). Use temporary directories for all generated data, bounded
child processes with cleanup, and local-only HTTP (localhost servers) for network
behavior. Never point a probe at a real service.

Label every finding with exactly one evidence label, plus the
`repo-production-review` type and S0–S4 severity:

- **CONFIRMED** — demonstrated by an executed probe/command whose output shows the
  failure, or an unambiguous doc-vs-behavior mismatch shown by running the CLI.
  Record the exact command, the probe path, and an output excerpt in the report
  (probes are not tracked, so the report must stand alone).
- **LIKELY** — the code path is traced end to end with file:line evidence, is
  reachable from a documented entry point, and no guard prevents it, but it was not
  executed (e.g. needs media, a platform, or a long run).
- **HYPOTHESIS** — a plausible mechanism that depends on runtime, platform,
  external-service, or timing behavior not available here. Each one must state the
  exact observation that would settle it: platform/host, command or UI steps,
  input, and what the passing vs failing outcome looks like.

Do not promote a finding because it "looks suspicious". Downgrade when tests,
guards, or documented constraints mitigate it. Prefer fewer, stronger findings.
Every material finding states: evidence, risk mechanism, impact, user-visible
journey affected, suggested verification, remediation direction, counterpoints.

## CPU and resource rules

Cheap work is allowed anywhere: reading, `rg`, `--help`/`version`, focused
single-file or single-selection pytest runs **without `-n`**, small synthetic probes,
and the static gates (`pyright --warnings`, `ruff check`, `ruff format --check`,
`bandit -c pyproject.toml -r src --severity-level medium`,
`lint-imports --config importlinter.ini`, `python scripts/generate_api_docs.py --check`,
`pytest -q tests/test_cli_contract_docs.py`).

CPU-heavy work runs **only in the orchestrator, once, at the end, after all child
evidence has been merged, serially, never overlapping**:

- full native suite: `uv run --no-sync pytest -q -n4 --dist loadgroup`
- CLI E2E with media opt-in and generated media; any real `frame-compare run` on
  generated media
- Docker media gate: `bash tools/verify_docker_integration.sh`
  (or the focused `--pytest-path` form if that is all a finding needs) — never
  concurrently with another verifier or E2E media run; they share the generated-media cache
- Docker streaming-resource proof (runbook command with
  `FRAME_COMPARE_CONTINUOUS_ALIGNMENT_RESOURCES=1`) — only if a finding concerns
  whole-track memory bounds, admitted lag, or collector cleanup
- report browser smoke: `uv run --no-sync pytest -q tests/browser/test_report_browser_smoke.py`
- strict docs build `uv run --no-sync zensical build --clean --strict`, only if
  the docs group is already installed (do not sync); it checks that the review
  folder itself does not break the site build

Children propose heavy runs in their reports; the orchestrator decides which to
run. Report every skip and its reason; a skip, a mocked VapourSynth, or an absent
CI job is never a pass. The local macOS host may lack L-SMASH-Works, FFMS2, and
vs-placebo — check with `frame-compare doctor` and route media-tier evidence
through Docker. Physical Windows, GPU, visible GUI/X11, signing, and live-service
behavior go to the "needs physical/live observation" list.

## Phase 0 — Baseline (orchestrator)

Record branch, `HEAD` SHA, `git status --porcelain` (must start clean),
tool versions (`uv`, Python, Docker availability, browser availability), and
`frame-compare doctor` capability summary. Read the ground-rule documents.

## Phase 1 — Census and defect-class derivation (orchestrator)

Build the `repo-production-review` census (tracked inventory, owners, entry points,
hotspots, largest files, CI jobs, release surfaces, exclusions such as
`third_party/`, generated output, and `site/`).

Then derive the **known defect classes** yourself from this repository's history:
`git log` (all `fix`, `test`, and revert commits with their bodies; history begins
at the v0.1.0 import on 2026-07-31), `CHANGELOG.md` (all Fixed/Security/Upgrade
notes), `docs/DECISIONS.md`, `docs/TODO.md`, `docs/release-evidence/`,
`docs/reviews/` (currently empty), and the plans under `docs/plans/`
(especially `2026-10-04-assessment-remediation.md`,
`2026-10-07-dependency-refresh-windows10-handoff.md`, and the defect notes in
`2026-09-30-e2e-test-strategy.md`). The seed list below was derived the same way;
verify each class against the cited commits, correct it, merge or split classes
where the evidence says so, and **add any class it missed** (I am not sure the seed
is complete — treat discovering missing classes as part of the job). For every
class, hunt the whole codebase for siblings of the mechanism, not just the fixed
instances, and record where you searched even when nothing was found.

### Seed defect classes

| ID | Class | Fixed examples | Sibling hunt |
| --- | --- | --- | --- |
| K1 | Alignment authority leak: provisional/unavailable/cached/manual evidence reaching trims or computed cache; zero offset treated as absent; provenance lost | f46752ce, 2bbe7900, 6acebb99, 5e75900c, d7fbb2b8, 80598c86 | Every consumer/writer of offsets: `phase_alignment`, reuse cache, previous offsets, manual overrides, VSView result acceptance; truthiness/`or 0` on optional offsets |
| K2 | Stale source identity between preparation and commit (TOCTOU) | 2bbe7900, bfa369ad | Analysis/probe/index caches, render inputs, VSView sessions, run records, report |
| K3 | Presentation diverges from the authoritative decision | ~25 review-target fixes 2026-09-26/27, 459865ea, 9aae9f52, c0fb947d, a37ddbba | Terminal output, JSON, run record, report payload, VSView panel, slow.pics labels — anything re-deriving facts instead of reading one projection |
| K4 | Persisted/external input not validated at its owner; invalid user config vs recoverable cache conflated | 0348e825, 2bbe7900, 0.5.0 schema fix | TMDB cache, history/run records, presets, `manual_overrides.toml`, VSView sidecars, L-SMASH indexes, browser-local report state, generated config |
| K5 | Status reported from prediction instead of the actual operation | 0348e825 | Dry-run vs real run, doctor presence-vs-function, cache hit/miss, progress, success summaries |
| K6 | Child-process/handle lifetime: unreaped children, unbounded `Popen` exit, pipes closed before readers drain, cleanup failure masked | 78c38b6e, 1c99e4b4, 94464b85, 71d5bd8b, b9919607 | Every `subprocess` use (`utils/subproc.py`, render batch FFmpeg, ffprobe, doctor, launcher, tonemap, PowerShell/updater), native VS handles |
| K7 | Cancellation and first-failure semantics | 32c60a24, 79f25999, 635c14e3, 233b8c6c | `gather`/TaskGroup/`to_thread`, `runner` sync→async bridge, KeyboardInterrupt in each phase, cancel exit codes |
| K8 | Unbounded operations (time/memory/size) | 3ee93554, c8c03a96, aeb67e4d, 474f8870 | HTTP timeouts, blocking resolution, unbounded reads/JSON of external size, `communicate()` without deadline, archive extraction |
| K9 | Secret/credential leakage | e7b457dd, 681ea6b3, 569b81c9, 6d8fb99e | Logs, JSON errors, chained exceptions with URLs/tokens, doctor output, run records, report payload, webhook/slow.pics errors, child environments |
| K10 | Child-interpreter import/environment isolation | 40ef773d, e04aa81b, 0a1dd975, portable `._pth` | Every child Python launch; inherited `PYTHONPATH`, cwd, user site |
| K11 | CLI option combinations validated late or inconsistently per mode | 33dbc6e7 | All flag pairs; JSON mode × prompts; `--dry-run` × `--write-config`; validation before run-folder reservation |
| K12 | Producer/verifier drift: copy, module paths, links pinned in tools/proofs | 2bbbb403, stale `vsview.main` (10-07 handoff), 5fc065a4 | `tools/`, `scripts/`, `tools/windows_portable/`, `Dockerfile`, workflows; API renames from the 10-07 dependency refresh (VSView 0.12, Cyclopts, vspackrgb 2.0) |
| K13 | Report viewer async races and unsafe interpolation | 5c9c3de1, d1bf9d8c | Other deferred loads/timers in `viewer.js`, `lens.js`, `viewport.js`; escaping of filenames, labels, metadata; browser-local state validation |
| K14 | Sign convention, frame-domain, and retiming errors | 0.5.0 sign fix, 5e75900c, 853a5e21 | Trim composition, comparison vs source frame translation, negative/zero/retimed cases, frame numbers in report and slow.pics |
| K15 | Exception taxonomy and non-finite/degenerate numerics | 7bfed695, DECISIONS 2026-02-07 (FC-2009 vs FC-2001) | Broad `except ValueError`/`Exception`, error-code → exit-code mapping, NaN/zero FPS, empty windows |
| K16 | Platform-specific behavior | 57d24df5, 982e7e27, `render/naming` path bounds, 9401f471 | `open()` without encoding, Windows replace/lock semantics (`utils/file_lock.py`, `atomic_write.py`), signals, case-insensitive collisions, path length |
| K17 | Partial failure discards sibling results (or vice versa) | 0.6.0 TMDB variant fix, 6d8fb99e | Render batches, publishing, metadata merges (HDR FFprobe merge) |
| K18 | Verification blind spots | 2aed9636, 681ea6b3, 9c1fbc59, 2835f74d | Skips counted as passes, mocked VS hiding failures, ambient env/git config leakage into tests, CI path/branch filters vs runtime-affecting paths |
| K19 | Release and update integrity | 474f8870, 0.6.0 release-body fix | `release.yml`, `scripts/validate_release_contract.py`, `install.ps1`/`install.cmd`, updater manifest/rollback, action pins |
| K20 | Guard assertions lost during test slimming | the "restore trimmed assertions" lanes of 2026-10-02 | Remaining user-visible values and failure distinctions with no surviving proof after the O1–O4/lane trims |

## Phase 2 — Parallel review units (child chats)

Dispatch child chats per `orchestrate-implementation-chats`: resolve this chat's
real thread/host IDs, cite this turn as the authorization, read each selected
preset TOML from the checkout and pass its `model` as `model` and
`model_reasoning_effort` as `thinking`, use the local environment on this
checkout (no worktrees needed — children do not edit tracked files), and record a
dispatch map. Respect actual host concurrency. Suggested units (merge or split
when context cost warrants; every class, journey, and dimension must be owned):

| Unit | Preset | Scope |
| --- | --- | --- |
| R1 Alignment authority & domains | `explorer` | K1, K2, K3, K14; journeys J4, J5; architecture A1, A2 |
| R2 Lifecycle, cancellation, bounds | `explorer` | K6, K7, K8, K10, K17; journey J9; webhook/DNS, VSView adapter, render batch, audio streaming |
| R3 Persistence, config, CLI surface | `explorer` | K4, K5, K11, K9, K15; journeys J1–J3, J7, J8 |
| R4 Report viewer | `explorer` | K13; journey J10; viewer/lens/viewport JS and the Python report renderer/payload |
| R5 Platform, packaging, release, CI | `explorer` | K12, K16, K18, K19; journeys J11, J12 |
| R6 Docs-vs-code contract | `explorer` | Phase 4 below |
| R7 Architecture & maintainability | `reviewer` | Phase 5 below, applying `design-code` and `review-code` |
| R8 Official external behavior | `docs_researcher` | Only specific questions a finding depends on (e.g. Windows `os.replace` semantics, asyncio cancellation, httpx timeouts, Qt/VSView API, GitHub Actions trigger rules) |
| V1… Validation | `reviewer`; `deep_reviewer` only for disputed S0/S1 | Phase 6 below |

Each child packet must be self-contained (handoff template in the skill): source
identity (branch, HEAD), this prompt's ground rules, the relevant specialist skill
names with their actual paths, the seed classes/journeys it owns, the CPU rules,
its probe directory, the evidence labels, and the `repo-production-review` sidecar
output format (scope reviewed, wide scan, files inspected/not inspected,
per-dimension coverage with no-finding notes, candidate findings with evidence,
limits). Children: read-only on tracked files, probes only in their own
directory, no heavy runs, no nested delegation, one terminal callback, then a
final report in their own chat. When nothing useful remains for you, end your
turn and let callbacks resume you; do not poll.

## Phase 3 — End-to-end journeys

Derive and refine these from `README.md`, `docs/guides/`, `docs/getting-started/`,
`docs/reference/`, `docs/current-cli-contract.md`, `docs/current-architecture.md`,
and the actual CLI/config surface. For each journey, trace the code path, list
the existing proof (`tests/e2e/`, `tests/integration/`, `tests/browser/`, Docker
verifier, runbook procedures), and record gaps and findings.

- **J1 First comparison per route** — `wizard` → `doctor` → `run --dry-run` →
  `run` → `report.html`, on native, Docker, and Windows portable.
- **J2 Repeat comparisons** — warm caches, `--from-cache-only`, `--no-cache`;
  `history list` / `history open`; `preset list` / `apply` / `save`;
  `--write-config` persistence; `version` and help without the native runtime.
- **J3 Config variants** — user/random-only selection (analyze skipped);
  `analysis.performance_mode` quality vs performance; `active_rect_detection = auto`;
  `[runtime] memory_limit_mb`; three or more sources and an explicit reference;
  source overrides and labels; `match_fps` / `effective_fps` retiming; FFmpeg-only
  vs VapourSynth rendering; HDR tonemap presets; external `paths.generated_dir`;
  rejection of removed `[audio_alignment]` keys and other unknown keys.
- **J4 Alignment** — trusted automatic offset applied; provisional/competing/
  unresolved not applied; valid zero offset; previous-offset reuse
  `disabled`/`prompt`/`always`; manual overrides; VSView review confirm, keep-current,
  cancel, interrupt; source changed during preparation or review.
- **J5 Run-only full-window retry** consent path and its fatal retry-once boundary.
- **J6 Publishing** — slow.pics upload, `confirm_upload_after_report` ordering and
  decline, shortcut policy; webhook delivery including DNS deadline, repeated
  cancellation, uncertain delivery; TMDB lookup and its durable cache.
- **J7 Output modes** — JSON stdout cleanliness and schema, human progress on
  stderr, exit codes, non-TTY and non-interactive prompt behavior.
- **J8 Failure paths** — missing or partial runtime (doctor guidance), invalid or
  secret-bearing config, corrupted caches, unreadable or degenerate media, unwritable
  or full generated dir, too few clips, selection failure, render failure, HDR
  without VapourSynth (FC-2009).
- **J9 Cancellation** — Ctrl+C (single and repeated) in probe, analyze, align
  (collection and VSView), render, metadata, publish/webhook, report; child cleanup,
  state of partial run folders and run records, exit codes.
- **J10 Report viewer** — offline open, slider/overlay/diff/blink/grid, lens,
  filmstrip, keyboard and focus, review state persistence and the v1.1→v1.2 state
  reset, hostile or very long filenames/labels, Windows browser path limits,
  auto-open ownership.
- **J11 Platforms** — Windows portable install, code-only update, refusal across
  runtime fingerprints, rollback, uninstall, `._pth` startup; Docker default
  headless, `gpu-nvidia`, `gui-linux`; native installs with partial plugins.
- **J12 Packaging and release** — wheel/sdist contents (`scripts/verify_distribution.py`),
  installed CLI without native deps, Release Please → guarded `release.yml`,
  Windows build/sign workflows, docs site, API-doc drift.

## Phase 4 — Doc-vs-code contract check

Compare `docs/current-cli-contract.md`, `README.md`, `docs/guides/*.md`,
`docs/getting-started/*.md`, `docs/reference/*.md`, `docs/supported-media-runtime.md`,
`docs/windows-portable.md`, and `INSTALL-WINDOWS.md` against actual behavior: run
`frame-compare --help`, each subcommand's `--help`, `version`, config schema
(`config/schema_models.py` and friends), error codes and exit mapping, JSON output
shapes, persistence paths and schemas, and the tests that claim to prove them.
First determine what `tests/test_cli_contract_docs.py` already enforces, then focus
on what it does not. Classify each mismatch as code bug, doc bug, or undecided
(→ "needs my decision"). Cheap CLI invocations are fine; anything needing a real
media run is deferred to the orchestrator's end-of-review runs.

## Phase 5 — Architecture and maintainability

Treat this as a first-class dimension, not an afterthought. Apply `design-code`
(architecture assessment: trace representative operations, name concrete caller
burden, duplicated policy, invalid states, misplaced ownership) and `review-code`'s
design-and-standards lens, plus `repo-review-architecture-boundaries` and
`repo-review-maintainability-ai-debt`. Recommend retaining a design where no
concrete burden is found. Seed targets to verify, not conclusions:

- **A1** Alignment subsystem: the highest-churn area (`services/alignment*.py`,
  `utils/alignment_evidence.py`, `utils/alignment_review_projection.py`,
  `orchestration/phase_alignment.py`, `vsview/alignment_review_*`). Does one owner
  hold each policy, or do callers re-check authority/state?
- **A2** Presentation/projection duplication — the structural cause behind K3's
  long fix series. Is there one projection every surface reads?
- **A3** Large mixed-responsibility modules: `services/report/assets/viewer.js`
  (~2.2k lines), `cli/run_command.py`, `cli/output.py`, `orchestration/preparation.py`,
  `services/run_result_record.py`, `services/publishers.py`, `orchestration/doctor_checks.py`.
- **A4** Types that permit invalid states (boolean/optional combinations encoding
  authority, cache disposition, or phase state).
- **A5** Ad hoc environment reads outside the config owner; import-contract erosion
  or suppressions in `importlinter.ini`.
- **A6** Error taxonomy coherence across `errors.py`, `error_*.py`, and per-package
  `errors.py` modules.
- **A7** Dead, test-only, or compatibility-scaffolding production code with no real
  consumer (single-user project; old paths should be deleted rather than shimmed).
- **A8** Leftover tooling such as `tools/old_consensus.py` and `tools/old_corr.py`.

Report maintainability findings with the concrete burden (which callers, which
repeated fixes, which invalid state), the owner that should hold the policy, and
the strongest alternative. File size alone is not a finding.

## Phase 6 — Validation and calibration (orchestrator + validation units)

Merge and deduplicate child candidates into the evidence ledger. Directly re-check
every S0–S2 candidate and every high-risk "no finding" claim yourself. Send disputed
or high-consequence candidates to a `reviewer` validation chat (or `deep_reviewer`
for disputed S0/S1) with the reviewer packet from `repo-production-review`. Run
`repo-review-evidence-calibration`. Unsupported child claims are not findings.

## Phase 7 — End-of-review heavy runs (orchestrator only)

Run the static gates, then the heavy runs from "CPU and resource rules" that the
merged findings actually need, serially, once. Use them to promote LIKELY to
CONFIRMED (or reject candidates), and to record the baseline health of the checkout.
Record exact commands, durations, pass/fail/skip counts, and every skip reason.

## Deliverables

Write to `docs/reviews/comprehensive-review-<DATE>/`. Every file starts with the
same front matter as `docs/plans/` files:

```yaml
---
search:
  exclude: true
---
```

Reference source files as literal code spans (`src/frame_compare/...:123`), never
as Markdown links: paths outside `docs/` break the strict site build. Never include
secrets, token-bearing URLs, private media names, or personal diagnostics.

1. **`REPORT.md`** — the `repo-production-review` report template, extended with:
   - Baseline (HEAD, tools, capabilities, commands run and not run, skips).
   - Defect-class table: each class (seed and newly discovered) with its derivation
     evidence, where siblings were searched, and the findings it produced or an
     explicit "searched, none found" note.
   - Journey matrix: J1–J12 (and any you add) × existing proof × gaps × findings.
   - Doc-vs-code contract section.
   - Architecture and maintainability section.
   - Findings, each with ID `F-###`, evidence label, type, severity, confidence,
     classes/journeys, evidence (file:line, command, probe path, output excerpt),
     mechanism, impact, suggested verification, remediation direction, counterpoints.
   - Probe index: probe path → purpose → command → result.
2. **`REMEDIATION.md`** — produced with `repo-production-remediation-plan` as a
   **draft package proposal** for my review. Treat CONFIRMED and LIKELY findings
   that survived calibration as provisionally accepted; park HYPOTHESIS and
   insufficient-data items. Group by implementation seam; for each package give
   findings, goal, scope, out of scope, files/symbols, approach, verification gate
   (focused proof, then which heavy gates the controller runs after integration),
   rollback notes, dependencies, and which items could run in parallel with
   disjoint ownership. Nothing in it is approved.
3. **`NEEDS-DECISION.md`** — product, contract, or design questions only I can
   answer (e.g. doc-vs-code mismatches where intent is unclear, features you think
   are unsound, behavior changes a fix would imply), each with options and your
   recommendation.
4. **`NEEDS-OBSERVATION.md`** — every HYPOTHESIS and every acceptance gap needing
   a physical host, GPU, visible GUI, Windows portable bundle, signing context, or
   live service: the exact steps, environment, input, and pass/fail criteria.

## Final message, then stop

Reply with: HEAD reviewed; counts by severity and evidence label; the top findings
(one line each); new defect classes you added to the seed; heavy runs executed and
their results; child chats used (preset, model/effort, outcome); the paths of the
four files; and confirmation that `git status --porcelain` shows only the new
review folder. Then stop and wait. Do not begin any remediation.
