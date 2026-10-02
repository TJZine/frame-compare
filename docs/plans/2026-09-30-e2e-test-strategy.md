---
search:
  exclude: true
---

Status: Active
Scope: Make real-CLI end-to-end tests the primary proof for Frame Compare features, prune unit tests that E2E, retained integration tests or a single retained owner per behavior already prove (S10), consolidate and type-check the rest, and change the repository rules so low-value unit tests stop being added.
Owner: Claude controller session (planning, adjudication, verification); Codex executes units A, B, B2, C, D and E through `.handoff/` prompts. Branch `agent/e2e-test-strategy`.

# E2E-first test strategy and unit-test pruning

## Baseline

- Main checkout `/Users/tristan/Software/frame-compare`, branch
  `agent/e2e-test-strategy`. It was created from `agent/audio-alignment-parity` at
  `57080b24`; its first commit is `7eea6921` (`ci: drop the coverage floor`). No push,
  PR, merge, release or signing is authorized by this plan.
- Authorities: `AGENTS.md`, `docs/ENGINEERING_RUNBOOK.md`,
  `docs/current-architecture.md`, `docs/current-cli-contract.md`, `importlinter.ini`,
  `pyproject.toml`. Where this plan conflicts with a test-writing rule in those
  documents, this plan governs for its scope, and A4 updates the documents.
- The coverage floor is already gone (`7eea6921`): `fail_under` is removed, CI runs
  plain `pytest -q`, and `[tool.coverage]` stays for local use.
- Inventory at `57080b24`: 258 test files, 2,708 test functions and about 90.7k
  test lines, against about 47k source lines. By area:

  | Area | Files | Tests | Lines |
  | --- | ---: | ---: | ---: |
  | services | 50 | 687 | 25,141 |
  | orchestration | 57 | 549 | 20,750 |
  | cli | 18 | 260 | 8,360 |
  | windows_portable | 13 | 139 | 5,517 |
  | render | 14 | 184 | 4,581 |
  | vsview | 9 | 115 | 4,220 |
  | integration | 12 | 52 | 4,062 |
  | analysis | 17 | 163 | 3,958 |
  | vs | 16 | 170 | 3,681 |
  | workflows | 14 | 77 | 2,804 |
  | root `tests/*.py` | 14 | 76 | 2,500 |
  | config | 9 | 112 | 1,745 |
  | utils | 10 | 92 | 1,415 |
  | browser, scripts, manual, e2e | 5 | 32 | 1,981 |

- Runtime facts:
  - **CI's `test` job** has no VapourSynth: `tests/conftest.py` substitutes a
    `MagicMock`, and real-VS modules skip themselves.
  - **On the maintainer's Mac (arm64)**, real VapourSynth imports but L-SMASH
    (`lsmas`) is missing, so every test that decodes media runs in Docker.
  - **`windows-portable-build.yml`** also runs the full `pytest -q` on Windows with
    `--extra vsview`, which installs VapourSynth and `vapoursynth-lsmas` there. The
    CLI tier (S2) therefore runs on Windows as well.
  - **Docker** (`tools/verify_docker_integration.sh`) ran `tests/integration/ tests/vs/`
    in the `frame-compare-test` image before S5. It then proves the production
    image with one real `frame-compare run` on two FFmpeg-generated clips, and with
    `doctor --json`.
    - The test service ran as the image's `framecompare` user (UID 1000), and the
      production proof as the host UID (`FRAME_COMPARE_HOST_UID`).
    - Since S5 (`fe128841`), the test service also runs `tests/e2e/`, as the host
      UID.
    - The hosted `docker-integration.yml` job runs on amd64. Before S5 it ran only
      for a path-filtered subset of changes; S5 widened the filter. A recent hosted
      run's verification step took about 2 minutes.
    - The image declares the media runtime through environment variables
      (`FRAME_COMPARE_MEDIA_RUNTIME_FINGERPRINT`, `FRAME_COMPARE_RUNTIME_KIND`,
      `FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED`, `FRAME_COMPARE_FFMPEG_EXECUTABLE`,
      `FRAME_COMPARE_FFPROBE_EXECUTABLE`). Child processes must inherit them.
  - **Real media** in `comparison_videos/` is gitignored and never available to tests
    or CI.
  - **Real-media alignment acceptance** already exists in-process in
    `tests/integration/test_alignment_u4_acceptance.py`, using generated fixtures.
  - **slow.pics and TMDB URLs are hard-coded constants**
    (`services/publishers.py`, `services/tmdb_lookup.py`), so no E2E can reach a
    local stub without a test-only production seam.
  - **There are no built-in presets.** `preset list` reads only
    `<root>/config/presets/*.toml`.
- Where the observable facts live:
  - `run --json` success: `success`, `screenshots_dir`, `slowpics_url`,
    `report_path`, `frame_count`, `clips_processed`, `duration_seconds`,
    `cache_hit`, `errors` (`cli/run_command.py`, `handle_json_output`).
  - `<run>/run_result.toml`: `status`, `clip_count`, `selected_frame_count`,
    `warning_count`, `metrics_cache_status` (`hit`, `miss` or `skipped`), and
    volatile timing fields.
  - The report payload, embedded in `report.html` as
    `<script type="application/json" id="report-data">`:
    - `frames[].number`, `frames[].category`;
    - `frames[].images[].clip` and `.source_frame`;
    - the tonemap `preset` and `target_nits`.

    It is the only place the selected frames, per-clip source frames and applied
    tonemap settings appear.
  - An alignment refusal reason appears only on stderr, as the JSON event
    `audio_alignment_requires_review` (contract, "Output Modes").
- Native baseline, in the execution record: 3,643 passed, 81 skipped, 127 s.

## Goal and non-goals

**Goal:** any credible feature regression fails either an E2E test that drives the
real `frame-compare` executable against generated media and leaves an artifact
someone can inspect, or the single retained owner test for that behavior (S10).
The unit suite shrinks to one owner per user-visible behavior, plus the boundary,
failure, contract, network, security and platform cases E2E can't reach. The
repository rules then keep it that way.

Non-goals:
- product behavior changes, except deleting production code whose only callers are
  tests (S7) and the maintainer-authorized fix in S9;
- new dependencies;
- coverage measurement in CI;
- live network tests;
- VSView GUI automation;
- changes to the Windows portable hosted route beyond the CLI tier running there;
- rewriting the report browser smoke (`tests/browser/`), which is already an E2E of
  the report viewer;
- a `doctor` media E2E, because the verify script already proves `doctor --json`
  in Docker.

## Strategy decisions

**S1. What counts as E2E.**
- An E2E test runs the installed console entry point as a child process:
  `frame-compare.exe` or `frame-compare` next to `sys.executable`, falling back to
  `shutil.which("frame-compare")`. In Docker the script is in
  `/home/framecompare/.local/bin`, found through `PATH`.
- The child runs with an explicit timeout. It **inherits `os.environ`** minus only
  config-override keys (`FRAME_COMPARE_<SECTION>__*`, the schema's `env_prefix` with
  the `__` delimiter), plus `NO_COLOR=1` and `PYTHONUTF8=1`. Runtime declarations,
  `PATH`, `LD_LIBRARY_PATH` and `VAPOURSYNTH_EXTRA_PLUGIN_PATH` pass through
  unchanged.
- Each test uses an isolated `--root` workspace under `tmp_path`, with a config file
  the test writes. Media is generated by FFmpeg `lavfi`, and copied into each
  workspace with `shutil.copy2`, because L-SMASH writes `.lwi` files next to the
  media.
- Test files in `tests/e2e/` never import `frame_compare`, never monkeypatch or mock,
  and read only exit codes, stdout, stderr and produced files (`json`, `tomllib`,
  `html.parser` or a regex for the `report-data` script, PIL).
- Every scenario sets `slowpics.auto_upload = false`, `tmdb.enabled = false` and
  `report.auto_open = false`, and passes `--skip-metadata --no-upload` to `run`. E2E
  never touches the network.
- No `skip`, `skipif` or `xfail` appears in `tests/e2e/` outside the single
  media-tier gate fixture.

**S2. Two tiers in one directory, `tests/e2e/`.**
- **CLI tier:** needs no media runtime. It runs natively, in CI's `test` job, on the
  Windows portable build job and in Docker.
- **Media tier:** marked `e2e` and `vs_required`. It runs **only** when
  `FRAME_COMPARE_E2E_REQUIRE_MEDIA=1`; otherwise the gate fixture skips it.
  - The gate does no runtime detection. With the variable set, a missing runtime
    fails the tests, it never skips them.
  - Only the Docker verify script sets the variable, so expected values are always
    produced by the pinned Docker runtime.
  - The variable is read only by test code. It is not a production seam.

**S3. Artifacts.**
- Each scenario writes `<artifact_root>/<scenario_id>/` containing `command.txt` (the
  argv, with the workspace path replaced by `<root>`), `stdout.txt`, `stderr.txt`,
  a copy of the run folder when one exists, and `summary.json`.
