Status: Active
Scope: Restore and improve legacy-quality screenshot geometry alignment, active-image overlay placement, and VapourSynth fpng screenshot writing for mixed-resolution and letterbox/pillarbox sources.
Owner: Next Codex cleanup-loop session; the main session is orchestrator only and must delegate validation, implementation, and review through the cleanup-loop workflow.

# Screenshot Geometry And FPNG Redesign

## User Intent

The maintainer confirmed that the newly implemented VSPreview source-frame alignment
flow is working and is much better, but one test clip still exposes a screenshot
alignment problem: one source has left/right black bars, the clips align in the
viewer when set to fit height, but generated screenshot overlays can land over the
black bars instead of the active image.

The maintainer clarified that the legacy implementation in
`C:\Software\video\frame-compare-legacy` is important because sources can differ in
strange ways that break exact pixel-to-pixel screenshot alignment. The new
implementation should restore that class of capability as at least an option, and
can improve the design rather than porting it mechanically. The maintainer also
expects the screenshot path to use VapourSynth `fpng` where appropriate because the
legacy repo had meaningful performance benefits there.

This plan is the handoff for a fresh session. It must be treated as an approved
workstream, but functional changes to the plan itself still require maintainer
approval.

## Required Workflow

- Use `frame-compare-cleanup-loop`.
- Keep authoritative live state in `update_plan`.
- Start by requesting adversarial review of this plan before implementation.
- Use subagents for plan validation, implementation units, and review. The main
  session remains the orchestrator and should not directly implement production
  runtime behavior unless resolving integration conflicts is unavoidable.
- Follow `AGENTS.md`, `docs/ENGINEERING_RUNBOOK.md`,
  `docs/current-architecture.md`, `docs/current-cli-contract.md`,
  `importlinter.ini`, and `pyproject.toml`.
- Use relevant boundary skills before editing:
  `runtime-integration-boundaries`, `report-output-patterns`,
  `persistence-boundaries`, `python-quality-boundaries`,
  `python-test-design`, `verification-strategy`, `execution-plan-authoring`,
  `review-request`, `review-adjudication`, and `closeout-verification`.
- Preserve existing user-facing CLI behavior unless explicitly authorized below.
- Preserve the already-landed VSPreview/manual-alignment work:
  base/untrimmed VSPreview sessions, audio offsets as hints only, user-prompted
  matching source-frame positions, final signed offsets computed as
  `reference_source_frame - comparison_source_frame`, and the parity fixes from
  `e799547` and `155a208`.
- Preserve exact source-frame selection semantics for FFmpeg extraction. If FFmpeg
  gains crop/scale/pad filters, frame selection must still target the same exact
  source frame before downstream transforms.

## Risk Tier

High risk.

Reasons:

- Changes touch screenshot rendering and likely `src/frame_compare/render/**`.
- Changes may touch VapourSynth integration in `src/frame_compare/vs/**`.
- Changes add or clarify config behavior under `[screenshots]`.
- Output pixels, overlay placement, report screenshot assets, and runtime plugin
  behavior are externally visible.
- Docker/runtime verification is required by the runbook for render/VS changes.

## Current Repo Facts

Current implementation in `C:\Software\video\frame-compare`:

- VS screenshot path:
  `src/frame_compare/render/encoders.py` `_render_vs()` loads a full VS frame,
  converts it through NumPy/Pillow, applies overlay to the full image, then writes
  PNG through Pillow.
- FFmpeg path:
  `src/frame_compare/render/encoders.py` `_execute_ffmpeg_render()` delegates to
  `src/frame_compare/render/backend/_ffmpeg_frame.py`, whose current extraction
  filter is only `select=eq(n\,frame)`.
- Overlay placement:
  `src/frame_compare/render/overlay.py` uses `_LABEL_POSITION = (10, 10)` and
  draws minimal/diagnostic overlays from that full-frame origin.
- Batch expansion:
  `src/frame_compare/render/batch/expansion.py` builds overlay config from full
  native dimensions and does not carry active-image rectangles, crop plans, scale
  plans, or pad plans.
