Status: Historical
Historical Scope: Archived record of the full opt-in shared alignment offset reuse feature implementation
Historical Owner: Completed Codex feature implementation session

# Shared Alignment Reuse Cache Plan

Historical status note: this plan records the implemented shared alignment reuse
feature, but it is no longer active authority for legacy alignment persistence.
For `previous_offsets = "disabled"` shared-cache write behavior, legacy
`audio_offsets.toml` precedence, and `check_alignment_cached()` lifetime, defer
to `docs/plans/2026-06-07-alignment-persistence-convergence-plan.md`.

## 1. Purpose

Frame Compare currently treats alignment offsets as run-scoped runtime state:

- computed offset cache entries live in `audio_offsets.toml` under the current
  generated/run area
- manual VSPreview confirmations live under the same current generated/run area
- run folders intentionally do not reuse prior run folders

That keeps individual runs isolated, but it makes repeat comparisons pay the
alignment and VSPreview-confirmation cost again even when the same source set,
source settings, and audio-alignment settings are unchanged.

Add an opt-in shared alignment reuse cache under the configured generated cache
area. When enabled, Frame Compare can show the user previously accepted offset
data before opening VSPreview, then either reuse it or let the user redo
alignment in VSPreview.

## 2. Product Decisions

Freeze these decisions for implementation. If implementation evidence shows any
decision is wrong, stop and re-plan before editing more code.

1. Add a public config-only field:

   ```toml
   [audio_alignment]
   previous_offsets = "disabled" # disabled | prompt | always
   ```

   Default is `"disabled"`.

2. Accepted values:
   - `"disabled"`: preserve current behavior. Do not read or write the shared
     alignment reuse cache. Current run-scoped `audio_offsets.toml` behavior
     stays unchanged.
   - `"prompt"`: when a complete valid previous-offset set exists for the
     current unresolved reference/comparison set, display the previous offset
     data on stderr and ask whether to reuse it. `yes` reuses the offsets and
     skips VSPreview for this run. `no` continues through the existing compute
     and optional VSPreview flow.
   - `"always"`: when a complete valid previous-offset set exists, reuse it
     without prompting and without emitting the interactive Rich reuse prompt.
     If no complete valid set exists, continue through the existing alignment
     flow.

   `audio_alignment.cache_results = false` disables alignment cache behavior.
   It is compatible only with `previous_offsets = "disabled"`. Reject
   `cache_results = false` combined with `previous_offsets = "prompt"` or
   `"always"` before the runtime pipeline and before `run --write-config` writes
   to disk. Do not silently treat `previous_offsets` as disabled, because that
   would hide an explicit user request to reuse previous offsets.
   The structured validation errors for this conflict must include both:

   ```json
   {"loc": ["audio_alignment", "cache_results"]}
   {"loc": ["audio_alignment", "previous_offsets"]}
   ```

   This compatibility check is an effective-config validation, not a schema/load
   default. `previous_offsets = "disabled"` with `cache_results = false`
   preserves current behavior and never reads or writes the shared reuse cache.
   `previous_offsets = "prompt"` or `"always"` requires `cache_results = true`
   for both read reuse and accepted-offset persistence.

3. Reuse is all-or-nothing for comparisons that remain unresolved after
   current-run manual overrides are applied. Current-run manual overrides satisfy
   completeness for their comparison keys because they remain highest precedence.
   For the remaining unresolved comparisons, if any comparison lacks a valid
   previous-offset entry, treat the shared reuse cache as unavailable for the run
   and use the existing alignment path for those unresolved comparisons.

4. Reused offsets become `AlignmentResult` values with:
   - `source = "cached"`
   - `algorithm = None` for human-confirmed previous offsets
   - `algorithm = "cross_correlation"` for computed previous offsets
   - `correlation_score = 1.0` for `vspreview_confirmed` previous offsets
   - original persisted `correlation_score` for computed previous offsets
   - `applied = true`

   Do not mark previous shared-cache reuse as `source = "manual"` because manual
   overrides remain the highest-precedence current-run override mechanism.

5. The existing precedence becomes:
   1. current-run manual overrides
   2. complete valid shared previous-offset reuse when enabled and accepted
   3. current-run `audio_offsets.toml`
   4. computed audio correlation
   5. optional VSPreview confirmation

   Current-run manual overrides must continue to win over everything else.

   `audio_alignment.force_interactive = true` remains the user's explicit demand
   to enter VSPreview. It is incompatible with `previous_offsets = "prompt"` and
   `previous_offsets = "always"` because both reuse modes can skip VSPreview.
   Reject that combination before the runtime pipeline with the standard typed
   config/CLI error path. `audio_alignment.use_vspreview = true` remains
   compatible with previous-offset reuse. If reuse is accepted in `"prompt"` mode
   or applied in `"always"` mode, VSPreview is skipped for that run. If the user
   answers `No` in `"prompt"` mode, the existing alignment path continues and
   may launch VSPreview when `use_vspreview = true`. That `No` branch is the redo
   fallback; accepted reuse never opens VSPreview.
   Also reject this incompatible effective config before `run --write-config`
   writes to disk, including when the conflict is created by
   `--force-interactive-alignment` on top of a config that already has
   `previous_offsets = "prompt"` or `"always"`. Do not persist a config that a
   subsequent normal run would reject for this conflict.
   The structured validation errors for this conflict must include both:

   ```json
   {"loc": ["audio_alignment", "force_interactive"]}
   {"loc": ["audio_alignment", "previous_offsets"]}
   ```

   Validation should aggregate applicable mode/config conflicts instead of
   letting validation order hide them. For example, a `run --json` invocation
   with `force_interactive = true` and `previous_offsets = "prompt"` must include
   the `force_interactive + previous_offsets` locations above, the
   JSON/prompt-mode location defined below, and the existing interactive
   alignment locations `["audio_alignment", "force_interactive"]` and
   `["audio_alignment", "use_vspreview"]` when `--force-interactive-alignment`
   forces both fields. If `cache_results = false` is also present, include the
   `cache_results + previous_offsets` locations above in the same aggregate
   error set. Do not allow the existing generic interactive-alignment JSON
   validation to hide the new previous-offset conflict locations or remove
   existing public loc entries.

