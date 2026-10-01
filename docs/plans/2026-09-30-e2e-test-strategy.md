---
search:
  exclude: true
---

Status: Active
Scope: Make real-CLI end-to-end tests the primary proof for Frame Compare features, prune unit tests that E2E or retained integration tests already prove, and change the repository rules so low-value unit tests stop being added.
Owner: Claude controller session (planning, adjudication, verification); Codex executes units A, B and C through `.handoff/` prompts. Branch `agent/e2e-test-strategy`.

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
  - **Docker** (`tools/verify_docker_integration.sh`) runs
    `tests/integration/ tests/vs/` in the `frame-compare-test` image. It then proves
    the production image with one real `frame-compare run` on two FFmpeg-generated
    clips, and with `doctor --json`.
    - The test service runs as the image's `framecompare` user (UID 1000). The
      production proof runs as the host UID (`FRAME_COMPARE_HOST_UID`).
    - The hosted `docker-integration.yml` job runs on amd64, and only for a
      path-filtered subset of changes. A recent hosted run's verification step took
      about 2 minutes.
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

**Goal:** any credible feature regression fails an E2E test that drives the real
`frame-compare` executable against generated media and leaves an artifact someone
can inspect. The unit suite shrinks to tests that guard something E2E cannot reach
reliably. The repository rules then keep it that way.

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

**S6. Deletion bar (units B and C).** Each test belongs to exactly one cluster; a
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
  (E*/M*) or retained integration test fail. Proven by C2.
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

  These are the proofs other tests are deleted against. They may lose only
  `junk:duplicate` tests within themselves.
- **`vsview`, `windows_portable` and `workflows`** may lose tests only as `junk:*`.
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

- Read-only work. There are eight lanes, run as two waves of at most six workers:
  1. `services` alignment (`test_alignment_*`, `alignment_request_test_support`);
  2. `services` other;
  3. `orchestration`;
  4. `cli`;
  5. `render`, `vs`, `analysis`;
  6. `config`, `utils`, root `tests/*.py`;
  7. `vsview`;
  8. `windows_portable`, `workflows`, `scripts`, `manual`.
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
  `junk:` record in lanes 1–4 and a sample of at least one in five elsewhere.
- The approved records become unit C's scope.

### Unit C: deletions (handoff written after checkpoint B)

- **C1:** one area per commit, **serially**, in the lane order above.
- **C2:** mutation proof for every approved `covered:` cluster, before deleting it.
  For each behavior the cluster asserts:
  1. Apply the proposed mutation.
  2. Run the cluster **and** its covering test. Both must fail on an assertion, not
     an exception, import error or crash of the child process. Media-tier covering
     tests run through the verify script with `--pytest-path`.
  3. Restore with `git checkout -- <file>` and confirm `git status` shows no source
     change.

  Record each command and failing assertion in the ledger. A behavior whose
  covering test doesn't fail keeps its tests; the ledger records why. Mutations are
  never committed, and unit C is serial so they never overlap another run.
- **C3:** delete the unlocked production seams, and update any authority document
  that names a deleted file, in the same commit (S7).
- **C4:** per commit, run:
  - the area's remaining tests;
  - `pyright --warnings`, `ruff check .`, `ruff format --check .`, `lint-imports`;
  - the full native `pytest -q`;
  - the verify script when the commit touches a media-tier owner or deletes
    production code.

  Report the `git diff --numstat` split into production and test lines.

Checkpoint C (controller): spot-check the mutation records and the diff, re-run the
full native gate and one Docker gate, then update the inventory table in the
execution record.

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
- Commits use `git commit --only -- <paths>`, one per task, with a Conventional
  Commit subject. Workers sharing the checkout never rely on the shared index.

## Stop conditions

Any of these stops the unit and sends a `blocked` message:

- a required scenario fact isn't exposed where Baseline says it lives;
- a media scenario can't be made byte-identical across two Docker runs;
- a retained test fails on the base;
- a deletion needs a production behavior change;
- a covering test that doesn't fail under its mutation, where the worker would have
  to weaken the cluster's classification rather than keep the cluster;
- any conflict between this plan and an authority document not listed in S5 or S8.

## Verification summary

| Unit | Native | Docker | Other |
| --- | --- | --- | --- |
| A1, A4 | `pytest -q tests/e2e`, linters on owned files | — | skill front matter and link check (A4) |
| A2 | media tier skipped | direct compose run ×2, byte-identical summaries | — |
| A3 | `tests/workflows`, `tests/vs/test_runtime_contract.py`, `bash -n` | none (fake-docker tests) | YAML parses |
| A5 | full gate | verify script ×2 | 3 mutations fail M5/M3/M4 |
| B | none (read-only) | — | ledger completeness |
| C | area tests, full gate per commit | when media owners or production code change | mutation records |

## Residual risks

- Cross-architecture determinism is confirmed only by A5's emulated amd64 run or a
  hosted run, and must be confirmed before unit C (Checkpoint A).
- Windows runs only the CLI tier. Windows media behavior stays covered by the
  hosted Windows portable route and the `platform` keep category.

## Rollback

Each task is one commit, so rollback is `git revert <sha>`. Unit C commits are
independent per area. Reverting one restores its tests and any seams it deleted.

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