- Geometry:
  `src/frame_compare/render/geometry.py` currently contains only small dimension
  helpers and is not a full screenshot geometry planner.
- Config:
  `src/frame_compare/config/schema_models.py` `[screenshots]` exposes
  `use_ffmpeg`, output directory, overlay mode, frame number, compression, and
  timeout. There is no current geometry mode or VS writer selection.
- Existing tests that intentionally encode current behavior include:
  `tests/render/test_overlay.py` assertions around `(10, 10)` overlay origins and
  `tests/render/test_ffmpeg_frame.py` asserting the simple select-only FFmpeg
  filter.

## Legacy Repo Reference Points

Use `C:\Software\video\frame-compare-legacy` as the reference repo, not
`origin/cleanup`.

Relevant legacy files and behavior:

- Screenshot orchestration:
  `C:\Software\video\frame-compare-legacy\src\frame_compare\screenshot\orchestrator.py`
  calls `vs_core.process_clip_for_screenshot(...)`, then
  `render.plan_geometry(...)`, then passes crop/scale/pad plans into writer paths.
- Geometry planning:
  `C:\Software\video\frame-compare-legacy\src\frame_compare\screenshot\render.py`
  `plan_geometry()` starts from source dimensions, applies mod crop, optional
  auto-letterbox handling, optional `align_letterbox_pillarbox`, scaling, and
  optional padding.
- Shared geometry helpers:
  `C:\Software\video\frame-compare-legacy\src\frame_compare\render\geometry.py`
  includes:
  - `plan_mod_crop()` for modulus-safe cropping.
  - `align_letterbox_pillarbox()` for same-width/same-height center crops when
    dimensions differ.
  - `plan_letterbox_offsets()` for aspect-ratio-based top/bottom offsets.
- Legacy defaults in
  `C:\Software\video\frame-compare-legacy\config\config.toml` include
  `use_ffmpeg = false`, `mod_crop = 2`,
  `letterbox_pillarbox_aware = true`, `auto_letterbox_crop = "strict"`,
  `pad_to_canvas = "on"`, and `letterbox_px_tolerance = 12`.
- FPNG writer:
  `C:\Software\video\frame-compare-legacy\src\frame_compare\screenshot\render.py`
  `save_frame_with_fpng(...)` uses VapourSynth `core.fpng.Write`, applies crop,
  resize, pad, and optional VS text/subtitle overlay before writing.
- Legacy FFmpeg writer:
  The legacy FFmpeg path applies filters in crop, scale, pad, drawtext order.

Important legacy limitation:

- The legacy implementation has valuable geometry/canvas planning, but it is not a
  complete pixel-inspection black-bar detector. Do not assume the legacy algorithm
  alone is sufficient for all encoded black-bar cases. Use it as a reference and
  improve where the current problem requires active-image awareness.

## Approved Public Behavior Changes

The following public config behavior changes are approved for this workstream:

- Add an optional screenshot geometry mode under `[screenshots]`.
- Keep the default mode backward-compatible unless the implementer can prove that a
  new default has pixel/output parity and no meaningful compatibility risk.
- The recommended public shape is a single high-level option, for example:
  `screenshots.geometry_mode = "native" | "aligned"`.
- `native` means current full-frame behavior: no automatic crop/scale/pad planning
  and legacy `(10, 10)` full-frame overlay anchoring.
- `aligned` means the screenshot renderer computes deterministic per-source geometry
  plans so mixed-resolution, encoded letterbox/pillarbox, odd-modulus, and
  same-height/same-width mismatch cases can be compared on a common active-image
  basis.
- If additional public knobs are necessary, keep them minimal and explicitly justify
  them in the implementation review. Do not add a large legacy compatibility matrix
  by default.
- Preserve current `screenshots.use_ffmpeg` semantics: `true` forces the FFmpeg
  screenshot path, while `false` leaves the renderer in `auto`, which prefers the
  VapourSynth path when available and can fall back to FFmpeg according to the
  existing tonemap/HDR fallback rules. Do not replace this boolean with a breaking
  enum in this workstream.