- `summary.json` has sorted keys, a 2-space indent and a trailing newline. It holds
  **exactly the required fields listed for that scenario in S4**: no more, no fewer.
  - It never contains timestamps, durations, absolute paths, tool versions,
    fingerprints or floating-point values. Paths are reduced to names relative to
    the run folder.
- The test compares `summary.json` for equality against an expected dictionary
  literal in the test. Changing the expected output then means editing the test,
  which shows up in review.
- `artifact_root` is `$FRAME_COMPARE_E2E_ARTIFACTS` when set, otherwise a `tmp_path`
  subdirectory. A scenario replaces its own directory completely.
  - The verify script removes `generated/e2e/` before the run, sets the variable to
    `/workspace/generated/e2e`, and hosted CI uploads that directory with the
    repository's existing pinned `actions/upload-artifact` SHA, `if: always()`.
- **Repeatability is required.** Two consecutive Docker runs produce byte-identical
  `summary.json` files, checked once in A5. Fixtures use unambiguous content (flat
  dark and bright segments, strong motion edges), so metric-ranked selection is
  stable across arm64 and amd64.
  - The first hosted amd64 run is the cross-architecture confirmation. A mismatch
    there is fixed in the fixtures, never by loosening the expected values.
- There is no regeneration switch, golden-file directory or snapshot library.

**S4. Scenario catalog.** Each ID is one test function, or one parametrized
function where noted. The implementer takes expected values from
`docs/current-cli-contract.md` and the sources in Baseline, "Where the observable
facts live". A required fact the product doesn't expose is a `blocked` message,
not a new field.

CLI tier:

- **E1, version and help**, in `tests/e2e/test_cli_version.py`. The filename stays,
  because the contract names it.
  - `version` prints `frame-compare <version>`. The expected version is read from
    `pyproject.toml` with `tomllib`, not from package metadata.
  - Running with no arguments prints the usage text and exits 0.
  - Summary:
    - for `version`: `exit_code` and the full `stdout`;
    - for no arguments: `exit_code`, whether `Usage:` appears, and the sorted
      command names.

    Never the full help text: it is a snapshot, and its layout depends on terminal
    width.
- **E2, errors.** Parametrized; each case runs with `--json`:
  - a missing input directory;
  - an invalid config value;
  - `--no-cache` together with `--from-cache-only`;
  - `--dry-run` together with `--write-config`;
  - a reference selector that matches no file;
  - a path that escapes the root.

  Summary for each case: `exit_code`, the parsed payload's `success`, `error.code`
  and `error.name`, which stream carried it, and whether the other stream was empty.
  The payload shape is
  `{"success": false, "error": {code, name, message, hint?, details?}}`.
- **E3, `run --dry-run --json`.**
  - Zero-byte placeholder files with supported extensions are allowed, because
    dry-run does no probing.
  - Summary: the sorted top-level keys, `reference.resolved_filename`,
    `input.source_filenames`, the `selection` object, and a sorted listing of the
    workspace before and after, which must be equal.
- **E4, config persistence.**
  1. Run `run --write-config` with overrides.
  2. `run --dry-run --json` shows those values.
  3. `preset save p1`, then `preset list` prints `p1`.
  4. Change the config, then `preset apply p1`.
  5. `run --dry-run --json` shows the saved values restored.

  Summary: exit codes for each step, the `selection` object after steps 2 and 5, and
  the preset list.
- **E5, `history list --json` with no runs.** Summary: `exit_code` and the parsed
  object (`{"runs": []}`).

Media tier (Docker only):

- **M1, VapourSynth render path.** Two 8-bit SDR clips,
  `screenshots.use_ffmpeg = false`, report enabled, `dark_frame_count` and
  `bright_frame_count` above 0.
  - Summary fields:
    - from the JSON: `success`, `frame_count`, `clips_processed`, `cache_hit`,
      `errors`;
    - from `run_result.toml`: `status`, `clip_count`, `selected_frame_count`,
      `metrics_cache_status`;
    - from the report payload: `frames` as `[number, category, [[clip,
      source_frame], ...]]`;
    - the sorted screenshot file names, each with its PNG mode and size.
- **M2, FFmpeg screenshot path.** The same inputs with `use_ffmpeg = true`. Same
  fields as M1.
- **M3, cache lifecycle and history.** Each step records `exit_code`,
  `metrics_cache_status` and the report's frame numbers.
  1. The first run is a `miss`.
  2. A second identical run is a `hit`, with the same frames.
  3. `--from-cache-only` is a `hit`.
  4. `--no-cache` is a `miss`.
  5. Truncate the `.compframes` payload so the loader reports `corrupted`, then run
     `--from-cache-only`. It fails; record `exit_code` and the JSON `error.code` and
     `error.name` that `CacheCorruptionError` (`orchestration/preparation.py`) maps
     to, and confirm on the
     filesystem that no new run folder was created (contract, "Cache Mode
     Semantics").
  6. `history list --json` lists the runs. Summarize them as
     `sorted([name, status, report_available])`, because entries sort by
     second-precision timestamps and can tie.
- **M4, HDR tonemap.**
  - A 10-bit PQ/BT.2020 fixture, generated with the verify script's HDR recipe, is
    compared with an SDR clip, with tonemapping enabled at a fixed preset and
    target.
  - Summary: M1's fields, plus the payload's tonemap `preset` and `target_nits`, and
    each PNG's mode (which must be 8-bit RGB).
- **M5, audio alignment applies a known offset.**
  - The comparison clip carries the reference program delayed by a whole number of
    frames N the test chooses. Every frame shows a frame-identifying pattern: blocks
    whose luma encodes the frame number, decodable by averaging pixels.
  - Summary: `exit_code`, `status`, the per-frame `source_frame` delta between the
    clips (equal to N for every frame), and the decoded pattern id of each
    screenshot (equal across clips for every frame).
- **M6, audio alignment refuses.** The comparison clip has unrelated audio.
  - The fixture must produce an alignment decision, so the event's
    `decision_state` is not `unavailable`.
  - Summary: `exit_code`, `status`, the `reason` and `decision_state` of the
    `audio_alignment_requires_review` event, and the per-frame `source_frame` delta
    (0).
  - Only stderr lines that parse as JSON with
    `event == "audio_alignment_requires_review"` count. stderr also carries native
    plugin text.
  - Files under `alignment_diagnostics/` are never evidence for M5 or M6.

**S5. CI and Docker wiring.**
- `docker-integration.yml` runs on every pull request to `main`, `pre-release` and
  `staging` that touches:
  - `src/**`, `tests/**`, `pyproject.toml`, `uv.lock`;
  - `Dockerfile`, `docker-compose*.yml`, `tools/verify_docker_*.sh`;
  - the workflow file itself.

  This replaces the file-by-file list.
- **Verify script, test container.**
  - It runs as the host UID/GID with `HOME=/tmp/framecompare-home` and
    `PYTHONUSERBASE=/home/framecompare/.local`, mirroring `frame-compare-run`, so it
    can write the bind-mounted `generated/`.
  - It passes `FRAME_COMPARE_E2E_REQUIRE_MEDIA=1` and
    `FRAME_COMPARE_E2E_ARTIFACTS=/workspace/generated/e2e`.
  - The default pytest paths become `tests/e2e/ tests/integration/ tests/vs/`,
    keeping the streaming-resources ignore.
  - Its skip check also rejects `xfailed` and `xpassed`.
- The production-image proof section is unchanged.
- The hosted job uploads `generated/e2e` (S3).
- Tests that pin the old wiring change with it:
  - assertions that pin old values are updated;
  - assertions that the job must *not* trigger for `services/**`,
    `orchestration/**` or render phases are deleted, because S5 inverts them.

  This covers `tests/workflows/test_docker_integration_contract.py` and
  `tests/vs/test_runtime_contract.py`. The runbook sentence saying the Docker job
  "need not trigger for every relevant owner" is replaced.

**S6. Deletion bar (unit B; S10 governs units B2, C and D).** Each test belongs to exactly one cluster; a
cluster is the set of tests guarding the same behavior. Every cluster gets one
classification:
- **`junk:<pattern>`** matches one of these patterns:
  - no assertion, or an assertion that can't fail;
  - self-comparison, or an expected value computed by the code under test;
  - a copied inventory, manifest, export list or constant, where the copy isn't a
    second, independently maintained source;
  - a source, import or string grep that doesn't guard a user-facing key, byte or
    path;
  - a private call-shape or call-order test, where the order isn't observable;
  - a mock that implements the behavior being asserted;
  - a duplicate invocation of a contract another retained test already proves;
  - a test whose only purpose is keeping a test-only export, wrapper or hook alive.

  A test whose name or docstring promises more than its input exercises gets
  renamed, not deleted, unless it also matches a pattern above.
- **`covered:<test ids>`**: every behavior the cluster asserts makes a named E2E
  (E*/M*) or always-keep test (listed below) fail. Proven by C2.
- **`keep:<category>`**: the cluster guards something E2E can't reach reliably.
  Categories:
  - `failure-mode`: subprocess timeout or kill, malformed external data, partial or
    atomic writes, cancellation or cleanup;
  - `network`: slow.pics and TMDB through `MockTransport` or RESPX;
  - `security`: path escape, secret redaction, signature verification;
  - `numeric`: estimator or selection math whose edge cases E2E fixtures can't pin
    cheaply, such as negative offsets, retiming, VFR or `match_fps`;
  - `contract`: exact CLI JSON schema, exit codes, persisted file formats, frozen
    user-facing strings, cross-checks between two independently maintained sources
    (for example Dockerfile ARGs against code constants), and release, Docker or
    Windows workflow contracts whose only real E2E is a hosted run;
  - `platform`: Windows-only behavior.

  Within a `keep` cluster, duplicates of the strongest test for the same failure are
  `junk:duplicate`.
- **Always keep:**
  - `tests/e2e/`, `tests/browser/`, `tests/integration/*` and
    `tests/vs/test_integration.py`;
  - `tests/services/test_alignment_frozen_strings.py`;
  - the report viewer's Node-harness tests (`tests/services/test_report_*` that go
    through `tests/services/node_harness.py`), which are the runbook's documented
    viewer proof.

  These are the proofs other tests are deleted against. Always-keep tests are
  never deleted in units C and D.
