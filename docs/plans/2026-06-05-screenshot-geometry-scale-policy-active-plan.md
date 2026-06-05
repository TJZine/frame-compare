Status: Active
Scope: Add explicit aligned screenshot scale policy and conservative aspect-ratio active-rect detection so mixed FHD/UHD scope sources align without unintended oversized canvases.
Owner: Codex planning session on 2026-06-05; implementation owner TBD.

# Screenshot Geometry Scale Policy And Active-Rect Detection Plan

## Goal

Implement both approved directions:

1. Split aligned screenshot geometry into separate active-area detection and output scale policy decisions.
2. Add conservative automatic active-rect detection for mixed-resolution letterboxed scope sources, using legacy behavior as reference but keeping the current repo's smaller owner boundaries.

The concrete regression to prevent is the Fight Club case with two `1920x800` clips and one `3840x2160` clip producing `5184x2160` screenshots under `screenshots.geometry_mode = "aligned"`. The intended aligned behavior is not height-only scaling. It must be possible to:

- upscale active content to the largest active source, such as `1920x800` to `3840x1600`;
- downscale active content to the smallest active source, such as `3840x1600` to `1920x800`;
- match the selected reference source active size;
- optionally fit active content inside an exact configured target canvas.

## Non-Goals

- Do not change VSPreview source registration, source dropdown behavior, manual offset prompts, or audio alignment in this workstream.
- Do not add CLI flags. The new behavior is config-only under `[screenshots]`.
- Do not change `geometry_mode = "native"` output behavior.
- Do not change screenshot filenames, report upload membership, slow.pics behavior, JSON output, or report viewer logic.
- Do not add pixel-scanning black-bar detection in the first implementation pass.
- Do not change VapourSynth tonemap, color conversion, or writer-selection semantics except where geometry plans already flow into render writers.
- Do not update `importlinter.ini` unless implementation discovers an unavoidable architecture decision and maintainer approves it first.

## Risk Classification

Risk tier: High.

Reasons:

- Public config behavior changes under `[screenshots]`.
- Screenshot pixel dimensions and generated report assets are user-visible output.
- Changes touch `src/frame_compare/render/**`, a runtime surface requiring full verification and Docker/runtime verification by the runbook.
- FFmpeg and VapourSynth paths both consume `RenderGeometryPlan`; both must preserve exact source-frame selection before crop/scale/pad.

## Public Config Contract

Add these config-only public fields to `[screenshots]`:

```toml
[screenshots]
geometry_mode = "native" # existing: native | aligned
active_rect_detection = "aspect_ratio" # provided | dimension | aspect_ratio
aligned_scale_policy = "largest_active" # largest_active | smallest_active | reference_active | explicit_size
# aligned_target_width = 3840
# aligned_target_height = 2160
```

Contract details:

- `geometry_mode = "native"` ignores the new aligned-only fields and preserves existing native full-frame screenshot behavior.
- Schema validation still parses enum values and validates target field types for all configs. However, aligned-only cross-field validation is gated on `geometry_mode = "aligned"` so native-mode configs may carry inert aligned settings without changing native output.
- If `aligned_target_width` or `aligned_target_height` is present in any config, the provided value must still be a positive even integer. The requirement that both target values are present for `explicit_size`, and omitted for non-`explicit_size` policies, applies only when `geometry_mode = "aligned"`.
- `active_rect_detection = "provided"` uses only active rectangles that are already provided by explicit per-source `active_rect` overrides or trusted metadata. It disables derived dimension and aspect-ratio inference.
- `active_rect_detection = "dimension"` keeps the current same-height/same-width center-crop inference only.
- `active_rect_detection = "aspect_ratio"` runs explicit/metadata handling first, then existing dimension inference, then conservative aspect-ratio letterbox inference.
- `aligned_scale_policy = "largest_active"` fits every active image inside the active-source envelope `{max(active_width), max(active_height)}`. This is the default and is the intended upscale policy. It is not selected by pixel area.
- `aligned_scale_policy = "smallest_active"` fits every active image inside the active-source envelope `{min(active_width), min(active_height)}`. This is the downscale policy for users who want normalized lower-resolution comparison output. It is not selected by pixel area.
- `aligned_scale_policy = "reference_active"` fits every active image inside the reference source active dimensions.
- `aligned_scale_policy = "explicit_size"` fits every active image inside `aligned_target_width x aligned_target_height`. In aligned mode, both target values are required and must be positive even integers when this policy is selected. In aligned mode, both target values must be omitted for all other policies.
- Fitting must preserve aspect ratio and must never scale an active image beyond the selected target width or selected target height. This is the main guard against another `5184x2160` style output.
- Final canvas size is the normalized target dimensions for derived policies and the exact configured target dimensions for `explicit_size`. Each scaled active image is centered with black padding when needed.