6. Shared previous offsets are written only after the run has a complete accepted
   offset set whose eligible entries were established under the current run's
   full typed identity facts:
   - offsets computed and applied in the current run may be written
   - offsets confirmed in VSPreview during the current run may be written
   - rejected/unapplied computed offsets must not be written
   - offsets reused from the shared previous-offset cache must not be rewritten
     into the shared cache or refresh their `accepted_at` timestamp
   - offsets loaded from the legacy run-scoped `audio_offsets.toml` must not be
     promoted into the shared cache
   - offsets loaded from pre-existing current-run manual override files must not
     be promoted into the shared cache
   - if any comparison in the source set is resolved by legacy run-scoped
     `audio_offsets.toml` or a pre-existing manual override, write no shared
     cache entries for that source set

   This prevents weaker legacy state from seeding the strongly validated shared
   cache. Existing run-scoped cache hits and pre-existing manual overrides may
   still participate in the current run according to existing precedence, but
   they make the final source set ineligible for shared-cache writes unless the
   user re-confirms every such comparison in VSPreview during this run or every
   such offset is recomputed in this run. Do not write permanently partial shared
   source-set entries.

   Add a services-owned provenance carrier for shared-cache write eligibility.
   It must distinguish at least:
   - `computed_this_run`
   - `vspreview_confirmed_this_run`
   - `shared_previous_offsets`
   - `legacy_audio_offsets`
   - `preexisting_manual_override`

   Shared-cache writes may consume only `computed_this_run` and
   `vspreview_confirmed_this_run`. Do not infer write eligibility from the final
   `AlignmentResult.source`, because current behavior flattens several sources
   into `source = "cached"` or `source = "manual"`.

   The shared cache schema must use one authoritative provenance field:

   ```text
   origin = "computed" | "vspreview_confirmed"
   ```

   Display labels map from this stored origin:
   - `computed` -> `computed`
   - `vspreview_confirmed` -> `confirmed`

   Each shared-cache entry must also store a per-entry timestamp, for example
   `accepted_at = "<UTC ISO-8601 timestamp>"`. The prompt table must display
   this per-entry timestamp rather than relying on file mtime or index mtime,
   because shared index files can be rewritten for unrelated entries.

   Computed entries must persist the computed `correlation_score` and replay it
   when reused. Confirmed entries use `correlation_score = 1.0`.

   Do not overload this provenance with `AlignmentResult.source`. Reused
   previous offsets still become `AlignmentResult(source="cached", ...)` at
   runtime.

   Preserve write-eligible origin before current-run confirmation handling is
   flattened into `AlignmentResult(source="manual")`. VSPreview confirmations
   produced during the current run must carry `origin = "vspreview_confirmed"`
   into shared-cache writes. Computed applied offsets produced during the
   current run carry `origin = "computed"`.

   Pre-existing manual override files are legacy state and are not write-eligible
   for the shared cache. If the implementation must inspect their
   `ManualOverride.confirmed` value for current-run behavior, preserve the
   current loader contract: missing `confirmed` means `true`. Do not write
   `manual_override` provenance to the shared cache in this feature because no
   safe producer exists under the stronger shared-cache identity.

7. Shared cache identity must be stronger than the existing stem key. A shared
   entry must validate all facts needed to avoid silently reusing offsets for a
   different source or source interpretation:
   - selected reference identity
   - comparison identity
   - source path, size, and mtime freshness for reference and comparison
   - configured source trims for reference and comparison
   - effective FPS for reference and comparison
   - selected reference relationship
   - audio alignment settings that affect computed offsets, including sample
     rate, max offset, correlation mode, preprocessing mode, channel strategy,
     thresholds, window/consensus settings, refinement settings, and selected
     audio streams

8. The shared cache file format must be versioned. Invalid, corrupt, or
   unsupported shared cache data degrades to the existing alignment path with a
   warning log event. It must not crash normal runs unless the implementation
   proves the current cache owner already treats equivalent corruption as a
   typed user-visible error.

   Do not require the raw config selector string in the cache identity. Current
   runtime state resolves selectors to source paths and source settings before
   alignment; requiring raw selector strings would force a broader orchestration
   metadata change without improving safety beyond validated resolved identity.

9. The shared cache storage root is:

   ```text
   <resolved paths.generated_dir>/cache/alignment/
   ```

   This path remains shared workspace-level cache state even when
   `paths.use_run_folders = true`, matching the analysis cache pattern. Do not
   store shared reuse entries in a fresh run folder.

   Implementation must add an explicit workspace-level alignment cache path
   instead of reusing the current `WorkspacePaths.cache_dir` name, which
   currently means the shared analysis cache directory. Preferred shape:

   ```python
   WorkspacePaths.shared_alignment_cache_dir
   ```

   Match the existing shared analysis cache shape: add an optional backing field
   such as `alignment_cache_dir: Path | None = None` plus a derived
   `shared_alignment_cache_dir` property, rather than adding a new required
   constructor argument to every `WorkspacePaths` instantiation. `with_run_dir()`
   should preserve the workspace-level path by setting the backing field to
   `self.shared_alignment_cache_dir`, parallel to current
   `analysis_cache_dir` handling.

   In run-folder mode this should continue to point at the base configured
   generated area, for example `generated/cache/alignment/`, while
   `WorkspacePaths.generated_dir` points at the fresh run folder's generated
   directory.

10. Keep the existing run-scoped `audio_offsets.toml` behavior and format unless
    the implementation discovers a small mechanical update is required for
    interop. Do not migrate or repurpose it as the shared cache.

11. The prompt display is human-only and uses Rich on stderr. It must be concise
    and deterministic. Show at least:
    - reference clip label, using orchestration `ClipState.label` when available
      and filename/stem only as a fallback
    - comparison clip label, using orchestration `ClipState.label` when
      available and filename/stem only as a fallback
    - signed frame offset
    - time offset seconds
    - previous offset source label derived from shared-cache `origin`:
      `confirmed` or `computed`
    - per-entry `accepted_at` timestamp from the shared cache
    - shared cache path

    All user- or filesystem-derived display values, including labels, filenames,
    stems, and cache paths, must be rendered Rich-safely. Use
    `rich.markup.escape`, `Text`, or an equivalent non-markup cell path so
    labels containing characters such as `[` and `]` cannot corrupt or hide
    prompt/table content.

12. Prompt text:

    ```text
    Reuse previous alignment offsets? [y/N]
    ```

    Default is `No`. Accepted yes inputs should follow existing CLI yes/no
    conventions if there is a local helper; otherwise support `y` and `yes`
    case-insensitively. EOF or unavailable stdin behaves as `No` for
    `"prompt"`. This soft fallback is deliberate: JSON and quiet modes are
    rejected before runtime, but a human run that loses prompt input should not
    hang or crash and should not silently reuse previous offsets.

    Prompt availability must be detected before any blocking read. Prompt mode
    must check both `stream_is_tty(sys.stdin)` and `stream_is_tty(sys.stderr)`,
    or use an equivalent injected prompt boundary, before calling `readline()`.
    If stderr is not a TTY, do not render the table or prompt and do not attempt
    to read because the prompt surface would be invisible; emit no human
    diagnostic and treat the answer as `No`. If stderr is a TTY but stdin is not
    a TTY, do not render the table or prompt and do not attempt to read; emit
    this deterministic stderr line and treat the answer as `No`:

    ```text
    Previous alignment offset reuse prompt unavailable; continuing without reuse.
    ```

    If both streams are TTYs, render the table and prompt, then treat EOF as
    `No` and emit the same deterministic stderr line before continuing through
    the existing alignment path.