- **`vsview`, `windows_portable` and `workflows`** may lose tests only as `junk:*`
  (S10 adds `delete:internal`). They are never `delete:covered`, except under
  ruling U7.
  Their real E2E is a GUI session or a hosted Windows or release run, which unit C
  cannot execute.
- A cluster whose classification is uncertain is kept. The goal is confidence, not
  a deletion count.

**S7. Production seams.**
- When a deletion leaves a production export, parameter, wrapper, hook or branch with
  no non-test caller, unit C deletes it in the same commit.
- Proof that nothing else uses it:
  - `rg` over `src/`, `tools/`, `.github/` and the entry points in
    `pyproject.toml`;
  - `pyright --warnings` and `lint-imports` clean;
  - no documented public surface in `docs/current-cli-contract.md` or `docs/api.md`.
- Total replacement: no aliases, shims or deprecation paths.
- When unit C deletes a test file that an authority document names (for example the
  primary-check lists in `docs/current-cli-contract.md`, or runbook routing), the
  same commit updates that document.

**S8. Rules (A4).**
- **`AGENTS.md`, always-on defaults.** Add exactly these three bullets and change
  nothing else:
  - "Prove features with E2E tests in `tests/e2e/` that drive the real
    `frame-compare` executable on generated media and leave a checked artifact; the
    media tier runs through the Docker gate."
  - "Don't add unit tests that restate code you just wrote. A bug regression test
    must fail on the pre-fix code, once, at the highest seam that reproduces the
    bug."
  - "Write isolated tests only for the keep categories in `python-test-design`; list
    the failure modes before writing the code."
- **`.agents/skills/python-test-design/SKILL.md`.** Rewrite around this order:
  1. E2E (S1–S3);
  2. retained real-runtime integration;
  3. isolated tests only for the S6 `keep` categories, with the failure modes listed
     first.

  Also:
  - Add a four-question authoring gate: what behavior it protects; what credible
    regression fails it; why E2E and integration don't already catch it; whether it
    needs a production seam that no production caller needs (if yes, don't write
    it).
  - Add the S6 junk-pattern list.
  - Keep the existing subprocess-timeout, HTTP-strictness, CLI-stream and
    VS-mock-awareness rules.
  - Keep it concise, well under 100 lines.
  - Keep the name. Update the `.claude/skills/python-test-design/SKILL.md` entry only
    if the description changes.
- **`docs/ENGINEERING_RUNBOOK.md`, Docker / Runtime Verification.** Add to its
  routing list:
  - `tests/e2e/` media-tier scenarios;
  - behavior changes in `orchestration/`, `services/` or `analysis/` that change
    what a media-tier scenario observes: run output, selected frames, screenshots,
    alignment, cache or report payload.

  Keep the existing pure-calculation carve-out. No other runbook change in A4 (S5
  owns the trigger sentence).
- **`CONTRIBUTING.md`.** Update the testing section's examples and marker table for
  `tests/e2e/`, both tiers and the two environment variables.
- **No new `test-audit` skill.** S6 and S7 carry the audit procedure.

**S9. Authorized product fix: cache-flag conflict** (maintainer, 2026-09-30).
- **The defect:** `--no-cache --from-cache-only` behaves differently by mode.
  - With `--dry-run`, it is rejected early as `CONFIG_VALIDATION_ERROR` (FC-1003,
    exit 2).
  - In a real run, CLI validation skips it, and `execute_prep`
    (`orchestration/preparation.py`) rejects it later as `METRICS_CALCULATION_ERROR`
    (FC-4002, exit 5).
- **The fix:** every pipeline run and every dry run rejects the pair at the CLI
  before any runtime work, with FC-1003 and exit 2.
  - The check runs right after `validate_run_contracts` on both paths, so the
    existing error order holds.
  - `--write-config` and `--diagnose-paths`, which ignore cache flags, are
    unchanged.
  - The policy lives once, in `orchestration/analysis_policy.py`, beside the
    skip-analysis policy. The CLI and `execute_prep` both call it.
  - `RunRequest` is public (`docs/api.md`), so `execute_prep` keeps a guard for
    direct API callers through the same policy function, which raises
    `ConfigValidationError`.
  - The contract's cache section names the error.
  - E2's case expects FC-1003, exit 2. It is the regression test and must fail on
    the pre-fix code.

**S10. Revised deletion bar** (maintainer, 2026-10-01). This replaces S6's
classification rules for units B2, C and D. S6's junk patterns, always-keep list and
junk-only areas (`vsview`, `windows_portable`, `workflows`) still apply. The one
exception is ruling U7 in "Checkpoint B rulings", which allows some duplicates in
those areas to be deleted as covered.

Unit B under S6 kept 96% of tests (3,533 of 3,679) and proposed only 1,543 lines
for deletion. The reason: S6 counted a test as covered only if E2E observed every
assertion in it, and most unit tests assert internals E2E never sees.

**The question for every behavior is now:** if this test were deleted, could a
user-visible bug ship that no remaining test catches?

- **User-visible** means anything a user or a persisted consumer can observe:
  - exit codes;
  - documented stdout and stderr content;
  - files written: run records, report payload, screenshots, caches, config,
    presets;
  - requests sent to slow.pics or TMDB;
  - process behavior: hangs, leaked children, partial or lost files;
  - VSView behavior;
  - Windows install and update behavior;
  - return values and exceptions of the symbols in `docs/api.md`;
  - whether a warning or error is emitted at default verbosity (its exact wording
    only if frozen);
  - cache reuse and invalidation decisions: a stale cache reused after a change is
    a user-visible bug.
- **Internal** means everything else, including:
  - call counts or order on fakes;
  - intermediate dataclass fields;
  - private helper return values when the public output is checked elsewhere;
  - log or progress event order that no contract documents;
  - progress rendering and order, unless the progress output crashes, hangs or
    corrupts stdout.

  An internal assertion is never a reason to keep a test.
- **The flow rule** (Checkpoint B, 2026-10-01): a value is internal only if it never
  reaches a user-visible output from the list above.
  - Follow production callers only. The value must change the output's content,
    not merely appear in a debug log.
  - **Reaching an output makes the test a case of that output, not a keep.** It is
    `keep:edge` only if it reaches a production branch or boundary (cite
    `file:line`) that no retained test of that output reaches.
  - Otherwise it is `delete:covered(<owner>)`, with the mutation placed in that
    branch.
  - Example: a corpus of real release filenames whose shapes reach distinct parser
    branches (cited per shape) is `keep:edge`, consolidated into rows. Shapes that
    reach no unique branch are `delete:covered` by the corpus owner.
- **Clusters group tests by behavior, not by function.** A cluster may span
  functions and files within one lane. Each user-visible behavior has one owner:
  the strongest test for it. The other tests in its cluster are deleted as covered
  by that owner.
- **Two tests are distinct cases** if some single-line mutation fails one and not
  the other. When unsure, check whether they reach a different production branch.
  Distinct cases belong to separate clusters, or become separate rows of a
  consolidated test. POSIX and Windows variants of one behavior are distinct
  cases.