Authority docs to update in the implementation pass:

- `docs/current-cli-contract.md`: update Config-Only Screenshot Surface.
- `docs/current-architecture.md`: update the screenshot geometry owner summary so it describes active-rect detection and fit-to-target scale/canvas planning instead of the old shared-height policy.

Default rationale:

- `native` remains the global default through `geometry_mode`.
- For users who opt into `aligned`, `largest_active` plus `aspect_ratio` is the safer default because it matches the currently intended "align to the largest encode/source" behavior without height-only overflow.

## Owner Seam

Primary owner: `frame_compare.render`.

Target files:

- `src/frame_compare/config/schema_enums.py`
  - Add enums for active-rect detection and aligned scale policy.
- `src/frame_compare/config/schema_models.py`
  - Add fields and validation to `ScreenshotsConfig`; target fields should default to `None` in Python but be omitted or commented in TOML examples because TOML has no `null` literal.
- `src/frame_compare/config/defaults.py`
  - Update `DEFAULT_CONFIG_TOML` in the same pass as `config/config.toml` so wizard/default-template behavior cannot drift.
- `config/config.toml`
  - Add documented default values for enum fields and commented numeric examples for explicit target fields.
- `src/frame_compare/render/geometry.py`
  - Own active-rect fallback resolution and scale/canvas planning.
  - Consume already-resolved provided rectangles and their `active_rect_source` provenance from `SourceGeometry`; do not parse diagnostic metadata, source overrides, or warning policy here.
  - Prefer adding a small options dataclass rather than adding many positional arguments.
- `src/frame_compare/render/batch/expansion.py`
  - Convert screenshot config into geometry planning options and keep batch-level planning as the place where cross-source geometry is computed.
  - Remain the sole owner for converting per-frame trusted diagnostic metadata into `SourceGeometry.active_rect` plus any rejection warnings.
- `src/frame_compare/render/backend/_ffmpeg_frame.py`
  - Should not need policy changes, but existing tests must prove generated filter order remains `select`, then crop, scale, pad.
- `src/frame_compare/render/encoders.py`
  - Should not need policy changes, but existing VS Pillow/fpng geometry tests must prove crop/resize/pad still applies correctly.
- Tests under `tests/config/`, `tests/render/`, and `tests/test_cli_contract_docs.py`.

Files out of scope by default:

- `src/frame_compare/vspreview/**`
- `src/frame_compare/services/alignment*.py`
- `src/frame_compare/orchestration/phase_tasks.py`, unless the implementation discovers a missing handoff of already-available metadata that cannot be solved inside render DTOs.
- `src/frame_compare/services/report/**`, unless screenshot dimension metadata in reports is proven stale or misleading after render changes.
- CLI command files and `src/frame_compare/config/overrides.py`, because no new CLI flags are planned.

## Behavior Design

### Active Rect Precedence

For each source in aligned mode, resolve active rect in this order:

1. Explicit `[sources.overrides."<selector>"].active_rect`, already validated during preparation.
2. Trusted metadata active rect when current render DTOs mark metadata as trusted for geometry.
3. Dimension-derived same-axis inference when `active_rect_detection` is `dimension` or `aspect_ratio`.
4. Aspect-ratio-derived letterbox inference when `active_rect_detection` is `aspect_ratio`.
5. Full frame.

Explicit active rects must remain highest priority and invalid explicit rects must fail during preparation, not silently fall back.

Ownership boundary:

- `render.batch.expansion` must convert explicit overrides and trusted diagnostic metadata into provided `SourceGeometry.active_rect` values before calling `render.geometry`.
- `render.batch.expansion` must preserve provenance on `SourceGeometry.active_rect_source` (`explicit` versus `metadata`) so `render.geometry` can apply deterministic evidence tie breaks without reading raw metadata.
- `render.batch.expansion` must also keep ownership of warnings for rejected or missing trusted metadata.
- `render.geometry` must not inspect raw diagnostics or source override config. It only consumes dimensions, already-provided active rects, active-rect provenance, and geometry options, then performs dimension-derived, aspect-ratio-derived, or full-frame fallback.

### Conservative Aspect-Ratio Inference

Use this only when `active_rect_detection = "aspect_ratio"`.

The implementation should infer vertical letterbox crops for sources whose full-frame aspect ratio is materially narrower than a strongly evidenced target content aspect ratio.

Use named constants in `render.geometry` with these initial values unless implementation tests reveal a documented reason to stop and replan:

- `ASPECT_RATIO_MATCH_REL_TOLERANCE = 0.005`
- `ASPECT_RATIO_MIN_CROP_REL_DELTA = 0.005`
- `ASPECT_RATIO_MAX_HEIGHT_REMOVAL_FRACTION = 0.35`

Compare two aspect ratios with relative delta:

```text
relative_delta = abs(candidate_ratio - observed_ratio) / max(candidate_ratio, observed_ratio)
matches = relative_delta <= ASPECT_RATIO_MATCH_REL_TOLERANCE
```

Treat a full-frame source as materially narrower than the target only when:

```text
(target_ratio - full_frame_ratio) / target_ratio > ASPECT_RATIO_MIN_CROP_REL_DELTA
```

Target aspect evidence must be conservative. A candidate target aspect ratio may be used only when at least one of these is true:

- at least two sources have already-resolved active/full-frame ratios that match the candidate ratio within `ASPECT_RATIO_MATCH_REL_TOLERANCE`;
- one source has an explicit or trusted-metadata active rect establishing the candidate ratio.

Candidate selection must be deterministic:

1. Build candidate ratios from explicit/provided active rects first, then trusted-metadata active rects, then ratios shared by at least two already-resolved full-frame or dimension-derived rects.
2. Merge candidates whose relative delta is within `ASPECT_RATIO_MATCH_REL_TOLERANCE`; use the first candidate in source order as the representative ratio for that cluster.
3. Rank candidates by support count across sources.
4. Break support-count ties by evidence class: explicit/provided active rect evidence, then trusted metadata evidence, then dimension-derived/full-frame evidence.
5. Break remaining ties by preferring the candidate closest to the reference source's already-resolved active/full-frame ratio.
6. Break final ties by source order, not by set/hash/dictionary iteration.

A single ultrawide source must not force-crop every other source by itself.

For the concrete regression:

```text
1920x800 ratio = 2.40
1920x800 ratio = 2.40
3840x2160 ratio = 1.777...
target content ratio = 2.40
3840 / 2.40 = 1600
crop UHD to active rect x=0, y=280, width=3840, height=1600
```

Required guardrails:

- Only apply centered vertical crops. Do not implement mixed horizontal/pillarbox aspect inference in this pass unless tests and docs prove it. Existing same-height/same-width dimension inference already covers the common pillarbox case.
- Do not infer a crop when fewer than two sources are present.
- Do not infer a crop when the target aspect ratio is supported only by one full-frame source and no explicit/trusted metadata active rect.
- Do not infer a crop when the target aspect ratio difference does not exceed `ASPECT_RATIO_MIN_CROP_REL_DELTA`.
- Compute vertical crop height as `floor(source_width / target_ratio)`, then reduce to the existing geometry mod-safe value without exceeding the computed height.
- Do not infer a crop when computed active height is non-positive or when `(source_height - crop_height) / source_height > ASPECT_RATIO_MAX_HEIGHT_REMOVAL_FRACTION`.
- Crop dimensions and crop offsets must be mod-safe using the existing geometry mod logic. Center the crop after height reduction, adjust the `y` offset only as needed to satisfy mod-safety, and preserve containment inside the source frame.
- If the heuristic cannot prove a conservative crop, fall back to the previously resolved rect and let scale policy fit/pad the image.
- Do not read or decode pixels for this heuristic.