13. `audio_alignment.previous_offsets = "prompt"` is incompatible with
    `run --json`. Reject it before the runtime pipeline with the standard
    config-error JSON payload. This keeps JSON stdout machine-clean without
    requiring runtime cache probing to decide whether a prompt would occur.
    This runtime-branch validation must not prevent `run --write-config` or
    `run --diagnose-paths` from preserving their existing early-exit behavior.
    The separate persisted-config validity check for
    `force_interactive + previous_offsets` still applies before `--write-config`
    writes.
    Successful `run --write-config --json` behavior remains unchanged: it exits
    through the existing write-config path and must not introduce a new success
    JSON payload for this feature.
    The JSON validation error for this conflict uses:

    ```json
    {"loc": ["audio_alignment", "previous_offsets"]}
    ```

14. `audio_alignment.previous_offsets = "always"` is compatible with
    `run --json` because it is non-interactive and does not change the success
    JSON schema. Existing JSON incompatibilities for `use_vspreview` and
    `force_interactive` remain unchanged.

15. `--quiet` is compatible with `"always"`. `--quiet` is incompatible with
    `"prompt"` and must be rejected before the runtime pipeline with the
    standard typed config/CLI error path. Prompt mode is an interactive human
    output surface and should not silently degrade to an unstyled or reduced
    prompt. This runtime-branch validation must not prevent `run --write-config`
    or `run --diagnose-paths` from preserving their existing early-exit behavior.
    The separate persisted-config validity check for
    `force_interactive + previous_offsets` still applies before `--write-config`
    writes.
    The structured error location for this conflict is:

    ```json
    {"loc": ["cli", "quiet"]}
    ```

16. No new `run` flag is required. This is a config-only surface.

17. Successful `run --json` output remains unchanged. Do not add cache reuse
    fields to the machine-readable success payload.

18. Existing `--from-cache-only` analysis semantics are unchanged. Previous
    alignment reuse is not part of analysis cache-only prevalidation. A cache-only
    run may reuse previous alignment offsets when `previous_offsets = "always"`
    and a complete valid set exists, but missing previous alignment offsets must
    not fail `--from-cache-only` by itself.

    Existing `--no-cache` semantics are also unchanged. `--no-cache` remains
    analysis-cache-only and must not delete the shared alignment reuse cache
    under `generated/cache/alignment/`.

19. The shipped default config template must include:

    ```toml
    previous_offsets = "disabled"
    ```

    under `[audio_alignment]`.

20. The human at-a-glance preview must include a `previous offsets` row showing
    the effective mode: `disabled`, `prompt`, or `always`. This is user-visible
    effective configuration, analogous to the existing `interactive alignment`,
    `force interactive`, and `VSPreview` rows.

21. Add a typed alignment request/DTO seam between orchestration and the
    alignment service. The request must carry all data needed by the shared
    reuse cache and prompt display rather than making `services.alignment`
    reconstruct orchestration state from paths. Required facts include:
    - reference path and display label
    - comparison paths and display labels
    - current-run generated directory for run-scoped alignment state
    - workspace-level shared alignment cache directory
    - selected reference identity/fingerprint facts available at orchestration
      level
    - comparison identity/fingerprint facts available at orchestration level
    - reference and comparison source trims
    - reference and comparison effective FPS values
    - effective alignment settings used by cache identity through a
      `utils.types`-owned cache-identity settings DTO covering sample rate, max
      offset, correlation/preprocessing/channel modes, thresholds,
      window/consensus/refinement settings, and selected streams
    - preserved frame props currently passed for VSPreview session generation

    The identity/cache-key facts in this DTO must be layer-neutral primitives or
    dependency-light shared structs owned by `frame_compare.utils.types`.
    `services` must not import orchestration-owned or analysis-owned identity
    types such as `ClipIdentity`, `ClipFingerprint`, or `ClipState`. Do not use
    loose parallel argument lists for new shared-cache identity data. The
    cross-layer alignment request and cache-identity DTOs live in
    `utils.types`; `services.types` may define only service-local policy values,
    write-source provenance enums/carriers, and alignment result carriers.

    Preserve the existing `align_clips(...)` convenience API as a compatibility
    wrapper for existing service/integration tests and non-orchestration callers,
    or keep an equivalent wrapper with the same behavioral contract. The wrapper
    must preserve current behavior only: no shared previous-offset reads, no
    shared-cache writes, and no reconstruction of missing labels/trims/FPS/source
    identity from paths. The richer request path is the only path that may enable
    shared previous-offset reuse. This feature must not force an unrelated broad
    migration of existing direct `align_clips(...)` call sites.

    Preserve `check_alignment_cached()` as a current-run-only compatibility
    seam. It must continue checking only current-run manual overrides and
    run-scoped `audio_offsets.toml`; it must not consult the new shared
    previous-offset cache.

    Add `previous_offsets` as an explicit typed service-side alignment policy
    field, alongside the existing `AlignmentConfig` policy fields, so
    `services.alignment` owns alignment reuse behavior. Do not implement reuse
    mode as raw config branching in orchestration or ad hoc kwargs.

22. Preserve the existing duplicate comparison stem fail-fast contract in both
    the typed request path and the preserved `align_clips(...)` wrapper. Even
    though the new shared cache identity is stronger than stem keys,
    `comparison_streams`, legacy `manual_overrides.toml`, and legacy
    `audio_offsets.toml` remain stem-keyed alignment surfaces. Duplicate
    discovered source stems must continue to fail before alignment/reuse work
    until every stem-keyed alignment surface is explicitly migrated in a separate
    plan.

## 3. Non-Goals

- No per-comparison interactive reuse selection. The feature presents the full
  previous-offset set and asks one yes/no reuse question.
- No full-screen TUI alignment manager screen. The TUI requirement for this
  feature is a styled Rich stderr table plus yes/no terminal input.
- No migration from historical run-folder `audio_offsets.toml` files into the
  shared reuse cache.