- **Classifications:**
  - `delete:junk:<pattern>`: any S6 junk pattern except `duplicate`. The full list:
    - no assertion, or an assertion that can't fail;
    - self-comparison, or an expected value computed by the code under test;
    - a copied inventory, manifest, export list or constant;
    - a source, import or string grep that doesn't guard a user-facing key, byte
      or path;
    - a private call-shape or call-order test, where the order isn't observable;
    - a mock that implements the asserted behavior;
    - a test that only keeps a test-only export, wrapper or hook alive.

    A smoke test with no assertion is also junk when a retained test runs the same
    path. Under S10, duplicates are always `delete:covered`, so they get a mutation
    proof.
  - `delete:internal`: every assertion in the test is internal (as defined above,
    including the flow rule), and **the code it checks has no user-visible outcome
    at all**. Examples: immutability of a frozen dataclass that no document lists,
    timing spans, and progress-event order.
    - The record names the production code the test exercises.
    - If a retained owner checks that code's user-visible outcome, the record is
      `delete:covered(<owner>)` instead, and needs a C2 mutation.
    - C5's coverage diff is the safety net.
  - `delete:covered(<target>)`: the named retained test fails when the cluster's
    user-visible behavior breaks. The target may be any `keep` test in the same
    lane, or an S6 always-keep or E2E test. A target in another lane is
    `delete:covered-pending(<target>)` until that target is confirmed `keep`. C2
    proves each claim by mutation.
  - `keep:<category>`, narrowed:
    - `owner`: the strongest test of a user-visible behavior that no E2E or
      always-keep summary field observes. The record names the observable output it
      checks;
    - `edge`: one boundary input per distinct boundary, in any function, including
      estimator cases such as a negative offset, VFR or `match_fps`, with its
      user-visible consequence;
    - `failure`: a failure with a user-visible consequence that no E2E or
      always-keep test triggers (hang, leaked process, partial or lost file, wrong
      exit or error code, corrupted persisted state);
    - `contract`: only behavior documented in `docs/current-cli-contract.md` or
      `docs/api.md`, a persisted format, frozen strings, or a release, Docker or
      Windows workflow contract. The record cites the document line or the writer,
      and names the specific field, byte or key asserted. Each contract element has
      one owner; other tests of the same element are `delete:covered`;
    - `network`, `security`, `platform` and `always`: unchanged from S6.
- **`keep:unresolved(<question>)`:** a test that S10 can't place. The worker writes
  the specific question in one line and continues; it never blocks the lane.
  Checkpoint B decides each one.
- **Annotations on `keep` records**, used by unit D:
  - `rewrite:<what>`: the kept test has an assertion that can't fail. Unit D
    changes it so the assertion can fail, and proves it with one mutation;
  - `trim`: the internal assertions to remove from a kept test, by line;
  - `consolidate:<group>`: kept tests in **one file** that share setup or shape and
    can become one parametrized test. The record maps each member test to a
    parameter row and gives the expected lines after merging.
- **No E2E widening.** The scenario summaries stay as they are. A new summary field
  or scenario is added only when B2 finds a user-visible behavior whose only guard
  is a heavily faked unit test. Each such case goes to the maintainer individually.

**S11. Two retention rules** (maintainer, 2026-10-01, after lane 1a). These apply to
unit C from the resume onward, through a catch-up pass for lanes already done, and
to unit D.