### Scale And Canvas Policy

Replace current height-only common scaling with fit-to-target scaling.

For each active rect, after policy target selection and target canvas normalization:

```text
scale = min(target_width / active_width, target_height / active_height)
scaled_width = floor(active_width * scale)
scaled_height = floor(active_height * scale)
```

Here `target_width` and `target_height` mean the normalized target for derived policies and the exact configured target for `explicit_size`. Then clamp both scaled dimensions to that target, reduce dimensions to mod-safe values without exceeding the target, and center-pad to the target canvas. Do not round up scaled dimensions if doing so would exceed the target canvas.

Policy target selection:

- `largest_active`: use `{max(active_width), max(active_height)}` across resolved active rects.
- `smallest_active`: use `{min(active_width), min(active_height)}` across resolved active rects.
- `reference_active`: choose source index 0's active rect.
- `explicit_size`: use configured `aligned_target_width` and `aligned_target_height`. Reject odd target dimensions during config validation so the exact configured canvas promise does not conflict with mod-safety.

Target canvas normalization:

- After selecting a target for `largest_active`, `smallest_active`, or `reference_active`, normalize the target canvas by reducing width and height independently to the existing geometry mod-safe values without exceeding the selected target.
- Do not increase a derived target canvas to satisfy mod-safety.
- If target normalization would make width or height non-positive, skip aligned planning through the existing warning/fallback path rather than producing invalid geometry.
- `explicit_size` targets are not normalized after validation; config validation rejects odd or non-positive values so the exact configured canvas is preserved.
- The final canvas size is the normalized target for derived policies and the exact configured target for `explicit_size`.

For the Fight Club regression with default aligned settings:

```text
active rects:
  FHD A: 1920x800
  FHD B: 1920x800
  UHD:   3840x1600
target: largest_active = 3840x1600
final canvas for all clips: 3840x1600
```

If aspect-ratio inference is disabled but `largest_active` is still used, the target is `3840x2160`; the two FHD clips must fit inside that target as `3840x1600` with vertical padding, not `5184x2160`.

## Implementation Units

### Unit 1: Config Contract

1. Add enum types:
   - `ScreenshotActiveRectDetection`
   - `ScreenshotAlignedScalePolicy`
2. Add fields to `ScreenshotsConfig`.
3. Validate `explicit_size` target values:
   - provided target values are always required to be positive even integers;
   - when `geometry_mode = "aligned"` and `aligned_scale_policy = "explicit_size"`, both target values are required;
   - when `geometry_mode = "aligned"` and the scale policy is not `explicit_size`, both target values must be omitted/`None`;
   - when `geometry_mode = "native"`, target fields are inert for behavior and only structural validation applies.
4. Update both `config/config.toml` and `src/frame_compare/config/defaults.py` comments and defaults in the same pass, using commented numeric examples rather than TOML `null`.
5. Update CLI contract docs and config schema/default-loader tests.

Expected tests:

- Defaults parse.
- Each enum value parses.
- invalid enum values fail.
- `explicit_size` with missing width or height fails.
- aligned non-explicit policy with target width/height fails.
- native mode with inert aligned policy settings and no explicit-size target pair still parses and preserves native geometry behavior.
- native mode with an odd target value still fails structural validation.
- odd explicit target dimensions fail.
- project default config TOML remains parseable.
- `DEFAULT_CONFIG_TOML` includes the new screenshot defaults and still loads through the default-config loader path.

### Unit 2: Geometry Planner Options

1. Add a geometry options dataclass in `render.geometry`.
2. Update `plan_render_geometry` to accept options while preserving simple existing call behavior for tests.
3. Keep `native` mode behavior byte-for-byte equivalent in tests where possible.
4. Preserve existing dimension-derived tests.
5. Add focused tests for scale policies.

Expected tests:

- Current native tests unchanged.
- Current same-height and same-width aligned tests still pass or are updated only where target canvas policy intentionally changes.
- `largest_active` with `1920x800`, `1920x800`, `3840x2160` produces no dimension above `3840x2160` even before aspect-ratio crop.
- `largest_active` plus aspect-ratio crop produces `3840x1600`.
- `smallest_active` plus aspect-ratio crop produces `1920x800`.
- `reference_active` matches source index 0 active dimensions.
- `explicit_size = 3840x2160` fits `1920x800` as `3840x1600` with vertical padding.
- odd active/source dimensions are floored or clamped without exceeding the selected target.
- odd derived target dimensions are reduced to mod-safe canvas dimensions for `largest_active`.
- odd derived target dimensions are reduced to mod-safe canvas dimensions for `smallest_active`.
- odd derived target dimensions are reduced to mod-safe canvas dimensions for `reference_active`.
- mixed-aspect sources where max-width and max-height come from different sources still use the documented envelope policy.

### Unit 3: Conservative Aspect-Ratio Detection

1. Implement aspect-ratio-derived vertical active rects after explicit/metadata/dimension inference.
2. Keep constants named and local to geometry.
3. Preserve deterministic source order.
4. Add tests for malformed/edge cases.

Expected tests:

- Fight Club shape derives UHD active rect `GeometryRect(0, 280, 3840, 1600)`.
- No crop when all sources have effectively the same aspect ratio.
- No crop with one source.
- No crop when one ultrawide outlier is the only source supporting the candidate target ratio.
- Crop is allowed when one explicit or trusted metadata active rect establishes the target ratio.
- When two different supported candidate ratios compete, selection follows support count, evidence class, reference-ratio closeness, then source-order tie breaks.
- No crop when candidate crop would remove too much height.
- Boundary tests for `ASPECT_RATIO_MATCH_REL_TOLERANCE`, `ASPECT_RATIO_MIN_CROP_REL_DELTA`, and `ASPECT_RATIO_MAX_HEIGHT_REMOVAL_FRACTION`.
- Mod-safe crop-height and centered-offset tests prove the crop remains inside the source frame after reducing dimensions.
- Existing explicit active rect beats aspect-ratio inference.
- Existing trusted metadata active rect beats aspect-ratio inference.

### Unit 4: Batch Expansion Integration

1. Map `ConfigSchema.screenshots` fields to geometry options in `render.batch.expansion`.
2. Convert explicit overrides and trusted diagnostic metadata into `SourceGeometry.active_rect` before calling `render.geometry`; do not move metadata parsing into `render.geometry`.
3. Ensure warnings remain deterministic and attached to the existing render warnings list if trusted metadata is rejected or the planner skips alignment due to missing dimensions.
4. Do not add runtime imports to CLI or orchestration.
5. Keep `ScreenshotBatchRequest` shape unchanged unless absolutely necessary.

Expected tests:

- `expand_batch_render_requests` attaches geometry plans using the configured scale policy.
- trusted metadata active rects are converted in batch expansion and consumed as provided rects by geometry.
- rejected trusted metadata warnings stay in the existing render warnings surface.
- Overlay `resolution` and `resolution_summary` reflect the new final canvas.
- FFmpeg render requests still receive one geometry plan per source reused across frames.
- Existing missing-dimensions fallback still warns and uses native geometry.

### Unit 5: Writer Path Guard Tests

1. Keep FFmpeg filter order proof.
2. Keep VS Pillow geometry proof.
3. Keep fpng geometry proof where existing tests cover it.
4. Add or update only narrow assertions around dimensions, filter order, and crop/scale/pad values.

Expected tests:

- FFmpeg argv remains `select`, `crop`, `scale`, `pad`.
- Exact source frame selection stays before geometry filters.
- VS Pillow path crops/resizes/pads to final canvas.
- fpng path receives geometry-transformed clip when eligible.

### Unit 6: Docs And Closeout

1. Update `docs/current-cli-contract.md` in the same pass as config changes.
2. Update `docs/current-architecture.md` with the new active-rect detection and fit-to-target scale/canvas behavior in the screenshot rendering owner summary.
3. Keep this plan Active until implementation and verification complete.
4. When complete, mark this plan Historical and record verification results and any runtime proof gaps.