- Add or clarify VS writer behavior so actual VapourSynth screenshots can use
  `core.fpng.Write` when available and appropriate. If a new config knob is needed,
  use the narrow option `screenshots.vs_writer = "auto" | "pillow" | "fpng"` and
  do not overload `use_ffmpeg`.
- Define `screenshots.vs_writer` behavior as:
  - `auto`: on the actual VapourSynth screenshot path, prefer `fpng` only when the
    plugin is available and the selected geometry/overlay behavior can be preserved;
    otherwise fall back deterministically to the existing Pillow save path. If
    `use_ffmpeg = false` and the renderer falls back to FFmpeg before VS writing,
    this setting does not force a failure.
  - `pillow`: on the actual VapourSynth screenshot path, use the existing
    NumPy/Pillow PNG write path regardless of whether `fpng` is available.
  - `fpng`: require the actual VapourSynth path and `core.fpng.Write`; fail with a
    typed user-visible render/config error if VapourSynth or `fpng` is unavailable,
    or if the selected overlay/geometry mode cannot be preserved without silently
    dropping overlay text or changing the planned output contract.
- Keep `screenshots.png_compression` as the public compression input. The
  implementation must add and test a deterministic Pillow-to-fpng compression
  mapping after checking the current plugin behavior or legacy mapping; unsupported
  values must fail validation or be clamped only if the clamp is documented in
  `docs/current-cli-contract.md`.
- No new CLI flags are required unless implementation discovers a strong product
  reason. If CLI flags are added, stop and request maintainer approval first.

Any change outside these approved surfaces is a stop-and-replan trigger.

## Target Design Constraints

### Geometry

- Keep geometry planning pure and testable, owned by `frame_compare.render` rather
  than orchestration or VS-specific modules.
- Model geometry explicitly: source dimensions, detected/known active image rect,
  crop rect, scale dimensions, pad dimensions, final canvas dimensions, and overlay
  anchor/origin.
- Support at least these aligned-mode cases:
  - same-height clips where one source has left/right bars or different width;
  - same-width clips where one source has top/bottom bars or different height;
  - odd source dimensions that need mod-safe crop behavior;
  - sources whose final comparison should fit a common height or canvas;
  - sources that should be padded rather than stretched after active-image crop.
- Do not stretch active image content to fake alignment. Scale proportionally and
  pad to the chosen canvas when needed.
- Prefer deterministic metadata/dimension geometry where trustworthy. If pixel
  black-bar detection is added, make it conservative, deterministic, and covered by
  synthetic tests. It must fail closed to native/full-frame or legacy-dimension
  behavior rather than cropping real image content aggressively.
- Dolby Vision L5 active-area metadata currently appears only as diagnostic overlay
  text. If the implementation uses it for geometry, document the precedence and add
  tests for malformed, missing, and explicitly zero/unspecified values.

### Overlay Placement

- In `native` mode, preserve existing full-frame overlay origin unless explicitly
  changed and documented.
- In `aligned` mode, overlay text must be anchored to the active image rectangle
  when an active rect is known. Fall back to final planned canvas anchoring only
  when no active rect is known. Canvas-origin anchoring must not be used when it
  would place the label over detected, metadata-described, cropped, or padded bars.
- Overlay anchoring should be represented in render request/config data, not hidden
  inside ad hoc image-size checks in `overlay.py`.
- Keep minimal and diagnostic overlay modes supported.
- Avoid brittle golden-image assertions. Test overlay origin behavior through
  deterministic synthetic inputs and small image probes.

### FPNG

- Treat `fpng` as a VapourSynth plugin capability (`core.fpng.Write`), not a Python
  package dependency.
- The VS screenshot path should prefer `fpng` only when it can preserve required
  behavior for the selected overlay/geometry mode. If full overlay parity cannot be
  maintained with `fpng` in the first implementation unit, keep a documented Pillow
  fallback for those cases and do not silently drop overlays.