- No automatic reuse by default.
- No new JSON success fields.
- No change to generated HTML report alignment UI.
- No Docker, Windows portable, or packaging behavior change beyond normal Python
  package inclusion.

## 4. Risk Classification

Risk tier: full-verification feature work.

Reason:

- config schema and documented config contract change
- CLI human/JSON/quiet contract change
- new filesystem persistence owner
- alignment runtime behavior changes in `services/` and orchestration-visible
  results
- Rich user-visible output change

This is not a Docker or Windows release-path feature. However, because the plan
preserves targeted real FFmpeg-backed integration coverage in
`tests/integration/test_alignment_runtime.py`, the runbook's Docker/runtime gate
applies. Run `bash tools/verify_docker_integration.sh` or record a
documented-only gap if the local environment cannot run it.

## 5. Public Surfaces

Update in lockstep:

- `docs/current-cli-contract.md`
  - document `audio_alignment.previous_offsets`
  - update the `## Config-Only Audio Alignment Surface` section explicitly for
    `previous_offsets = "disabled" | "prompt" | "always"`
  - document that `previous_offsets` is config-only and has no `run` flag
  - document JSON incompatibility for `"prompt"`
  - document quiet incompatibility for `"prompt"`
  - document that `previous_offsets = "prompt" | "always"` requires
    `audio_alignment.cache_results = true`, while
    `previous_offsets = "disabled"` remains compatible with
    `cache_results = false`
  - update the `## run Command Contract` / `### Output Modes` section for the
    new JSON rejection, quiet rejection, stderr prompt/table behavior, and
    prompt-mode TTY fallback rules
  - update the at-a-glance summary contract to include the `previous offsets`
    row and its effective mode values
  - document incompatibility between `force_interactive = true` and
    `previous_offsets = "prompt" | "always"`
  - document `"always"` JSON compatibility and unchanged JSON success schema
  - document prompt-mode human behavior: table/prompt on stderr, default `No`,
    EOF fallback to `No`, non-TTY stdin or non-TTY stderr fallback to `No`, and
    `--no-color` disabling ANSI styling for the reuse table/prompt
  - document that the prompt table displays the shared-cache per-entry
    `accepted_at` timestamp, not file mtime or index mtime
  - document shared alignment cache path and run-folder behavior
  - update Cache Mode Semantics to state that `--no-cache` remains
    analysis-cache-only and does not delete `generated/cache/alignment/`
  - document that `--diagnose-paths` continues to report the resolved configured
    generated root while shared alignment entries live below it at
    `cache/alignment/`
  - update the Persistence Rules section to document that `run --write-config`
    rejects effective configs combining `force_interactive = true` with
    `previous_offsets = "prompt" | "always"` before writing
  - update the Persistence Rules section to document that `run --write-config`
    also rejects effective configs combining `cache_results = false` with
    `previous_offsets = "prompt" | "always"` before writing
- `docs/current-architecture.md`
  - add `<generated>/cache/alignment/` to persistence owners
  - document the shared-cache exception to run-folder scoping, parallel to
    analysis cache
  - document `WorkspacePaths.shared_alignment_cache_dir`
  - document owner module for shared alignment reuse cache
  - document the typed orchestration-to-services alignment request seam used by
    `run_align_phase()` and `services.alignment`
  - document that cache-identity request structs use layer-neutral primitives or
    dependency-light shared types, not orchestration/analysis-owned identity
    types
  - document the services-owned prompt/output helper and write-source provenance
    carrier as part of the alignment owner narrative
- `src/frame_compare/cli/output.py`
  - add the `previous offsets` row to the human at-a-glance preview
- `src/frame_compare/config/defaults.py`
  - include `previous_offsets = "disabled"` in the default config template
- `src/frame_compare/config/schema_models.py`
  - add the enum-like config field with default `"disabled"`
- `tests/config/test_schema.py`
  - lock defaults and valid/invalid values
  - lock default-template inclusion
- `tests/config/test_overrides.py`
  - prove CLI override application preserves config-only
    `audio_alignment.previous_offsets` unchanged
- `tests/cli/test_run_json_errors.py`
  - lock JSON rejection for `"prompt"`
  - lock JSON/config rejection for `force_interactive = true` combined with
    `"prompt"` or `"always"` if the existing CLI error tests are the right owner
  - own `run --write-config --json` pre-write conflict rejection coverage,
    including JSON error payload shape and no config write
- `tests/cli/test_run_output.py` or a focused CLI test module
  - lock quiet rejection for `"prompt"`
  - lock human prompt/table stream placement with semantic assertions
- `tests/cli/test_cli_output.py`
  - lock the `previous offsets` at-a-glance row for disabled, prompt, and always
    modes
- `tests/test_cli_contract_docs.py`
  - update any doc-lock expectations for new config/CLI authority text
  - update architecture-doc authority assertions for
    `WorkspacePaths.shared_alignment_cache_dir`,
    `<generated>/cache/alignment/`, and the new shared-cache run-folder
    exception
  - assert no `run --previous-offsets` option is exposed
  - assert `CLI_OVERRIDE_MAP` does not include `audio_alignment.previous_offsets`
- `tests/services/test_alignment_workflow.py`
  - preserve wrapper/runtime alignment flow, duplicate-stem fail-fast behavior,
    and precedence behavior while adding the typed request path
- `tests/services/test_alignment_workflow_vspreview.py`
  - preserve VSPreview workflow interaction behavior while adding shared reuse
- `tests/services/test_alignment_vspreview.py`
  - preserve existing TTY/prompt launch policy coverage and add prompt-safety
    assertions where that owner remains involved
- `tests/services/test_alignment_cache.py`
  - preserve legacy run-scoped `audio_offsets.toml` versioning, freshness, and
    serialization behavior while proving legacy cache hits are distinct from
    shared-cache write eligibility
- `tests/integration/test_alignment_runtime.py`
  - preserve targeted runtime proof that `check_alignment_cached()` and
    direct/runtime compatibility seams remain current-run-only and isolated from
    the shared previous-offset cache using the existing real FFmpeg-backed
    generated-media coverage
- `tests/cli/test_run_request_config.py`
  - prove request/config construction preserves `previous_offsets`
- `tests/cli/test_run_command.py`
  - pin `--diagnose-paths` documentation/test expectations for the cache root
    and shared `cache/alignment/` placement if that test remains the owner
  - prove `--no-cache` does not delete `generated/cache/alignment/` if this CLI
    test remains the cache-mode owner
  - own successful `run --write-config --json` no-success-payload behavior and
    non-JSON `run --write-config` pre-write conflict rejection if those branches
    remain in `handle_run()`