- **R1. Test-only production code is S7 scope.** A production symbol is test-only
  when nothing outside tests uses it:
  - the symbol is a function, class, method, module, parameter or branch;
  - `git grep` over tracked files finds no caller in `src/` (outside its own
    definition), `tools/`, `.github/` or the `pyproject.toml` entry points;
  - it isn't documented in `docs/api.md` or `docs/current-cli-contract.md`.

  Such a symbol is S7 scope even if no deletion orphaned it.
  - Tests whose only subject is a test-only symbol are
    `delete:junk:test-only-hook`.
  - Unit C deletes the symbol (C3) when no retained test uses it.
  - When retained tests use it as an oracle or expected-value producer, unit C
    records it in the lane's `c.md` as `rewrite: inline the expected values, then
    delete <symbol>`. Unit D does that work.
  - Lines and branches inside a test-only symbol never count as C5 coverage loss.
  - Lane 1a example: `services/alignment_correlation.py::comparison_window` has no
    production caller. Its restored tests B1a-030 and B1a-126 may be deleted, and
    unit D rewrites the streaming oracle tests that use it.
- **R2. One test per failure outcome, for data the program writes itself.**
  - **Scope:** validators, parsers and constructor guards (`__post_init__` checks)
    for data Frame Compare writes and reads back:
    - alignment evidence and diagnostic payloads;
    - analysis, probe and alignment caches;
    - `run_info.toml` and `run_result.toml`;
    - the report payload;
    - VSView session data;
    - internal carriers.
  - **Rule:** for each entry point, keep one test per distinct failure outcome:
    refused with a warning, a specific documented error raised, treated as a cache
    miss, or falling back to "unavailable". Other tests that reach the same
    outcome through a different malformed-data branch are
    `delete:redundant-failure(<outcome owner>)`.
  - These need no C2 mutation, because the owner deliberately doesn't cover their
    branch. Their C5 coverage loss is accepted and listed, not restored.
  - **Out of scope** (per-branch edge cases stay):
    - input users author: config files, CLI flags, environment variables,
      filenames and release names, presets, user-edited files;
    - data from outside the program: FFmpeg and ffprobe output, HTTP responses,
      plugin output;
    - security checks: path escape, redaction, signatures;
    - cache identity and reuse decisions. A stale cache reused after a change is a
      user-visible bug, not malformed data.

## Units

Codex runs each unit through a handoff. The Claude controller verifies each
checkpoint, reusing the unit's reported evidence where it is still current, before
writing the next handoff.

### Unit A: E2E suite, CI wiring and rules (`.handoff/T1-codex-e2e-suite.md`)

- **A1:** harness (runner, workspace, artifact writer, media gate) and E1–E5.
- **A2:** media generator and M1–M6. It needs A1 and is determinism-heavy, so it
  goes to `worker`. Its proof runs through direct `docker compose run`, never the
  verify script.
- **A3:** S5 wiring and the matching test and runbook updates. No real Docker runs:
  the existing fake-docker tests prove the argv.
- **A4:** rules (S8).
- **A5:** integrated proof:
  - the full native gate;
  - the verify script run twice, with byte-identical summaries;
  - three temporary source mutations, each reverted with `git checkout -- <file>`:
    flip the applied alignment offset's sign, skip the analysis cache write, and
    force tonemapping off. Each must fail M5, M3 and M4 respectively, on an
    assertion.
  - one amd64 run of the media tier (`DOCKER_DEFAULT_PLATFORM=linux/amd64`), with
    its summaries identical to the arm64 ones. If emulation makes that impractical,
    say why; the cross-architecture check then moves to Checkpoint A;
  - a review of the whole unit A diff.

Order: A1 and A4 together, then A2 and A3 together, then A5.

Checkpoint A (controller):
- review A5's evidence and every scenario against S1–S4;
- rerun the native gate only if the tree changed after A5;
- confirm the cross-architecture check before unit C starts. The evidence is A5's
  amd64 run, or a hosted amd64 `docker-integration` run of this branch; the
  maintainer decides whether to push for that. Unit B is read-only and may start
  first.

### Unit B: discovery ledgers (handoff written after checkpoint A)

- Read-only work. There are ten lanes, with at most six running at once. The two
  largest areas are split; exact file sets are in the unit B handoff.
  1. **1a:** `services` alignment estimator and evidence;
  2. **1b:** `services` alignment workflow, reuse and review;
  3. **2:** `services` other;
  4. **3a:** `orchestration` execution and phases;
  5. **3b:** `orchestration` other;
  6. **4:** `cli`;
  7. **5:** `render`, `vs`, `analysis`;
  8. **6:** `config`, `utils`, root `tests/*.py`;
  9. **7:** `vsview`;
  10. **8:** `windows_portable`, `workflows`, `scripts`, `manual`.
- Each lane writes only `.handoff/test-audit/<lane>.md`. One record per cluster:
  - test node IDs and file:line;
  - the behaviors asserted, one line each;
  - the classification (S6);
  - for `covered:` clusters, the named covering test for each behavior and a
    proposed minimal mutation for each behavior;
  - for `junk:` clusters, a one-line demonstration: the line that can't fail, the
    copied source, or the other test that already asserts the same thing;
  - the production seams the deletion unlocks (S7), and any authority documents
    that name the file;
  - relevant history (`git log -S` or the commit that added the test);
  - lines deleted.
- Workers run no tests, no mutations and no Docker.

Checkpoint B (controller):
- Adjudicate every record: `Approved`, `Keep` or `Needs proof`, with a one-line
  reason.
- Check `junk:` records with the same strictness as `covered:` ones: check every
  `junk:` record in lanes 1a–5 and a sample of at least one in five elsewhere.
- The approved records become unit C's scope.

### Unit B2: reclassification under S10 (`.handoff/T3-codex-reclassify.md`)

- Read-only. The same ten lanes and file sets as unit B. Each lane reads its unit B
  ledger as an inventory of what each test asserts, and writes
  `.handoff/test-audit/<lane>.b2.md`.
- Checkpoint B (controller) adjudicates the B2 ledgers instead of the unit B ones,
  with the same rules: check every `delete` record in lanes 1a–5 and a sample of
  at least one in five elsewhere, plus a sample of `keep` records against the
  narrowed categories.

### Checkpoint B rulings (controller, 2026-10-01)

**B2 result.** All ten lanes done; 3,679 nodes mapped exactly once.
- Proposed for deletion: 216 junk, 142 covered and 434 internal tests, 11,643
  lines in total.
- Kept: 2,763 tests. Unresolved: 124 tests in 105 questions.
- Projected remainder after units C and D: about 76.7k of 92.0k `wc -l` lines.

**Samples.**
- **Junk** records are sound. The one exception is ruling **B8-087:
  `keep:contract`**. It is a source grep for the PowerShell `param` block, which
  PowerShell requires first.
- **Internal** records show a systematic error, which the flow rule and the
  narrowed `delete:internal` above now fix:
  - parser corpora (**B2-2-003, B2-2-059**) were called internal although their
    values reach TMDB queries and labels. They are re-decided by the flow rule;
  - tests with a named owner (**B6-013**) skipped the mutation proof. They become
    `delete:covered` with a C2 mutation.

  Every `delete:internal` and `delete:junk` record, and every record named in these
  samples, is re-verified in unit C step C0. Unit B3 was folded into C0; see
  below.

**Rulings on the `keep:unresolved` questions.** Each applies to every record it
names.

- **U1. Arguments handed to an external runtime are owned behavior.** A test that
  asserts the arguments, expressions, properties or calls handed to VapourSynth,
  libplacebo, Pillow or FFmpeg is `keep:owner` of "the correct parameters reach the
  runtime".
  - The exception: a real-runtime test (M*, `tests/vs/test_integration.py`,
    `tests/integration/**`) **observes** the case. "Observes" means a field in that
    test's `expected` literal, or an assertion, changes when the parameter is
    wrong. Running the code path is not enough.
  - If it observes the case, the record is `delete:covered(<test>)`, route docker.
  - Distinct parameter cases of kept owners become consolidation rows.
  - Applies to: B5-055, 056, 064, 149, 165–169, 328–332, 368, 459, 462, 463–473,
    477–479, 481–486; B3b-119, 139, 140, 141.
  - B5-277 (graph serialization) and B5-487–492 (probe and backend selection) are
    `keep:failure`, because the user-visible consequence is a crash, hang or
    wrong backend.
  - B5-338 and B5-340–348 (DLL and plugin loading) are `keep:platform`.
- **U2. No public proof means the test is the owner.** When the question is "which
  public result observes X" and none does, the existing test is `keep:owner`.
  - Assertions on the carrier field that carries the value to the output are the
    owner's check, and never `trim`.
  - Only fake-call and shape assertions are `trim`.
  - Applies to: B3a-043, 076, 078, 079, 080, 083, 085, 108, 109, 117, 126, 149,
    151, 176, 177; lane 2's two metadata-stub questions; B4-190.
  - B3a-030's forbidden-publisher assertion is swallowed by warn-only handling. It
    stays `keep:owner` with the annotation `rewrite: make the forbidden-publisher
    assertion able to fail`, for unit D.
- **U3. Shared-mutation questions are decided by C2.** These records become
  `delete:covered(<owner>)`, deleted only if C2's mutation fails both the owner
  and each deleted test individually, on an assertion: B1a-045, B3a-003,
  B3a-025, B5-290, B5-305, B5-334, B5-461. Otherwise each becomes `keep:edge`, in
  its own cluster.
- **U4. Documented behavior is a contract.**
  - `keep:contract` with a citation: B3b-149, if "Shared Path Resolution Rules"
    lists the asserted locations, otherwise `keep:owner`; B4-196, logging
    precedence.
  - B6-247 (numeric exit values) and B4-062 (exit categories): exit codes are
    user-visible.
    - B6-247 is `keep:contract` if the contract documents the values, otherwise
      `keep:owner`.
    - B4-062 is one non-parametrized test, so it stays `keep:owner` with
      `consolidate` into one row per category. A row that a retained command-level
      owner already fails on is `trim`; the record names that owner and its C2
      mutation.
- **U5. Undocumented internals.**
  - B3b-207 (returned shared-cache paths): `delete:internal`, unless a
    user-visible consumer reads them.
  - B4-078 (terminal width at import): `keep:failure` only if its history shows a
    regression fix, otherwise `delete:internal`.
  - B6-055 (preset bytes): `keep:owner`. It compares two saves in one process, so
    it guards against per-save content such as a name or timestamp leaking into
    the file. It can't catch hash-order nondeterminism.
  - B6-116 (umask): `keep:failure`. A process-wide permission race changes the
    permissions of written files.
  - B6-156: `delete:junk:no-assertion`.
  - B6-226: `delete:junk:no-assertion` only if a retained test passes the same cold
    and reuse states; otherwise `keep:edge`, because it fails if the policy
    rejects valid states.
  - B6-218 (API-doc drift): `keep:owner` for one matching case and one stale case;
    the others are `delete:covered`.
- **U6. Lane 2 specifics.**
  - The metadata stubs, B2-2-012 and B2-2-015: as in U2.
  - Category display labels, B2-2-088: `keep:edge`, because they are visible text.
  - The reduced-motion and 44px CSS checks, B2-2-142: `keep:owner`. Accessibility
    basics are never simplified away.
  - The webhook on port 8443, B2-2-246: `keep:security`.
- **U7. Duplicates in junk-only areas.** Within `vsview`, `windows_portable` or
  `workflows`, a duplicate may be `delete:covered` when its owner is in the same
  area **and** C2 can run that owner natively. If the owner skips natively (no
  `pwsh`, or Windows-only), the duplicate is kept.
  - Applies to: B7-039, B7-048, B8-040, B8-216.
  - B8-135, B8-141: their executed owners skip natively, so they are kept.
- **B4-126:** `keep:platform`.

**Not a product bug.** SB8-1 (`tools/open_docker_host_target.py:60`):
`PurePosixPath` normalizes `.` away, so the `"."` half of the check never fires,
but `.` can't escape. `..` is still rejected, and the `resolve()` plus
`is_relative_to` guard is the real protection. At most it's one dead condition.

**Widening candidates: all declined** (maintainer, 2026-10-01). B2 listed 76. Each
describes a behavior that keeps a unit test, so none would let unit tests be
deleted, and each would add E2E lines. The goal is a slimmer suite.

### Unit B3: folded into unit C (maintainer, 2026-10-01)

The separate read-only verification round (`.handoff/T4-codex-verify-deletions.md`)
was written but **not dispatched**. Its job became step C0 below, done by the same
worker that deletes the lane. The reasons:
- that worker must read the records anyway;
- C2 and C5 are objective gates that don't depend on its judgment;
- the controller reviews every C0 reclassification.

### Unit C: deletions (`.handoff/T5-codex-deletions.md`)

Inputs: each lane's B2 ledger, the Checkpoint B rulings (including the records
named under Samples), and S10 as amended (the flow rule and the narrowed
`delete:internal`).

- **Order.** One task per lane, **strictly serial**, one commit each, in lane order:
  1a, 1b, 2, 3a, 3b, 4, 5, 6, then 7 and 8 together. Serial work keeps the coverage
  diffs and mutations from overlapping. Ledger line numbers refer to `60d88657`
  and drift as earlier lanes delete code, so locate each mutation by its quoted
  text.
- **C0: verify before deleting.** For every `delete:internal` and `delete:junk`
  record, and every record named by a ruling or under Samples:
  - apply the flow rule, the narrowed `delete:internal`, rulings U1–U7, B4-126
    and B8-087.
  - **Owner protection.** Before deleting a node, `rg` its `file::function` (without
    the parameter suffix) across `.handoff/test-audit/*.b2.md` and `*.c0.md`.
    - Count only matches inside a `delete:covered(...)` or
      `delete:covered-pending(...)` target, or in a `c0.md` owner field. The
      node's own record always matches, and doesn't count.
    - A node that any record names as an owner is never deleted.
  - **Cross-lane owners.** A cross-lane owner is `delete:covered-pending(<node>)`.
    - If the target is in an earlier lane and still exists at HEAD, it counts as
      confirmed, and the record proceeds through C2.
    - If the target is in a later lane, the test stays. The target is recorded in
      `<lane>.c0.md`, so that the later lane's owner protection keeps it.
  - Write `.handoff/test-audit/<lane>.c0.md`, listing every changed record (old →
    new, reason, and the one-line trace `function → caller → output`) and every
    pending target.
- **C2: mutation proof for every `delete:covered` record**, including those C0
  creates. For each behavior:
  1. Apply the proposed mutation.
  2. Run every deleted test **individually** and the owner.
     - All must fail on an assertion failure, meaning `AssertionError` or pytest's
       `Failed` from `raises` or `fail`. An exception, import error or child
       process crash doesn't count.
     - For E2E owners, the summary diff must be in the fields the mutation
       targets. A Python traceback on stderr, or a change in fields the mutation
       doesn't target, disqualifies the proof.
     - Native owners run with `uv run --no-sync pytest`.
     - Docker-only owners run with
       `docker compose run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp/framecompare-home -e PYTHONUSERBASE=/home/framecompare/.local -e FRAME_COMPARE_E2E_REQUIRE_MEDIA=1 -e FRAME_COMPARE_E2E_ARTIFACTS=/workspace/generated/c2/<record> frame-compare-test -lc '<prelude>; python -m pytest -vv -p no:cacheprovider <owner node>'`.
       The bind mount sees the mutated source, and the artifacts stay under the
       gitignored `generated/`.
  3. Restore with `git restore --worktree -- <file>`, and confirm
     `git diff --quiet -- <file>`.

  A deleted test that doesn't fail is a distinct case: it stays, as `keep:edge`.
  This never blocks. Mutations are never committed.
- **C1: delete.** Delete:
  - the junk tests, confirmed internal tests and covered tests that passed C2;
  - support code that no remaining test, in any lane or covering proof, imports.
- **C3:** delete the S7 production seams, and update any authority document that
  names a deleted file or test, in the same commit.
- **C5: native coverage diff, per lane**, as the objective safety net for distinct
  cases.
  1. Create a scratch rc file outside the repository, `b2.coveragerc`:
     - `[run]`: `source = src/frame_compare`, `branch = true`,
       `patch = subprocess`, `omit = */__main__.py`, and
       `data_file = <scratch>/.coverage`, so nothing is written inside the
       repository;
     - `[report]`: `exclude_lines`, copied from `pyproject.toml`;
     - `[json]`: `show_contexts = true`.

     Subprocess patching was verified on coverage 7.16.2: the E2E child processes
     are measured.
  2. Run `uv run --no-sync pytest -q --cov --cov-config=<scratch>/b2.coveragerc
     --cov-report=json:<scratch>/<lane>.<phase>.json` twice before the deletions
     and once after. Add `--cov-context=test` to the first "before" run, which
     records which test executed each line.
     - A lane may reuse the previous lane's "after" run as its second "before" run
       only if no restoration happened after it, and the tree it measured equals
       the previous lane's commit.
     - Use the same machine and environment for every run.
     - A failing "before" run blocks the lane after one retry; leave the tree
       clean.
     - A failing "after" run is handled like a C4 gate failure: restore the
       responsible deleted tests and re-run.
  3. Lines or branches that differ between the two "before" runs are flaky and
     ignored.
  4. Every line or branch executed before and missing after needs one of:
     - an S7 deletion in the same commit;
     - a C2 mutation whose owner failed, placed on that line or branch, or in the
       same straight-line block or branch as it.

     Otherwise:
     - find the deleted tests that executed it, from the first "before" run's
       contexts. In-process tests are recorded as `<node id>|run`, `|setup` or
       `|teardown`; match `<node id>|*`. Lines run only
       inside child processes carry an empty context. If a lost line has only
       empty contexts, restore the lane's deleted tests that spawn a process
       reaching that code; verified with coverage 7.16.2 and pytest-cov;
     - restore those test functions and their fixtures from
       `git show <lane base>:<file>`;
     - re-run only those tests under coverage, and confirm the lost lines and
       branches are covered again.

     List each restoration with a one-line justification under "needs maintainer
     approval". A later task may delete them after approval.
  5. **Docker-route records.** Some code was covered natively only by a deleted
     test whose owner runs in Docker. That code is resolved by the record's Docker
     C2 mutation, under the same block rule as step 4. Code that only Docker runs
     never appears in the native diff at all.
- **C4: gates, per lane commit.**
  - `pyright --warnings`, `ruff check .`, `ruff format --check .`, `lint-imports`.
  - The full native `pytest -q`. A passing C5 "after" run counts as this if the
    tree hasn't changed since.
  - `bash tools/verify_docker_integration.sh --no-build` when the commit:
    - deletes production code; or
    - deletes tests or fixtures under `tests/vs/`, a conftest fixture, or a support
      module that `tests/integration/**` uses.
  - Before committing, `git status --short` lists only this lane's planned
    deletions and edits.
  - Report the `git diff --numstat`, split into production and test lines.
- **S11** (from the T5R resume): C0 applies R1 and R2; C3 deletes test-only symbols
  that no retained test uses; C5 ignores lines inside test-only symbols and
  accepts R2 losses. Lanes finished before S11 get a catch-up pass
  (`.handoff/T5R-codex-deletions-resume.md`).
- **Not in unit C:** trims, consolidation, `rewrite` annotations and renames. Those
  belong to unit D.

Checkpoint C (controller):
- review every C0 change, the "needs maintainer approval" list, a sample of C2
  records and the diff;
- re-run the full native gate and one Docker gate;
- update the inventory in the execution record.

### Checkpoint C rulings: the approval list (maintainer, 2026-10-01)

Unit C restored about 70 tests whose deletion lost native coverage. The maintainer
approved this split:

IDs are short B2 record numbers within each lane: lane 1b's B060 is ledger record
`B1b-060`. Each lane's `.c.md` lists them, with node IDs, under "needs maintainer
approval".

- **Delete (D0), accepting their coverage loss.** These are progress-display
  details, internal under S10:
  - lane 1b: B060, B151;
  - lane 3a: B026, B027, B028, B175, B188, B189, B190;
  - lane 3b: B113, B296, B297;
  - lane 6: B151, B152, B156, B160–B164, B168, B172, B180–B182, B184. B183 was
    already deleted in unit C.
- **Keep everything else**, including:
  - all twelve lane 2 records: the parser corpus, streaming-service display
    codes, folder-name edges, TMDB key redaction and malformed TMDB responses;
  - lane 3a: B067, B107, B148, B187, B191;
  - lane 3b: B283, B285, B293, B329, B330, B333, B334;
  - lane 5: B079, B360, B362, B363;
  - lane 6: B004, and B167, B169, B170, B171, B177, which are crash guards for the
    plain and Rich progress lifecycles;
  - lane 7: B102, B103, B104.

### Unit D: consolidation, rewrites and typing (`.handoff/T6-codex-consolidate.md`)

One task per lane, **strictly serial**, because consolidation and rewrite proofs
mutate `src/`. The order is the same as unit C: 1a, 1b, 2, 3a, 3b, 4, 5, 6, then
7 and 8 together. Each task works only on its lane's surviving tests and, for R1,
the production symbols its records name. Its inputs:
- the lane's `.c.md` (and `1a.c-s11.md`): unit C's `rewrite` records and R1
  symbols left for unit D;
- the B2 ledger's `trim`, `consolidate`, `rewrite` and rename annotations, applied
  only to tests that still exist;
- the D0 list above.

**Scope limits:**
- Unit D deletes only the D0 list and R1 symbols. A "reconsider" note in a `.c.md`
  record is recorded in the task record, not acted on.
- A lane may edit another lane's or `tests/integration`'s files only where its own
  R1 records name them as consumers of a symbol it deletes. Today that means:
  - lane 5: the render-wrapper consumers in `tests/integration/test_render_*.py`;
  - lane 6: B3b-293, for `RichProgressReporter.no_color`;
  - lane 4: B4-192 for `force_tty`, which lane 3b leaves in place.
- Production edits are R1 deletions under S7, plus docstrings or comments that
  name a deleted R1 symbol.

Steps, in order:

- **D0.** Delete the approved tests. Their C5 losses are accepted, not restored.
- **D1. Rewrites.**
  - Apply every unit C `rewrite` record and B2 `rewrite` annotation. That includes
    R1: inline the expected values, or migrate to the real API, then delete the
    test-only symbol under S7 checks.
  - Each rewrite is proved by the mutation its record names, which fails the
    rewritten test on an assertion.
- **D2. Trims.**
  - A trim may not remove an assertion that C2 recorded as failing.
  - When a trimmed file owns a `delete:covered` target, rerun that target's C2
    mutations after the trim.
- **D3. Consolidation.**
  - Each group's surviving members become one parametrized test.
  - Every original case maps to a parameter row or a retained assertion, and the
    mapping goes in the task record.
  - The file's collected case count may drop only by approved deletions and by
    the merges recorded in the case-mapping table.
  - One mutation per group fails the new test on an assertion.
- **D4. Renames** from the ledger annotations.
- **D5. Typing.** Every Python file in the lane passes
  `pyright --warnings <file>` under the existing `tests` execution environment.
  - Fakes use the real types or a `Protocol`.
  - `# type: ignore` is allowed only with a reason on the same line.
  - There were 504 errors in `tests/` at `3682ed88`: 294 in `tests/vs`, 67 in
    orchestration, 39 in cli, 36 in integration, and the rest spread out.
- **Mutation restores:** before mutating a file with uncommitted lane edits, stage
  that file. `git restore --worktree` returns to the staged state, and
  `git diff --quiet -- <file>` then confirms the restore.
- **Gates:**
  - after commits (a) and (b): the lane's own tests;
  - once per lane, before commit (c): the full native `pytest`;
  - `pyright --warnings` on the lane's files, `ruff check .`, `ruff format --check .`
    and `lint-imports`;
  - `bash tools/verify_docker_integration.sh --no-build` when the lane deletes
    production code or touches `tests/vs/`, a conftest, or support that
    `tests/integration/**` uses.
- **Commits:** at most three per lane: D0–D1; D2–D4; D5.
- Lane 3b also fixes the stale `FramePlan` docstring at
  `orchestration/context.py:143`.

**Checkpoint D (controller, before unit E):**
- compare each lane's `assert` line count before and after, excluding D0 and its
  deleted tests;
- sample the case-mapping tables and rewrite mutations;
- run the full native gate.

### Unit D repair: restore carrier assertions (`.handoff/T6R-codex-trim-repair.md`)

Checkpoint D found that D2 trims removed assertions guarding user-visible values.
The B2 trim annotations predate the flow rule and U2, and neither the trim-safety
rule nor C5 could catch them.

**The proven case:** after the B3a-150 trim, breaking the comparison-stream mapping
in `phase_alignment.py` passes the whole native suite.

**The repair,** per lane and serially:
1. Enumerate the assertions removed in `53b60b4c..47a9ad4c`, other than D0, R1
   tests and consolidated re-expressions.
2. Classify each one as internal or carrier, under the flow rule.
3. For each carrier group, prove it with a mutation, or restore the assertion
   with its original expected value. A restored assertion must fail the
   mutation.

Unit E follows after the controller checks the repair.

### Unit E: pyright gate and rules (`.handoff/T7-codex-typing-rules.md`, after checkpoint D)

- Type-check the files no lane owns: `tests/integration/**`, `tests/browser/**`,
  `tests/e2e/**`, and `tests/conftest.py`. Fix type-only regressions in any
  `tests/` file.
- Set `include = ["src", "tests"]` in `[tool.pyright]`, and confirm that
  `pyright --warnings` is clean repo-wide.
- Update any runbook or `CONTRIBUTING.md` text that says pyright covers only
  `src/`.
- **Align the authoring rules with S10.** Rewrite `AGENTS.md`'s three testing
  bullets and the `python-test-design` skill to S10's vocabulary:
  - one owner per user-visible behavior;
  - the flow rule;
  - the `owner`, `edge`, `failure`, `contract`, `network`, `security` and
    `platform` categories;
  - R1, R2, and that internal assertions are not a reason to keep a test.
- **Final gates:** the full native gate, and one
  `bash tools/verify_docker_integration.sh --no-build`.

## Invariants

- No product behavior change, apart from S7's deletion of test-only production code
  and S9's fix.
- No test-only production seams: no new flags, env reads, hooks or exports in
  `src/`.
- No new dependencies and no new pytest plugins.
- No added skips, `xfail`s or loosened assertions in retained tests, except S5's
  deletion of the inverted negative-trigger assertions. A retained test that fails
  on the base is a possible product bug: report it `blocked`.
- Every subprocess call in tests has an explicit timeout.
- E2E never reaches the network, and never writes outside its `tmp_path` workspace
  and `artifact_root`.
- Mutations are temporary, serial and never committed.
- Commits use `git commit --only -- <paths>`, with a Conventional Commit subject:
  one per task, except unit D, which allows up to three per lane. Workers sharing
  the checkout never rely on the shared index.

## Stop conditions

Any of these stops the unit and sends a `blocked` message:

- a required scenario fact isn't exposed where Baseline says it lives;
- a media scenario can't be made byte-identical across two Docker runs;
- a retained test fails on the base;
- a deletion needs a production behavior change;
- (not a stop condition) a covering test that doesn't fail under its mutation: the
  deleted tests are kept as `keep:edge`, and the work continues;
- any conflict between this plan and an authority document not listed in S5 or S8.

## Verification summary

| Unit | Native | Docker | Other |
| --- | --- | --- | --- |
| A1, A4 | `pytest -q tests/e2e`, linters on owned files | — | skill front matter and link check (A4) |
| A2 | media tier skipped | direct compose run ×2, byte-identical summaries | — |
| A3 | `tests/workflows`, `tests/vs/test_runtime_contract.py`, `bash -n` | none (fake-docker tests) | YAML parses |
| A5 | full gate | verify script ×2 | 3 mutations fail M5/M3/M4 |
| B, B2 | none (read-only) | — | ledger completeness |
| C | C0 records; full gate per commit (the C5 "after" run may count); C5 line and branch diff | C2 Docker mutations; verify script per the C4 triggers | mutation records |
| D | lane `pyright --warnings`; full gate per lane | verify script per the D gate triggers | case mapping; one mutation per group and per rewrite |
| E | `pyright --warnings` repo-wide, with `tests` included; full gate | verify script once | rules text against S10 and S11 |

## Residual risks

- Cross-architecture determinism: confirmed by A5's emulated amd64 run (all 17
  summaries matched arm64). The first hosted run remains the final check.
- **M4 doesn't measure pixels.** It proves the configured tonemap preset, target and
  RGB export, but no pixel statistic shows the tonemap ran. A unit test guarding
  tonemap pixel math can only be `delete:covered(M4)` if its C2 mutation actually
  fails M4.
- Windows runs only the CLI tier. Windows media behavior stays covered by the
  hosted Windows portable route and the `platform` keep category.

## Rollback

Each task is one commit (up to three per lane in unit D), so rollback is
`git revert <sha>`, in reverse order within a lane. Later unit C lanes can
build on earlier lanes' S7 deletions, so revert unit C commits in reverse order.
Reverting one restores its tests and any seams it deleted.

## Execution record

- 2026-09-30: `7eea6921` removed the coverage floor (`fail_under`, CI `--cov`, and the
  workflow test's coverage assertions).
- 2026-09-30: native baseline on `7eea6921` (macOS arm64,
  `uv run --no-sync pytest -q`): 3,643 passed, 81 skipped, 127 s wall time. Skip
  causes:
  - PowerShell or Windows process semantics unavailable (`windows_portable`);
  - `lsmas plugin not available`;
  - opt-in resource and live-network tests;
  - `libplacebo` unavailable.
- 2026-09-30: plan and T1 handoff reviewed (`deep_reviewer`; correctness,
  repository policy and adversarial passes). All 20 findings were accepted and
  folded into this revision:
  - test-container UID and artifact permissions;
  - inherited runtime environment;
  - no built-in presets;
  - shared-index commits and Docker collisions;
  - where the observable facts live;
  - media-tier gating by environment variable only;
  - the Windows CLI tier;
  - `xfail` detection;
  - required summary fields and A5 mutations;
  - two-sided mutation proof;
  - keep rules for `vsview`, the Node harness and cross-source contracts;
  - authority-document test lists;
  - A3's inverted assertions;
  - rule text consistency;
  - M7 dropped;
  - E1 version source;
  - M3 analysis and corruption;
  - `.lwi` isolation;
  - A2 given to `worker`;
  - baseline wording.
- 2026-09-30: verification pass by the same reviewer. It found 15 of 20 fixed and 5
  partial, plus nine new issues. All were folded in:
  - wave 2 waits for A4 (both touch the Docker / Runtime runbook section);
  - E2 error fields (`error.code`, `error.name`);
  - the M3 history order tie;
  - no E1 help snapshot;
  - the S5 inversions exempted from the no-loosening invariant;
  - `tomli_w` for config files;
  - `--no-build` for the mutation runs;
  - M3 step 5 corruption mechanics and M6 event parsing;
  - explicit commit steps;
  - the amd64 check before unit C.
- 2026-09-30: T1 first dispatch, base `ed183652`.
  - Committed:
    - A4 `458feea4`: rules;
    - A1 `4ffb7440`: harness, E1–E5, 11 tests;
    - A3 `fe128841`: CI and Docker wiring.
  - A2 blocked on a real contract conflict, and A5 was not dispatched.
  - The controller resolved the conflict in `922e9421`. The stale sentence at the
    old contract line 1625 predated the video check; the code and the final-state
    list are authoritative, so M5 stands.
  - Controller review of A1 and A4 found rework, done in the T1R handoff:
    - the artifact writer's read-back self-comparison;
    - scenario configs replacing the network-safe defaults;
    - tests importing helpers from `conftest.py`;
    - E4's artifact recording one of seven steps;
    - E3's expected listing copied from the value under test;
    - the skill citing plan IDs;
    - `CONTRIBUTING.md` running the media tier natively.
  - E2 exposed the cache-flag defect fixed by S9.
- 2026-10-01: T1R completed unit A at `3d906ee2`, from base `d4f7da5a`.
  - Commits:
    - A4R `66defd1e`: rule text cleanup;
    - P `33dbc6e7`: S9 fix. The E2 regression failed on the old code with exit 5,
      FC-4002, and passed after the fix;
    - A1R `53f626f2`: harness rework;
    - A2 `88bb9609`: media tier M1–M6;
    - A5 `cf8197e6`, A5R `1768a4fb`, A5S `3d906ee2`: media fixture gating and M3
      failure recording.
  - Evidence:
    - native: 3,652 passed, 87 skipped. The difference from baseline is the 8 CLI
      cases, 1 workflow case and 6 gated media cases;
    - arm64 Docker: 294 passed twice, 0 skipped, xfailed or xpassed. The 17
      `summary.json` files were byte-identical, and the media tier took about 16 s;
    - the three A5 mutations each failed M5, M3 and M4 at `summary == expected`;
    - an emulated amd64 run gave 17/17 summaries identical to arm64;
    - the artifacts are owned by the host UID.
  - **Checkpoint A** (controller, 2026-10-01): verified.
    - The S9 diff matches the spec.
    - The M3 repairs route a mid-loop failure into the checked summary without
      weakening anything.
    - The media scenarios carry the S4 fields as explicit literals.
    - Native `tests/e2e`: 11 passed, 6 media skipped.
    - The import, conftest-import and skip greps are empty apart from the media
      gate, and pyright is clean.
    - The A5 Docker evidence is reused under the runbook's currency rule.
  - Unit B lanes split to ten (1a/1b, 3a/3b), because of size.
- 2026-10-01: unit B (T2) completed at base `ae434e5c`. All ten lanes reported done,
  and 3,679 nodes were ledgered exactly once. Proposed for deletion: 117 clusters,
  146 tests, 1,543 lines. Kept: 2,531 clusters, 3,533 tests, 68,042 lines.
  - **Maintainer decision:** adopt S10 and reclassify (B2) before any deletion. Add
    unit D (consolidation with typing) and unit E (pyright for tests). No E2E
    widening.
  - The unit B ledgers stay as B2's assertion inventory. Checkpoint B moves to the
    B2 output.
- 2026-10-01: the first T3 dispatch blocked in all six started lanes on two S10
  gaps. Fixed in the plan and T3:
  - S10's junk list read as examples, so it omitted private call-shape and
    source-grep patterns. It now lists every S6 pattern.
  - There was no label for tests whose assertions are all internal (for example
    frozen-dataclass immutability). Added `delete:internal`, with C5 as the safety
    net.
  - Unplaceable tests now become `keep:unresolved(<question>)` instead of blocking
    a lane.
- 2026-10-01: maintainer decisions:
  - decline all 76 widening candidates;
  - don't dispatch T4. Its verification became unit C step C0, done by the
    deleting worker, with C2 and C5 as the objective gates.

  Unit C runs serially, lane by lane (lanes 7 and 8 together), from
  `.handoff/T5-codex-deletions.md`.
- 2026-10-01: lane 1a `c2f3be2d`.
  - Deleted 11 cases, 183 lines net, against a proposal of 38 cases and 718 lines.
    C0 moved 21 records to keep. Two owners didn't fail C2, so their candidates
    were kept. C5 restored B1a-030 and B1a-126.
  - All gates passed, and the full suite was 3,641 passed, 87 skipped. Checked by
    the controller, including the B1a-191 owner log, which showed an
    `AssertionError` in both cases.
  - **Maintainer decision:** adopt S11 (R1 and R2) to cut over-retention. Unit C
    paused after lane 1a and resumes from `.handoff/T5R-codex-deletions-resume.md`,
    starting with a catch-up pass for lane 1a.
- 2026-10-01: unit C completed at `a0c4717f`, resumed from `bdf9a7fd` under S11.
  - Commits: 1a `c2f3be2d`, 1a catch-up `57ee36ad`, 1b `f2d39549`, 2 `6a8a4c09`,
    3a `8e3e5233`, 3b `7d79fab6`, 4 `72ed794a`, 5 `0247de07`, 6 `6f79c9f4`, 7 and 8
    `a0c4717f`.
  - Removed: 579 cases and 7,507 test lines. S11 removed 22 production symbols
    (368 `src/` lines) and 195 R2 cases. The accepted R2 coverage losses are 100
    lines and 86 branches.
  - Test lines: 92,040 → 84,533 (`wc -l`).
  - **Checkpoint C** (controller, 2026-10-01): verified.
    - Native: pyright 0/0, ruff and formatting clean, `lint-imports` 2/2 kept,
      bandit with no medium findings. The full `pytest`: 3,074 passed, 90 skipped.
    - Docker: the post-commit `verify_docker_integration.sh --no-build` log at
      HEAD: 284 passed, 0 skipped, all proof markers. Reused under the currency
      rule, because the tree is unchanged.
    - The production deletions have no remaining references (`git grep`),
      including tools, docs and `pyproject.toml`.
      - `tools/benchmark_analysis_tiers.py` still loads.
      - `resolve_metadata(prompt_callback=)` had no production caller.
      - FC-3004 was raised only from the deleted test-only `frame_plan` and was
        documented nowhere.
    - One stale docstring, `orchestration/context.py:143` (`FramePlan`), goes to
      unit D.
    - The thread settings were reported as UNVERIFIED, because Codex exposes no
      runtime metadata. Every thread was dispatched explicitly with
      `gpt-6.1-sol` / `medium`.
- 2026-10-02: unit D completed at `47a9ad4c`, from base `53b60b4c`.
  - Test lines: 84,533 → 80,792. Native: 3,050 passed, 90 skipped. Last triggered
    Docker run: 276 passed, 0 skipped. Lane pyright: zero errors in owned files;
    35 remain in unowned files, for unit E.
  - **Checkpoint D** (controller, 2026-10-02):
    - Static gates are clean.
    - Full `pytest`: one unidentified failure in six runs at HEAD. The other five
      runs passed 3,050, so the failing test is flaky. Its name wasn't captured.
    - Assertion lines in touched files: 8,106 → 6,747. Most of the drop is
      consolidation and approved trims.
    - **Finding:** the B3a-150 trim removed the only assertions that
      `reference_stream` and `comparison_streams` reach the alignment request, and
      a mutation of that mapping passes the whole suite.
      - A keyword scan finds up to 311 removed config, path, stream and label
        assertions that weren't re-added in the same file.
      - The repair unit above was added. Unit E waits for it.
  - The five unused video-wiring helpers deleted in lane 1a were a separate
    maintainer amendment, relayed through the controller and recorded in
    `1a.d.md`.
- 2026-10-02: **T6R repair checkpoint accepted by the controller**, at
  `a8a1f12e84e41811de10ab1f2240e42cff2ff656`. Unit E may be dispatched after
  this plan-only checkpoint is committed and its clean-state gate is checked.
  - All ten lanes completed the fixed `53b60b4c..47a9ad4c` assertion audit,
    with exhaustive exclusions, flow classifications and producer mutations in
    `.handoff/test-audit/<lane>.d-repair.md`.
  - Restored checks and commits:
    - 3a: 78, `f969157f`; 1a: 22, `94a943cd`; 1b: 27, `4d351721`;
    - 2: 13, `01a1786d`; 6: 6, `17db3c4b`;
    - 3b: 4, `42464da6`; 4: 2, `4c6ab6ab`; 5: 0, `7f650849`
      (audit-only commit; retained assertions proved its carrier group);
    - 7: 24, `860c5866` and `cfca3318`; 8: 30, `a8a1f12e`.
    Counts follow each record's current-check and historical-site mapping.
  - B3a-150 is repaired: `test_phase_tasks_alignment.py:125,126` checks
    reference/comparison selected audio streams, and `:133,134` checks
    `max_offset_seconds` and `channel_strategy`. The controller's comparison
    mutation now fails the restored assertion; settings mutations also fail.
  - Scope ruling: T6R's newer explicit exclusions do not exempt different-input
    S11/R2 D1 rewrites. Lane 1a's 19 removed exception sites were included;
    12 were restored and seven proved by retained assertions. Unhandled errors
    alone were never accepted as assertion proof.
  - The user explicitly approved the sole one-commit-per-lane exception: one
    supplemental lane 7 commit for two Qt button-parent placement checks.
  - Controller inspected the repair diff and final gate output. Closing native
    `pytest -rf`: **3,069 passed, 90 skipped**, no failures/errors, 139.17s.
    Every task's closing native suite passed; no failing native node IDs were
    reported. Changed-file pyright, Ruff, formatting and import gates passed.
    Docker was not triggered by the repairs; skipped platform execution is not
    claimed as verified. Test lines: **81,505**, from `wc -l tests/**/*.py`.
  - Seven worker chats were dispatched serially with the verbatim instructions
    from `.codex/agents/worker.toml`, explicitly `gpt-6.1-sol` / `medium`.
    All confirmed `CONFIGURED ROLE: worker`; runtime metadata was unavailable.
  - All production mutations were restored and the final checkout was clean.
    An external fast-forward to `a997ef51` during lane 3a was preserved; no
    production changes were committed by the repair workers. Nothing pushed.
