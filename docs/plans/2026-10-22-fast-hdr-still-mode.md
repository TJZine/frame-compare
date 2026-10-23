---
search:
  exclude: true
---

# Opt-in fast HDR still tone mapping

Status: Approved for implementation on 2026-10-22. Base: `v0.7.0` at
`1d11e68f` (all PR #138 checks green).

## Objective

Add an opt-in setting, `color.tonemap_speed = "fast"`, that renders HDR screenshots
much faster while staying reproducible. Fast mode turns off libplacebo's dynamic peak
detection and takes the source peak from stream or static metadata. That makes one
shared Tonemap node safe for screenshots. The default, `"quality"`, keeps today's
behaviour exactly: the peak is measured per frame, with a fresh native node per
screenshot.

Do not offer the old shared-sequence mode. Its pixels change with request order (see
F-Evidence).

## Background and evidence

### Why the default is slow

Screenshots use `frame_policy=independent_frames` (commit `5c15cbf4`). Each screenshot
frame gets its own one-frame `placebo.Tonemap` node, so libplacebo's temporal peak
detector can't carry history from other frames. That repeats native setup for every
screenshot: Vulkan device, renderer, shader compilation and lookup tables.

### Measurements (F-Evidence)

Windows, RTX 5080, 4K, 32 adjacent frames (verification ledger, "Measured performance
cost and next experiment"):

| Mode | First frame | Each later frame |
| --- | --- | --- |
| quality (fresh per still) | ≈1.1 s | ≈1.09 s |
| shared node, detection on | 0.83 s | ≈0.16 s |
| shared node, detection off | not measured on Windows (V2 measures it) | expected ≈0.14–0.16 s |

Docker, software Vulkan, 1080p synthetic PQ clip, median of 3 fresh processes
(MacBook, 2026-10-22):

| Mode | 12 adjacent | 6 sparse | Each later frame |
| --- | --- | --- | --- |
| quality | 4.54 s | 2.23 s | 0.28–0.32 s |
| shared, detection on | 2.44 s | 1.51 s | 0.135 s |
| shared, detection off | 2.34 s | 1.39 s | 0.117 s |

Repeatability: the same frames were rendered in forward, reverse and sparse order on
content whose brightness changes gradually, below the scene-change thresholds.

| Mode | Frames that differ by order | Size |
| --- | --- | --- |
| quality | 0 of 12 | — |
| shared, detection on | 12 of 12 | up to ≈5 codes (8-bit), mean ≈1.6, ≈65% of samples |
| shared, detection off | 0 of 12 | — |

Abrupt dark/bright alternation hides the detection-on effect, because scene-change
detection resets history. The error appears within a scene.

Detection off with `metadata=0` (auto) on one shared node was also checked against a
fresh-node-per-frame reference.
- **Dolby Vision RPU sequence:** frames carrying non-zero L1, none, zero L1, malformed
  and missing L1, as in the Windows extended probe. The result was identical in every
  order.
- **Per-frame HDR10/scene-metadata sequence:** also identical in every order.
- **Not vacuous:** identical pixels with different RPUs rendered into three distinct
  groups (non-zero L1; none or malformed; zero or missing L1).

Fast mode does change the look against quality, because it doesn't adapt to each
frame. On the synthetic clip the mean shift was −1.4 to +3.3 codes per frame, up to 14
codes worst case. Real films will differ more where scene peaks are far from the
metadata.

These are Linux software-Vulkan observations. V2 repeats determinism and timing on
the Windows GPU.

## Decisions

- **D1 Setting.** `color.tonemap_speed`, a new `TonemapSpeed` StrEnum in
  `config/schema_enums.py` with values `quality` (default) and `fast`. CLI:
  `--tm-speed {quality,fast}`. The name describes intent; fast isn't strictly lower
  fidelity, it uses a different source-peak policy.
- **D2 Fast semantics.**
  - Fast sets `dynamic_peak_detection=False` and keeps `metadata=0` (auto). libplacebo
    then uses per-frame stream metadata (Dolby Vision L1 or HDR10+) when present,
    otherwise HDR10 static metadata, otherwise the resolved `src_max` hint.
  - All other tone settings (curve, knee, gamut, contrast recovery, endpoints,
    `use_dovi`) are unchanged. Smoothing, scene thresholds and percentile still pass
    through unchanged; libplacebo ignores them while detection is off.
- **D3 Frame policy follows detection, not the knob.**
  - Screenshot preparation with detection on keeps `independent_frames` (fresh node
    per still).
  - With detection off, it uses one `placebo.Tonemap` node over the clip, reported as
    a new `frame_policy` value, `shared_stateless`.
  - Sequence callers keep `sequence`.
- **D4 Scope.** The setting applies to every libplacebo tone-mapping route resolved
  from config (screenshots, VSView/sequence previews), so previews match screenshots.
  The degraded fallback tonemapper has no peak detection and ignores the setting;
  requested settings still show it.
- **D5 Disclosure and identity.**
  - `tonemap_speed` appears in the requested settings payload and in applied controls.
  - The new frame policy gets a plain label: "Shared (metadata peak, no per-frame
    measurement)".
  - The resolved source-peak origin (`configured`, `max_cll`, `default`, already in
    `ResolvedSourcePeak`) is disclosed. In fast mode with origin `default`, the report
    shows a note and the human log warns that no HDR peak metadata was found and the
    default peak is used.
  - Both values participate in report identity wherever tone controls already do.
- **D6 Presets.** The setting is orthogonal to presets and isn't preset-controlled.
  It is therefore not in the persistence placeholder list
  (`config/persistence.py` keeps its four fields). It persists like other ordinary
  fields.
- **D7 Experimental native reuse.** Fast mode never routes through
  `_still_frame_tonemap` or the dormant experimental `independent=1` path. Removing
  that dormant gate is a separate decision and is out of scope.
- **D8 Default unchanged.** `quality` stays the default; the reference preset is
  unchanged.

## Contract clauses

- **F1 Schema.** Add the enum and the `ColorConfig.tonemap_speed` field with default
  `quality`. Invalid values raise the existing typed configuration error.
  Environment-variable overrides behave like other colour fields.
- **F2 CLI.**
  - `--tm-speed` goes in the "Rendering and alignment" panel, parsed with
    `coerce_cli_choice(..., ("color", "tonemap_speed"), flag="--tm-speed")`.
  - Help text uses `format_enum_choices`. Precedence matches `--tm-curve`.
  - `--help` and `--version` stay runtime-free (no VapourSynth import).
- **F3 Resolution.** `render/prepare.resolve_tonemap_settings` applies the speed.
  `TonemapSettings` gains a `tonemap_speed` field, and fast sets
  `dynamic_peak_detection=False`. Speed is the single source of that override; do not
  add a separate public detection knob.
- **F4 Application.** In `vs/tonemap_libplacebo.apply_libplacebo`:
  - when `still_image` is true and `settings.dynamic_peak_detection` is false, build
    one `core.placebo.Tonemap(clip, **kwargs)` with no `FrameEval` and report
    `frame_policy="shared_stateless"`
  - all other branches stay byte-for-byte equivalent
  - add `"shared_stateless"` to the `LibplaceboTonemap.frame_policy` literal
- **F5 Report.** `services/report/payload.py` and `renderer.py` carry `tonemap_speed`,
  the new frame-policy label and the D5 source-peak note. Update JSON or report schema
  docs where the existing frame-policy and output-encoding facts are documented.
- **F6 Docs.** Plain voice, consistent with the repo's documentation style.
  - `docs/reference/configuration.md`: a new `color.tonemap_speed` entry with values,
    default and trade-off, plus the precedence paragraph.
  - `docs/guides/hdr-tonemapping.md`: a short "Fast screenshots" section covering when
    to use it, the look change and the metadata dependence.
  - `docs/current-cli-contract.md`: the flag, report facts, the frame-policy value and
    precedence.
  - `docs/current-architecture.md`: frame-policy derivation (D3).
- **F7 Tests.** Integration first. Follow existing test owners; no mock-heavy additions.
  - Config, overrides, round-trip and presets tests extended the way
    `contrast_recovery` is covered (`tests/config/`).
  - A CLI flag parsing and precedence test, in the existing CLI option tests.
  - `tests/render/test_tonemap_wiring.py`: fast resolves to detection off and still
    preparation.
  - `tests/vs/test_tonemap_extracted_modules.py` / `test_tonemap_apply.py`: kwargs and
    the frame-policy branch.
  - Report payload and renderer markup tests for the new labels and the identity
    change.
  - `tests/vs/test_integration.py`, real VapourSynth plus libplacebo, gated on
    `probe_libplacebo_runtime()` like the existing native-still tests:
    - (a) fast-mode screenshots through the product path (`apply_tonemap(...,
      still_image=True)` with fast settings) are identical in forward, reverse and
      sparse order, and identical to a fresh-node-per-frame reference with the same
      kwargs
    - (b) the same with per-frame Dolby Vision RPU and metadata variation, using small
      generated or checked-in RPU fixtures with their provenance recorded
    - (c) a sensitivity control: a shared node with detection on differs by order on
      gradual content, so (a) can't pass vacuously
  - `tests/e2e/test_media_tonemap.py` (media tier): one fast-mode CLI run producing
    PNGs and report facts. It runs in the Docker gate.
- **F8 Non-regression.** Quality-mode output, kwargs and report facts are unchanged
  for existing configurations. Existing native-still, sRGB and history tests pass
  unmodified.

## Verification

- **V1 Local gates.** From `.agents/project.md`:
  - focused pytest on touched tests
  - `ruff check`, `ruff format --check`, `pyright --warnings`, the bandit gate and
    `lint-imports`
  - `zensical build --clean --strict`
  - `tests/test_cli_contract_docs.py`

  Do not run the full suite repeatedly; once at the end is enough.
- **V2 Windows native**, on the RTX machine with the installed stock plugin:
  - run the F7 integration tests with `FRAME_COMPARE_REQUIRE_LIBPLACEBO=1`
  - time all three modes on the same 32 Kill Bill frames used in the ledger
    (12382–12413), quality, shared/detection-on (diagnostic only) and fast, with the
    existing probe style
  - record per-frame medians and determinism across forward and reverse order
  - attended run; no installation or driver change
- **V3 Docker gate.** `bash tools/verify_docker_integration.sh` on the MacBook, or the
  PR's Docker Integration workflow. Strict skip semantics apply.
- **V4 Ledger.** Append a short dated section with what ran, the numbers and the
  remaining limits.

## Out of scope

- Native independent mode and vs-placebo fork work (shelved).
- Removing the dormant experimental gate.
- Changing defaults or preset values; tone-curve tuning.
- VSView UI controls for the setting.
- A shared-sequence (detection-on) user mode.

## Approved D4 implementation scope extension — 2026-10-22

The first R review found that the existing VSView session did not receive color
configuration or invoke the product tonemapper. The user explicitly approved
expanding the plan and ownership to implement D4 for VSView. D4 remains required;
this extension supplies its missing caller and transport ownership.

### Unit D — accepted R1 correction

The orchestration alignment phase resolves tone settings with the existing
`render.prepare.resolve_tonemap_settings` owner and carries them in the existing
`AlignmentConfig`, `VSViewSessionRequest`, and generated session payload. Services
must not import render or duplicate preset/override resolution. Serialize the
resolved `TonemapSettings` values and validate/reconstruct their enums at the
generated-session boundary; the installed Pydantic dataclass adapter supports this
round trip. Keep the payload optional for older/direct session callers. Disabled
tonemapping retains the existing preview preparation path.

For configured HDR previews, inspect the original loaded clip's color evidence,
using the existing metadata probe when that evidence is unspecified, and invoke
the existing `apply_tonemap` sequence route before painting overlays. Do not apply
the old preview-default props over a successfully mapped SDR clip. SDR sources and
legacy sessions without settings retain their existing defaults. Preserve source
frame counts, effective FPS, output ordering, `hdr=False` registration, metadata-v5
review authority, sidecar/session identity, and resource cleanup. No viewer controls
or new public settings are added. D3 and F8 continue to govern the native mapper;
sequence quality previews retain temporal sequence behavior rather than acquiring
the screenshot frame policy.

Unit D owns these additional files and their scoped tests/documentation:

- `src/frame_compare/orchestration/phase_alignment.py`
- `src/frame_compare/services/types.py`
- `src/frame_compare/services/alignment_vsview.py`
- `src/frame_compare/vsview/adapter.py`
- `src/frame_compare/vsview/session_script.py`
- `src/frame_compare/vsview/session_runtime.py`
- `tests/orchestration/test_phase_alignment_contract.py`
- `tests/services/test_alignment_workflow_vsview.py`
- `tests/vsview/test_adapter.py`
- `tests/vsview/test_session_script.py`
- `tests/vsview/test_native_tonemap_preview.py` (new native integration proof)
- `docs/current-cli-contract.md`
- `docs/current-architecture.md`
- `docs/guides/hdr-tonemapping.md`

Proof must observe config-to-session settings, enum/JSON round trip, both native
speed policies through the generated-session preparation path, and preservation of
SDR/disabled/legacy handling and alignment metadata. Prefer real VapourSynth and
libplacebo with a captured output registrar over mocking the mapper. Native proof
must honor the required-runtime flag. A native graph/component result is not a
visible GUI or physical-display pass. Use focused verification after this
extension; the full native suite has already run once as requested.

### Unit G — accepted R2 verification correction

Own `tests/vs/test_integration.py` and narrowly scoped guard regression tests in
`tests/vs/test_tonemap_runtime.py`. Make absent or mocked VapourSynth fail before
the module-level skip when `FRAME_COMPARE_REQUIRE_LIBPLACEBO=1`; ordinary optional
runtime absence still skips. Prove both required and optional cases without
installing or removing a runtime. Preserve the existing native pixel/history tests.

Units D and G have disjoint write ownership and may run in parallel. Both use the
`worker` preset for accepted review fixes, remain uncommitted until orchestrator
integration, and retain every original hard rule. R re-reviews the resulting
corrections. The orchestrator records the results under V4 and commits the plan
extension and corrections with precise Conventional Commit subjects.