- `tests/orchestration/test_phase_tasks_alignment.py`
  - own typed request construction from `run_align_phase()`, including labels,
    trims, FPS, effective alignment settings, current-run path, shared alignment
    cache path, duplicate-stem fail-fast behavior, and shared-cache identity facts
- `tests/orchestration/test_phase_tasks_outputs.py`
  - preserve downstream align output mapping after the typed request change:
    `ClipAlignmentState.relative_offset_frames`, source-frame mapping,
    normalized selected frames, final trim ranges, and alignment warnings remain
    unchanged for equivalent alignment results
- `tests/orchestration/test_execute_run_phase_integration.py`
  - preserve an equivalent phase integration monkeypatch seam for alignment
    results after `run_align_phase()` moves from direct `align_clips(...)` kwargs
    to the richer request entrypoint, so execute-run phase ordering and
    align-to-render/report propagation remain testable
- `tests/orchestration/test_preflight.py`
  - own initial `WorkspacePaths.shared_alignment_cache_dir` resolution under the
    configured generated root
- `tests/orchestration/test_preparation.py`
  - own the optional-backed `WorkspacePaths.shared_alignment_cache_dir` property
    shape and `with_run_dir()` preservation of the shared alignment cache path
    alongside existing shared analysis cache invariants
  - prove `--no-cache` cleanup preserves `generated/cache/alignment/` alongside
    existing alignment-offset-cache preservation
- `tests/services/test_alignment_core.py`
  - own `AlignmentConfig`/typed-service default and construction coverage for
    the new request/provenance path where the service type owner changes

## 6. Owner Seams

Use existing owners and add one focused owner.

1. New shared cache owner:

   ```text
   src/frame_compare/services/alignment_reuse_cache.py
   ```

   Responsibilities:
   - shared cache path calculation below `WorkspacePaths.shared_alignment_cache_dir`
   - versioned file naming or index format
   - stable cache identity/fingerprint
   - TOML read/write
   - entry validation and freshness checks
   - typed result DTOs for reusable offset candidates
   - atomic writes through `frame_compare.utils.atomic_write`

2. Existing alignment coordinator:

   ```text
   src/frame_compare/services/alignment.py
   ```

   Responsibilities:
   - preserve existing current-run precedence
   - insert shared reuse after current-run manual overrides and before
     current-run `audio_offsets.toml`
   - save accepted final offsets to the shared cache when enabled
   - keep VSPreview confirmation behavior delegated
   - accept a typed alignment request/DTO that includes separate current-run
     alignment state and shared alignment reuse paths; do not infer one from the
     other
   - consume labels, trims, effective FPS, and selected-reference identity from
     the typed request rather than reconstructing orchestration state from paths

3. Existing VSPreview interaction owner:

   ```text
   src/frame_compare/services/alignment_vspreview.py
   ```

   Responsibilities:
   - remain owner of VSPreview launch and source-frame confirmation prompts
   - do not absorb shared cache read/write policy

4. Shared path owner:

   ```text
   src/frame_compare/utils/types.py
   src/frame_compare/orchestration/preflight.py
   ```

   Responsibilities:
   - add and preserve `WorkspacePaths.shared_alignment_cache_dir`
   - implement it as an optional-backed derived property, parallel to
     `shared_analysis_cache_dir`, rather than a new required constructor
     argument
   - keep the shared alignment cache path stable when `with_run_dir()` switches
     `generated_dir` into a fresh run folder
   - avoid changing the meaning of existing `WorkspacePaths.cache_dir`, which is
     the shared analysis cache directory today

5. Layer-neutral request type owner:

   ```text
   src/frame_compare/utils/types.py
   ```

   Responsibilities:
   - define dependency-light shared request/cache-identity structs needed by
     both orchestration and services
   - keep those structs free of imports from `frame_compare.orchestration`,
     `frame_compare.analysis`, or CLI modules
   - allow services to receive selected-reference/comparison identity facts
     without depending on orchestration-owned or analysis-owned identity classes
   - own the cross-layer alignment request and cache-identity DTOs; do not place
     those DTOs in `services.types`

6. Orchestration request builder:

   ```text
   src/frame_compare/orchestration/phase_tasks.py
   ```

   Responsibilities:
   - build the typed alignment request from `RunContext`, `ClipState`, and
     `WorkspacePaths`
   - pass `ctx.workspace.generated_dir` as current-run alignment state
   - pass `ctx.workspace.shared_alignment_cache_dir` as shared reuse state
   - pass `ClipState.label`, effective FPS, source trims, and selected-reference
     identity facts needed for cache identity and display
   - keep phase output behavior unchanged except for offsets selected by the new
     reuse policy

7. Prompt/output helper:

   Add a narrow services-owned helper so `services.alignment` does not import
   upward into the CLI layer:

   ```text
   src/frame_compare/services/alignment_reuse_prompt.py
   ```

   The helper may use Rich and `frame_compare.utils.terminal`, but it must not
   import from `frame_compare.cli`. Do not introduce an import-layer violation to
   reuse an existing CLI output helper.

   The prompt helper owns terminal safety. It must check stdin and stderr TTY
   status before reading, treat non-TTY stdin or non-TTY stderr as `No`, and
   expose a testable seam so owner-level and CLI tests can prove non-TTY and EOF
   behavior without hanging.

8. Config override owner:

   ```text
   src/frame_compare/config/overrides.py
   ```

   No new CLI flag is expected, so this should not need a new override mapping
   unless implementation evidence shows config write or diagnostics need it.

9. CLI pre-write validation owner:

   ```text
   src/frame_compare/cli/run_command.py
   ```

   Responsibilities:
   - add a narrow validation seam for effective configs about to be persisted by
     `run --write-config`
   - reject `force_interactive = true` combined with
     `previous_offsets = "prompt"` or `"always"` before writing to disk
   - reject `cache_results = false` combined with `previous_offsets = "prompt"`
     or `"always"` before writing to disk
   - keep this separate from Pydantic schema/load-time validation so
     `run --diagnose-paths` preserves its existing early-exit behavior
   - keep regular runtime contract validation for JSON/quiet prompt mode in the
     existing runtime validation path

## 7. Implementation Notes

These notes constrain behavior without prescribing local helper names.

1. Represent the public config value as a literal type, for example:

   ```python
   Literal["disabled", "prompt", "always"]
   ```

   Prefer a type alias if neighboring config code already uses aliases for
   enum-like config fields.

2. Use a typed shared cache candidate DTO rather than passing raw TOML dictionaries
   through alignment code.

3. Treat unknown TOML data as `object` at the file boundary, then validate and
   narrow. Do not use `Any` for cache data.