- If `fpng` is unavailable, fall back deterministically to the existing Pillow save
  path unless the user explicitly requested a hard failure mode.
- Maintain frame-number correctness: writer implementation must render the exact
  requested source frame after alignment offsets are applied.
- Compression mapping must be deterministic and tested. Do not assume Pillow PNG
  compression and `fpng` compression levels are semantically identical without a
  mapping or explicit documentation.

### FFmpeg

- FFmpeg remains an explicit screenshot backend forced by `screenshots.use_ffmpeg = true`;
  when `use_ffmpeg = false`, existing auto-mode fallback semantics still apply.
- If aligned geometry is supported for FFmpeg, add crop/scale/pad filters after exact
  frame selection and test command construction.
- If aligned geometry is not safely supportable in FFmpeg in the first pass, fail or
  warn clearly when the unsupported combination is selected. Do not silently produce
  native/full-frame screenshots while claiming aligned mode.

## Suggested Implementation Units

The next session may adjust unit boundaries, but functional scope changes require
maintainer approval.

1. Plan validation sidecars.
   - Read-only legacy geometry/fpng validation against
     `C:\Software\video\frame-compare-legacy`.
   - Read-only current repo owner-boundary validation.
   - Adversarial plan review through `frame-compare-cleanup-review`.

2. Config and docs contract.
   - Add minimal `[screenshots]` config fields.
   - Update `config/config.toml` if needed.
   - Update `docs/current-cli-contract.md` for config behavior.
   - Add config/schema tests and CLI contract-doc tests when the contract changes.

3. Pure geometry planner.
   - Implement geometry dataclasses/helpers in `src/frame_compare/render/geometry.py`
     or a focused adjacent module under `render`.
   - Port legacy behavior only where still correct; improve active-image handling
     conservatively.
   - Add focused tests for odd dimensions, same-height pillarbox, same-width
     letterbox, scaling, padding, and overlay anchor calculation.

4. Render request integration.
   - Carry geometry plans through batch expansion and render requests.
   - Use a two-pass expansion design if aligned mode needs cross-clip canvas or
     scale decisions: first collect prepared clip/source dimensions and eligible
     metadata for all batch requests, then compute common geometry plans before
     emitting per-frame `RenderRequest` instances.
   - Integrate with VS/Pillow path and FFmpeg path according to the support decision.
   - Keep orchestration changes minimal and avoid growing hotspot files.

5. Overlay active-origin integration.
   - Make overlay origin/content rect an explicit input to overlay rendering.
   - Preserve native-mode `(10, 10)` tests and add aligned-mode origin tests.

6. VapourSynth fpng writer.
   - Add capability detection and writer selection.
   - Apply crop/resize/pad before write.
   - Preserve overlays through an equivalent VS text/subtitle path or fall back to
     Pillow when parity cannot be preserved.
   - Add tests around writer selection, fallback, and command/runtime branching
     without requiring the real plugin for unit tests.

7. Runtime/manual proof and closeout.
   - Run full verification and Docker/runtime verification.
   - If a real local VSPreview or real `core.fpng` proof cannot be run, record the
     missing runtime proof explicitly in closeout.

## Files In Scope

Likely in scope:

- `src/frame_compare/config/schema_models.py`
- `src/frame_compare/config/schema_enums.py`
- `src/frame_compare/config/defaults.py`
- `config/config.toml`
- `docs/current-cli-contract.md`
- `docs/current-architecture.md` if ownership/runtime flow meaningfully changes
- `src/frame_compare/render/geometry.py` or adjacent render geometry module
- `src/frame_compare/render/types.py` or the current render request DTO owner
- `src/frame_compare/render/batch/expansion.py`
- `src/frame_compare/render/encoders.py`
- `src/frame_compare/render/backend/_ffmpeg_frame.py`
- `src/frame_compare/render/overlay.py`
- nearby tests under `tests/config/`, `tests/cli/`, and `tests/render/`