## Verification Strategy

Primary verification modes:

- `contract-first` for public screenshot config behavior and generated screenshot dimensions.
- `integration-ops` for FFmpeg/VapourSynth render paths.
- `manual-runtime` for real-media proof of the Fight Club shape.

Proof classification:

| Surface | Classification | Required proof |
| --- | --- | --- |
| New screenshot config fields | new regression/contract test required | config schema tests and CLI contract-doc test |
| Pure geometry target selection | new regression/contract test required | focused `tests/render/test_geometry.py` cases |
| Aspect-ratio active-rect detection | new regression/contract test required | focused conservative positive and negative cases |
| Batch expansion handoff | new regression/contract test required | `tests/render/test_expansion.py` |
| FFmpeg command construction | existing coverage sufficient plus targeted updates | `tests/render/test_ffmpeg_frame.py` |
| VS Pillow/fpng geometry | existing coverage sufficient plus targeted updates | `tests/render/test_encoders.py` |
| Real mixed FHD/UHD media output | broader integration/manual proof required | generate screenshots for current Fight Club inputs and inspect output dimensions |
| CLI flags and JSON stdout | no new automated test needed | no CLI flags or JSON schema changes planned |

Focused commands during implementation:

```bash
.venv/bin/pytest -q tests/config/test_schema.py tests/test_cli_contract_docs.py
.venv/bin/pytest -q tests/render/test_geometry.py tests/render/test_expansion.py tests/render/test_ffmpeg_frame.py tests/render/test_encoders.py
```

Static checks after code changes:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
```

Full verification before closeout:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/bandit -c pyproject.toml -r src --severity-level medium
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
bash tools/verify_docker_integration.sh
```

Manual runtime proof:

1. Use the current Fight Club inputs or equivalent synthetic media with two `1920x800` sources and one `3840x2160` source.
2. Run with `screenshots.geometry_mode = "aligned"`, `active_rect_detection = "aspect_ratio"`, and `aligned_scale_policy = "largest_active"`.
3. Confirm generated screenshots are `3840x1600` for all three clips.
4. Run with `aligned_scale_policy = "smallest_active"` and confirm generated screenshots are `1920x800` for all three clips.
5. Run with `aligned_scale_policy = "explicit_size"`, `aligned_target_width = 3840`, `aligned_target_height = 2160`, and confirm active content fits inside an exact `3840x2160` canvas without exceeding it.
6. If local VapourSynth, FFmpeg, Docker, or real media proof cannot run, record the exact missing proof and do not claim full runtime verification.

## Invariants

- `geometry_mode = "native"` remains unchanged.
- Explicit per-source active rect config remains highest precedence.
- Invalid explicit active rect config still fails during preparation.
- Source-frame selection remains exact and happens before crop/scale/pad.
- Scaling preserves aspect ratio.
- No aligned output may exceed the selected target canvas dimensions.
- Render output naming and ordering remain deterministic.
- No new CLI flags or JSON keys are added.
- No runtime policy is moved into CLI or orchestration.
- Missing dimensions still degrade with the existing warning path rather than failing unexpectedly.

## Stop And Replan Triggers

Stop and ask the maintainer before implementation continues if:

- Correct behavior appears to require pixel-based black-bar detection.
- Correct behavior requires changing default `geometry_mode` away from `native`.
- Correct behavior requires adding CLI flags.
- Correct behavior requires changing VSPreview, alignment, source ordering, or manual override semantics.
- Active-rect detection cannot be made conservative without cropping likely real image content.
- The proposed config shape needs more fields than listed in this plan.
- FFmpeg or VapourSynth geometry cannot preserve exact source-frame selection before transforms.
- The implementation needs import-layer changes.
- Docker/runtime verification cannot run and there is no acceptable documented-only proof path for the touched runtime surface.

## Rollback Surface

Rollback should remove only:

- new screenshot config enum fields and validation;
- geometry planner option changes;
- aspect-ratio active-rect inference;
- batch expansion handoff changes;
- focused tests and docs updates from this workstream.

Do not roll back unrelated report, slow.pics, alignment, VSPreview, or cache changes.