4. Include `format_version = "1"` or equivalent at the shared cache file/root.

5. Prefer one shared cache index/file per source-set fingerprint if it keeps
   invalidation simple. A single monolithic TOML file is acceptable only if
   write/update behavior remains deterministic and corruption of one entry does
   not make the whole feature brittle.

6. Use stable ordering for all serialized entries and displayed rows.

7. Cache write failure should log a warning and allow the run to succeed, matching
   existing alignment cache posture.

8. Cache read corruption or version mismatch should log a warning and continue
   through the existing alignment path.

9. In prompt mode, suspend any active Rich progress before printing the table and
   prompt, then resume afterward. Follow the existing VSPreview interaction
   pattern.

10. Do not eagerly import VapourSynth or VSPreview code from simple CLI paths.

## 8. Test Plan

Primary verification mode: `contract-first`.

Secondary verification mode: `integration-ops` for the alignment runtime boundary.
Use mocked/local-filesystem tests for shared-cache, prompt, and orchestration
policy edges, and preserve targeted real FFmpeg-backed integration coverage for
the existing `align_clips(...)` and `check_alignment_cached()` compatibility
seams.

Verification classification: `new regression/contract test required`.

Add focused tests before relying on full gates:

1. Config schema tests:
   - default is `"disabled"`
   - `"disabled"`, `"prompt"`, and `"always"` are accepted
   - invalid values fail config validation

2. Shared cache owner tests:
   - writes and loads a complete valid source set
   - rejects stale source freshness
   - rejects mismatched trims/effective FPS/audio settings
   - rejects partial unresolved comparison sets for all-or-nothing reuse
   - write eligibility requires a complete source set of entries from
     `computed_this_run` and/or `vspreview_confirmed_this_run`
   - corrupt or unsupported version degrades through the documented warning path
   - write failure logs and does not raise
   - persisted provenance uses exactly `computed | vspreview_confirmed`
   - each persisted reusable offset stores a per-entry UTC timestamp such as
     `accepted_at`, and display code uses that timestamp rather than file mtime
   - prompt/display candidates use only per-entry `accepted_at` as the
     authoritative timestamp
   - computed entries persist and replay the original `correlation_score`
   - confirmed entries replay `correlation_score = 1.0`
   - display source labels are derived from provenance without changing runtime
     `AlignmentResult.source`
   - entries with unsupported `origin = "manual_override"` are treated as
     invalid shared-cache data and do not get reused
   - legacy or hand-authored override records with missing `confirmed` preserve
     the current loader behavior for current-run application but are not
     write-eligible for the shared cache
   - legacy run-scoped `audio_offsets.toml` hits are not promoted into the
     shared cache
   - pre-existing manual override hits are not promoted into the shared cache

3. Alignment coordinator tests:
   - duplicate comparison stems still fail fast in the typed request path and
     preserved `align_clips(...)` wrapper
   - current-run manual override wins over shared previous offsets
   - mixed current-run manual override plus complete shared previous offsets for
     remaining comparisons reuses the shared offsets for only the unresolved
     comparisons
   - `"disabled"` does not read or write shared reuse cache
   - `cache_results = false` with `"disabled"` preserves current behavior and
     does not read from or write to the shared reuse cache
   - `cache_results = false` with `"prompt"` or `"always"` is rejected before
     reuse, compute, VSPreview, or shared-cache persistence
   - `"always"` reuses complete valid previous offsets and skips compute and
     VSPreview
   - `"always"` with `use_vspreview = true` still skips VSPreview when complete
     valid previous offsets are reused
   - `"always"` with `force_interactive = true` is rejected before alignment
   - `"prompt"` yes reuses complete valid previous offsets and skips VSPreview
   - `"prompt"` yes with `use_vspreview = true` still skips VSPreview
   - `"prompt"` no falls through to existing compute/VSPreview path and may
     launch VSPreview when `use_vspreview = true`
   - `"prompt"` with `force_interactive = true` is rejected before alignment
   - partial shared cache falls through to existing path
   - accepted computed/confirmed offsets are written to shared cache only when
     every comparison has an applied write-eligible offset
   - current-run computed offsets are eligible for shared-cache writes
   - current-run VSPreview confirmations are eligible for shared-cache writes
   - services-owned write-source carrier distinguishes `computed_this_run`,
     `vspreview_confirmed_this_run`, `shared_previous_offsets`,
     `legacy_audio_offsets`, and `preexisting_manual_override`
   - shared-cache writes consume only `computed_this_run` and
     `vspreview_confirmed_this_run`
   - reuse-only runs using `shared_previous_offsets` do not rewrite shared-cache
     entries or refresh `accepted_at`
   - legacy current-run `audio_offsets.toml` cache hits are applied when valid
     but not written into the shared cache
   - pre-existing manual overrides are applied when valid but not written into
     the shared cache unless re-confirmed in VSPreview during this run
   - if any comparison in the source set is resolved by legacy `audio_offsets`
     or pre-existing manual override, no shared-cache entries are written for
     that source set

4. Orchestration bridge tests:
   - `run_align_phase()` builds the typed alignment request with both
     `current_run_alignment_dir = ctx.workspace.generated_dir` and
     `shared_alignment_cache_dir = ctx.workspace.shared_alignment_cache_dir`
   - run-folder mode keeps current-run `audio_offsets.toml` and VSPreview
     artifacts under the fresh run folder while shared previous-offset reuse
     reads/writes under the workspace-level `generated/cache/alignment/`
   - `WorkspacePaths.shared_alignment_cache_dir` remains stable across
     `with_run_dir()` and does not change the existing `WorkspacePaths.cache_dir`
     analysis-cache meaning
   - labels, effective FPS values, trims, and preserved frame props from
     `ClipState` are passed through the typed request without lossy path/stem
     reconstruction
   - effective alignment settings used by shared-cache identity are carried in
     the typed request, not retrieved through ad hoc service-side config lookup
   - shared request/cache-identity structs are layer-neutral and services do not
     import orchestration-owned or analysis-owned identity types
   - reference and comparison identity/fingerprint facts are both present in the
     typed request used for shared-cache identity
   - existing direct `align_clips(...)` service/integration call sites continue
     to work through a compatibility wrapper or equivalent preserved API
   - direct `align_clips(...)` compatibility calls do not read from or write to
     the shared previous-offset cache and do not synthesize missing shared-cache
     identity data from paths
   - `check_alignment_cached()` remains current-run-only and does not consult
     the shared previous-offset cache
   - duplicate comparison stems still fail before shared reuse or current-run
     alignment work in the main orchestration path