Potentially in scope only if required:

- `src/frame_compare/vs/*` for fpng capability helpers or VS clip transforms
- `src/frame_compare/orchestration/phase_tasks.py` only if geometry needs metadata
  already owned there; avoid growing this hotspot if a narrower DTO handoff works.

Out of scope unless maintainer approves:

- Changing audio offset estimation policy.
- Changing VSPreview source-frame manual alignment behavior.
- Replacing `screenshots.use_ffmpeg` with a breaking config shape.
- Adding new CLI flags.
- Rewriting HTML report generation.
- Changing slow.pics upload behavior.
- Reworking unrelated render/report parity issues.

## Verification Strategy

Primary modes:

- `contract-first` for new screenshot config behavior and overlay/output semantics.
- `integration-ops` for VapourSynth, FFmpeg, and fpng runtime behavior.
- `manual-runtime` for real media/VSPreview/fpng proof where local runtime is
  required.

Required targeted tests:

- Config schema accepts default/native/aligned settings and rejects invalid values.
- CLI contract docs remain aligned with config/override behavior.
- Pure geometry tests cover same-height pillarbox, same-width letterbox, odd
  dimensions, scale/pad output, active-origin overlay anchor, and conservative
  no-crop fallback.
- Overlay tests preserve native `(10, 10)` behavior and prove aligned-origin
  placement.
- Render request expansion attaches geometry only when aligned mode is enabled.
- FFmpeg command tests preserve exact frame selection and cover any crop/scale/pad
  filter chain if implemented.
- VS writer selection tests cover `fpng` available, `fpng` unavailable fallback,
  overlay parity fallback, and failure/error messaging.

Run during implementation:

```bash
.venv/bin/pytest tests/render -q
.venv/bin/pytest tests/config -q
.venv/bin/pytest tests/cli/test_cli_commands.py tests/test_cli_contract_docs.py -q
```

Required full verification before closeout:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/bandit -c pyproject.toml -r src --severity-level medium
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
bash tools/verify_docker_integration.sh
```

Manual/runtime proof to attempt before closeout:

- Generate screenshots for the maintainer's black-bar/pillarbox test case with
  `screenshots.geometry_mode = "aligned"`.
- Confirm active images align without relying on viewer fit-height.
- Confirm overlay text is anchored on the active image when an active rect is known,
  and never on black bars or padding.
- Confirm `fpng` is used when the VapourSynth plugin is available and eligible.
- Confirm fallback behavior when `fpng` is unavailable.
- Record any missing real VSPreview, real media, Docker, or `core.fpng` proof
  explicitly.

## Stop-And-Replan Triggers

Stop and ask the maintainer before implementation continues if:

- The desired public config shape needs more than the approved minimal geometry
  mode and optional VS writer setting.
- Correct behavior requires changing default screenshot geometry or overlay
  placement in native mode.
- Supporting aligned geometry requires changing audio alignment, VSPreview session
  generation, or offset math.
- FFmpeg exact source-frame selection would be weakened or made ambiguous.
- `fpng` cannot preserve overlays and the only available path would silently drop
  overlay text.
- Pixel black-bar detection would need aggressive thresholds that risk cropping
  real image content.
- Import-layer changes require modifying `importlinter.ini`.
- The legacy repo behavior conflicts with current public CLI/config contracts.
- Required Docker/runtime verification cannot run and no acceptable documented-only
  proof path is available.

## Review Expectations

Before implementation:

- Reviewer must lead with findings ordered by severity and explicitly say whether
  this plan is implementation-grade.
- Reviewer must check that this is not an unbounded feature umbrella, that public
  config changes are approved and narrow, and that the verification surface covers
  render/VS/FFmpeg output risk.

After each implementation unit:

- Review for behavioral regressions, CLI/config contract drift, render output
  drift, import-layer violations, filesystem ownership leaks, runtime fallback
  failures, missing tests, and unrelated changes.
- Use `review-adjudication` for all findings before continuing.