5. CLI contract tests:
   - `run --json` rejects `"prompt"` with the standard config-error JSON payload
     and pins the structured `validation_errors[*].loc` path for
     `["audio_alignment", "previous_offsets"]`
   - `run --json` does not reject `"always"` solely because of previous-offset
     mode
   - `--quiet` rejects `"prompt"`
     and pins the structured error location `["cli", "quiet"]` for the
     quiet/prompt conflict
   - `force_interactive = true` rejects `"prompt"` and `"always"` through the
     standard config/CLI error path
     and pins structured error locations
     `["audio_alignment", "force_interactive"]` and
     `["audio_alignment", "previous_offsets"]`
   - `cache_results = false` rejects `"prompt"` and `"always"` through the
     standard config/CLI error path
     and pins structured error locations
     `["audio_alignment", "cache_results"]` and
     `["audio_alignment", "previous_offsets"]`
   - combined cases such as `run --json` with `force_interactive = true` and
     `previous_offsets = "prompt"` aggregate all applicable structured error
     locations, including `["audio_alignment", "force_interactive"]`,
     `["audio_alignment", "use_vspreview"]`, and
     `["audio_alignment", "previous_offsets"]`, instead of being hidden by the
     existing generic interactive-alignment JSON validation. If
     `cache_results = false` is also present, include
     `["audio_alignment", "cache_results"]` in that aggregate error set.
   - the new runtime-branch incompatibility checks do not prevent
     `run --write-config` and `run --diagnose-paths` from preserving their
     existing early-exit behavior
   - `run --write-config` rejects an effective config that combines
     `force_interactive = true` with `previous_offsets = "prompt"` or
     `"always"` before writing to disk
   - `run --write-config --json` rejects that same pre-write conflict with the
     standard JSON config-error payload and does not write the config
   - `run --write-config` rejects an effective config that combines
     `cache_results = false` with `previous_offsets = "prompt"` or `"always"`
     before writing to disk
   - `run --write-config --json` rejects the `cache_results = false` plus
     previous-offset reuse-mode conflict with the standard JSON config-error
     payload and does not write the config
   - successful `run --write-config --json` keeps the existing no-success-payload
     behavior
   - JSON/quiet/pre-write conflict tests assert the runtime runner is not invoked
     before rejection
   - `run --force-interactive-alignment --write-config` rejects before writing
     when the loaded config already has `previous_offsets = "prompt"` or
     `"always"`
   - `run --write-config` round-trips `previous_offsets` from config without
     requiring a CLI flag
   - `run --diagnose-paths` keeps its existing cache root semantics while docs
     explain that shared alignment entries live below that root at
     `cache/alignment/`
   - pre-write validation for `force_interactive + previous_offsets` lives in
     the CLI write-config path, not schema/load-time validation, so
     `run --diagnose-paths` remains unaffected
   - pre-write validation for `cache_results + previous_offsets` lives in the
     same effective-config validation seam and does not change
     `run --diagnose-paths` early-exit behavior
   - human prompt/table output goes to stderr, not stdout
   - `--no-color` disables ANSI styling for the previous-offset table/prompt
   - EOF or unavailable stdin in prompt mode behaves as `No`, does not reuse
     previous offsets, emits the deterministic fallback line on stderr when
     stderr is a TTY, and continues through the existing alignment path
   - non-TTY stdin is detected before reading, does not block, behaves as `No`,
     emits the deterministic fallback line on stderr when stderr is a TTY, and
     continues through the existing alignment path without rendering the table
     or prompt
   - redirected/non-TTY stderr prevents prompting before reading, behaves as
     `No`, emits no human diagnostic, and continues through the existing
     alignment path without rendering the table or prompt
   - the rendered previous-offset table uses `ClipState.label` in deterministic
     comparison order and falls back to filename/stem only when labels are absent
   - labels, filenames/stems, and cache paths containing Rich markup characters
     render as literal text rather than markup
   - human at-a-glance preview includes `previous offsets` with effective values
     `disabled`, `prompt`, and `always`

6. Prompt boundary owner tests:
   - owner-level tests cover yes, no/default, EOF, non-TTY stdin, and non-TTY
     stderr without invoking the full CLI
   - owner-level tests prove no blocking read occurs unless stdin and stderr are
     both TTYs
   - owner-level tests prove the deterministic fallback line is emitted only
     when stderr is visible and prompting cannot complete
   - owner-level or workflow tests assert progress is suspended before rendering
     the previous-offset table/prompt and resumed afterward
   - owner-level tests cover no-color rendering and label fallback semantics
   - owner-level tests cover Rich-safe rendering for labels and paths containing
     markup-like characters
   - owner-level tests cover provenance-to-display-label mapping:
     `computed -> computed`, `vspreview_confirmed -> confirmed`

7. Config-only contract tests:
   - `frame-compare run --help` does not expose `--previous-offsets`
   - declared Typer run options, using the existing `_declared_run_options()`
     contract-test helper pattern, do not include `previous-offsets`
   - `CLI_OVERRIDE_MAP` does not include `audio_alignment.previous_offsets`
   - CLI override application preserves config-only
     `audio_alignment.previous_offsets`
   - run request/config construction preserves `previous_offsets` from the
     loaded config
   - `docs/current-cli-contract.md` documents `previous_offsets = "disabled"`
     in the Config-Only Audio Alignment Surface and persistence sections

8. Docs lockstep:
   - update any existing docs-contract test that checks
     `docs/current-cli-contract.md`
   - assert the CLI contract `Output Modes` section documents JSON rejection,
     quiet rejection, stderr prompt/table behavior, and prompt-mode TTY fallback
     rules
   - assert the CLI contract documents prompt stderr output, default `No`,
     EOF/non-TTY fallback to `No`, and `--no-color` behavior
   - assert the CLI contract documents per-entry `accepted_at` as the timestamp
     displayed in the reuse table
   - assert the CLI contract Cache Mode Semantics section says `--no-cache`
     preserves `generated/cache/alignment/`
   - assert the CLI contract documents the at-a-glance `previous offsets` row
   - update any existing docs-contract test that checks
     `docs/current-architecture.md`
   - assert the architecture doc covers the typed alignment request seam,
     layer-neutral cache-identity request structs, services-owned prompt helper,
     and write-source provenance carrier

Required local commands:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/bandit -c pyproject.toml -r src --severity-level medium
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
bash tools/verify_docker_integration.sh
```

Expected outcomes:

- Pyright passes under strict `src` settings.
- Ruff passes without introducing formatting/import churn.
- Bandit reports no new medium-or-higher issues.
- Pytest passes, including new config/CLI/cache/alignment tests.
- Import-linter confirms no layer violations from CLI/Rich/cache wiring.
- Docker/runtime integration gate passes. If the local host cannot run it, record
  the Docker/runtime proof as documented-only and do not claim local runtime
  verification.

## 9. Files In Scope

Expected production files:

- `src/frame_compare/config/schema_models.py`
- `src/frame_compare/config/defaults.py`
- `src/frame_compare/services/alignment.py`
- `src/frame_compare/services/alignment_reuse_cache.py`
- `src/frame_compare/services/alignment_reuse_prompt.py`
- `src/frame_compare/services/types.py`
  - add the typed service-side `previous_offsets` alignment policy field and any
    service-local write-source provenance enums/carriers or alignment result
    carriers; do not place cross-layer alignment request/cache-identity DTOs in
    this module
- `src/frame_compare/services/alignment_vspreview.py` only if prompt/progress
  coordination requires a small shared interaction hook
- `src/frame_compare/cli/run_command.py`
- `src/frame_compare/cli/output.py`
- `src/frame_compare/utils/types.py`
  - own the layer-neutral typed alignment request/cache-identity DTOs and the
    optional-backed `WorkspacePaths.shared_alignment_cache_dir` property
- `src/frame_compare/orchestration/preflight.py`
- `src/frame_compare/orchestration/phase_tasks.py`

Expected tests:

- `tests/config/test_schema.py`
- `tests/config/test_overrides.py`
- `tests/services/test_alignment_reuse_cache.py`
- `tests/services/test_alignment_cache.py`
- `tests/services/test_alignment_core.py`
- `tests/services/test_alignment.py` or existing focused alignment tests
- `tests/services/test_alignment_workflow.py`
- `tests/services/test_alignment_workflow_vspreview.py`
- `tests/integration/test_alignment_runtime.py`
- `tests/orchestration/test_execute_run_run_folders.py` or a focused path test
  for shared alignment cache path preservation across run-folder switching
- `tests/orchestration/test_preflight.py`
- `tests/orchestration/test_preparation.py` or a focused `WorkspacePaths` owner
  test for shared alignment cache path invariants
- `tests/orchestration/test_phase_tasks_alignment.py` or a focused orchestration
  bridge test for typed request construction
- `tests/orchestration/test_phase_tasks_outputs.py`
- `tests/orchestration/test_execute_run_phase_integration.py`
- `tests/services/test_alignment_vspreview.py` only for interaction/progress
  changes
- `tests/services/test_alignment_reuse_prompt.py` or the focused owner test file
  matching the final prompt helper location
- `tests/cli/test_run_json_errors.py`
- `tests/cli/test_run_output.py`
- `tests/cli/test_cli_output.py`
- `tests/cli/test_run_request_config.py`
- `tests/cli/test_run_command.py`
- `tests/test_cli_contract_docs.py`

Expected docs:

- `docs/current-architecture.md`
- `docs/current-cli-contract.md`
- `docs/DECISIONS.md` only if the implementer wants a durable historical note;
  not required by this plan.

## 10. Files Out Of Scope

- `src/frame_compare/render/**`
- `src/frame_compare/services/report/**`
- `src/frame_compare/vs/**`
- `src/frame_compare/vspreview/adapter.py` unless implementation evidence shows
  launch request metadata must be extended
- Docker files and verification scripts
- Windows portable tooling
- existing historical plan files

## 11. Invariants To Preserve

- `audio_alignment.previous_offsets = "disabled"` preserves current behavior.
- `audio_alignment.previous_offsets = "prompt" | "always"` requires
  `audio_alignment.cache_results = true`; no shared reuse mode silently operates
  while alignment cache behavior is disabled.
- `audio_alignment.previous_offsets` remains config-only; no `run` flag or
  override-map entry is added.
- `run --json` stdout remains a single parseable JSON object on success and on
  typed config errors.
- No human Rich output appears on JSON stdout.
- Current-run manual overrides remain highest precedence.
- Shared cache reuse never applies stale or partial unresolved offset sets.
- `force_interactive = true` never silently skips VSPreview because of previous
  shared offsets.
- Prompt-mode EOF or unavailable stdin never silently reuses previous offsets.
- Rejected computed offsets are not persisted as reusable previous offsets.
- Run folders remain fresh per run; shared reuse cache lives outside the fresh
  run folder.
- Alignment cache identity uses typed orchestration facts passed through the
  alignment request/DTO, not ad hoc path/stem reconstruction.
- Existing current-run `audio_offsets.toml` cache format is not repurposed.
- Simple CLI commands do not import VSPreview/VapourSynth-heavy modules eagerly.
- Import-linter layer contracts continue to pass.

## 12. Rollback Surface

Rollback should be straightforward:

- remove the config field and docs entries
- remove the `WorkspacePaths.shared_alignment_cache_dir` path field/property
- remove the new shared cache owner
- remove the shared-reuse branch from `services.alignment`
- remove new tests

Because the feature defaults to `"disabled"`, rollback risk to users who did not
opt in is low. Shared cache files under `<generated>/cache/alignment/` are
generated state and can be ignored by older versions.

## 13. Stop And Re-Plan Triggers

Stop before continuing if any of these are discovered:

- stable source identity facts are unavailable even after adding the planned
  typed alignment request/DTO, or obtaining them would require reshaping
  ownership beyond `phase_tasks` request construction
- the typed alignment request/DTO would require moving orchestration-only types
  into `services` or creating an import-layer violation
- supporting `"always"` safely requires per-comparison interactive selection
  rather than the planned single yes/no decision
- import-layer rules make any clean prompt/output owner impossible without
  architecture changes
- existing cache-only semantics conflict with previous-offset reuse in a way that
  would change documented `--from-cache-only` behavior
- VSPreview confirmation currently relies on manual override files in a way that
  makes final accepted-offset extraction ambiguous
- Docker/runtime verification cannot be run and the implementation handoff does
  not explicitly record the runbook-required documented-only gap
- full verification requires Windows or real VSPreview runtime proof beyond the
  planned tests

## 14. Suggested Implementation Order

1. Add config schema field and tests.
2. Add typed alignment request/DTO and orchestration bridge tests.
3. Add shared cache owner with standalone tests.
4. Add workspace-level shared alignment cache path plumbing.
5. Add semantic CLI preflight rejection for JSON/quiet prompt mode and
   force-interactive/reuse-mode conflicts.
6. Wire `"always"` reuse through alignment with tests.
7. Wire `"prompt"` display, EOF fallback, and yes/no branching with tests.
8. Add shared cache writes after accepted final alignment results.
9. Update architecture and CLI contract docs.
10. Run focused tests, then full verification.
