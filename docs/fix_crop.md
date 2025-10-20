Task: Enable pixel-perfect odd-pixel crop/pad on subsampled SDR by pivoting geometry to full-chroma 16-bit only when needed

Context
- Current failure: Odd 1 px trims/pads on 4:2:0 SDR fail because geometry happens pre-RGB, and VapourSynth enforces mod-2 in subsampled formats.
- Goal: Allow 1 px symmetric crop/pad without scaling or distortion, while preserving quality and determinism.
- Approach: When odd geometry is requested on a subsampled SDR source, temporarily promote to YUV444P16, perform geometry, then convert to RGB24 with dithering. HDR path remains unchanged.
- SDR-only pivot: The 4:4:4/16 promotion applies only to SDR paths. HDR pipeline and tonemapping remain unchanged.

Constraints and guardrails
- Keep the diff-plan → approval → patches workflow.
- Strict typing (Pyright standard/strict).
- Tests must be added/updated for any code changes.
- Structure/CI edits must be proposed separately and are out-of-scope for this task.
- Pass color metadata explicitly through zimg (matrix_in, transfer_in, primaries_in, range_in) at each conversion; do not read frame 0 to sniff props.
- Color properties source: Use clip's inherent props (clip.format, clip.get_frame(0).props only if already loaded), with fallback to sensible defaults (BT.709 for HD, BT.601 for SD based on resolution).
- zimg integer enums: matrix=1 (BT.709), 5 (BT.470BG/601), 9 (BT.2020); transfer=1 (BT.709), 16 (SMPTE2084/PQ); primaries=1 (BT.709), 9 (BT.2020); range=0 (full), 1 (limited)
- Determinism: apply dithering only on the final 16→8 RGB24 hop; the 8→16 or same-bit-depth hops must use no dithering.
- Handle mixed bit-depths gracefully (8/10/12/16-bit sources should all promote to 16-bit for geometry)

Deliverables
- Code changes with minimal blast radius.
- New config options:
  - [screenshots].odd_geometry_policy = "auto" | "force_full_chroma" | "subsamp_safe" (default "auto")
  - [screenshots].rgb_dither = "error_diffusion" | "ordered" | "none" (default "error_diffusion")
- Logging that clearly indicates when the 444/16 pivot is applied.
- Unit and integration tests covering the failing scenario and edge cases.
- Axis-aware promotion: in auto policy, promote only if there’s an odd operation on an axis that is subsampled (vertical odd + subsampling_h>0; horizontal odd + subsampling_w>0).
- Color props passthrough: conversions must set zimg *_in args (and output props if needed) rather than peeking a frame.
- Dithering scope: rgb_dither applies only to final RGB24 down-quantization; intermediate up-quantization uses dither_type="none".
- Logging (INFO): “Odd-geometry on subsampled SDR → promoting to YUV444P16 (policy={…}, axis={vertical|horizontal}, fmt={…})”. (DEBUG: include source/dest formats and chosen dithering.)
- Documentation updates to config reference and geometry pipeline notes.

Definition of Done
- The 1920×1036 vs 1920×1038 scenario no longer errors with mod 2 complaints.
- Symmetric 1 px adjustments are preserved (1 px top + 1 px bottom), no scaling.
- Outputs are byte-identical to current behavior when only even-aligned geometry is involved.
- HDR pipeline behavior unchanged.
- Pyright passes; tests pass locally and in CI without structure changes.
- Determinism maintained (dithering is deterministic).
- Conditional pivot is axis-aware (no unnecessary promotion when, e.g., vertical-odd on 4:2:2).
- Dithering occurs only on final RGB24 conversion; outputs remain deterministic across runs.

Proposed patch plan (sequence of small, reviewable commits)

Patch 1: Config schema and types
- Add enums and fields to the screenshots config:
  - odd_geometry_policy: Literal["auto","force_full_chroma","subsamp_safe"] or Enum
  - rgb_dither: Literal["error_diffusion","ordered","none"] or Enum
- Defaults:
  - odd_geometry_policy="auto"
  - rgb_dither="error_diffusion"
- Update AppConfig/ScreenshotConfig dataclasses and TOML parsing.
- Update docs/config_reference tables.

Sketch:
- screenshots/typing.py (or wherever types live)
  - Define OddGeometryPolicy(Enum) and RGBDither(Enum)
- app_config.py
  - class ScreenshotConfig: add fields, defaults, validation
- docs/config_reference.md
  - Add the two new fields and descriptions

Patch 2: Planner signals when full-chroma is required
- In geometry planning (plan_mod_crop + letterbox_pillarbox_aware + _plan_geometry), compute requires_full_chroma if:
  - policy == "force_full_chroma" → always true for SDR
  - policy == "subsamp_safe" → always false
  - policy == "auto" → true only if subsampling exists in an axis where an odd crop/pad is requested on that axis
    - vertical_odd = any(x % 2 for x in (crop_top, crop_bottom, pad_top, pad_bottom))
    - horizontal_odd = any(x % 2 for x in (crop_left, crop_right, pad_left, pad_right))
    - requires_full_chroma = (policy=="force_full_chroma") or (policy=="auto" and ((vertical_odd and fmt.subsampling_h>0) or (horizontal_odd and fmt.subsampling_w>0)))
    - If policy=="subsamp_safe" and odd ops exist, do not promote; instead, rebalance to even geometry and log a warning.
- Store requires_full_chroma bool in the geometry plan object.
- If subsamp_safe forces rebalancing: log.warning(f"Rebalanced {orig_top}/{orig_bottom} to {new_top}/{new_bottom} for mod-2 safety; content may shift by 1px")

Helper function:
- compute_requires_full_chroma(fmt, crop_top, crop_bottom, pad_top, pad_bottom, crop_left, crop_right, pad_left, pad_right, policy) -> bool

Patch 3: Renderer 444/16 pivot for SDR only
- SDR gate: only pivot when plan.requires_full_chroma and the clip is SDR.
- In _save_frame_with_fpng (VapourSynth path):
  - If plan.requires_full_chroma and source is SDR, before any crop/scale/pad:
    - Convert to YUV444P16 using zimg (core.resize.*)
    - Preserve color props (matrix/primaries/transfer/range); pass them explicitly if props may be missing
  - Perform geometry as today
  - No frame peeking: obtain color info from existing clip props/config and pass explicitly; avoid clip.get_frame(0).
  - Convert to RGB24 at the end with dithering based on screenshots.rgb_dither
  - zimg args: use matrix_in, transfer_in, primaries_in, range_in (not *_in_s).
  - Dithering: up-promotion to 16-bit uses dither_type="none". Apply configured rgb_dither only on final RGB24 conversion.
- HDR clips remain on existing RGB48/tonemap path; do not add redundant conversions.
- Fast-path detection: Skip promotion if clip.format.subsampling_w == 0 and clip.format.subsampling_h == 0 (already 4:4:4/RGB)
- Logging: INFO message as in Deliverables; DEBUG includes src/dst formats and dither choice.

Notes:
- Use core.resize.Point for no-op resampling if that’s the current policy, but ensure the dither_type argument is honored on the final RGB24 hop (zimg supports dither_type on all resize kernels; pick the kernel consistent with current behavior).
- No dithering required when promoting to 16-bit; only when reducing to 8-bit (RGB24).
- create_test_clip helper can use core.std.BlankClip(format=format, width=width, height=height, length=1, color=[128, 128, 128])

Sketch:
def maybe_promote_to_444p16(clip: vs.VideoNode, props: ColorProps) -> vs.VideoNode:
    return core.resize.Bicubic(
        clip,
        format=vs.YUV444P16,
        matrix_in=props.matrix,
        transfer_in=props.transfer,
        primaries_in=props.primaries,
        range_in=props.range,
    )

def to_rgb24(clip: vs.VideoNode, props: ColorProps, dither: RGBDither) -> vs.VideoNode:
    dither_type = {
        RGBDither.ERROR_DIFFUSION: "error_diffusion",
        RGBDither.ORDERED: "ordered",
        RGBDither.NONE: "none",
    }[dither]
    return core.resize.Point(
        clip,
        format=vs.RGB24,
        matrix_in=props.matrix,
        transfer_in=props.transfer,
        primaries_in=props.primaries,
        range_in=props.range,
        dither_type=dither_type,
    )
    
def get_color_props(clip: vs.VideoNode) -> ColorProps:
    """Extract color properties with sensible defaults."""
    # SD/HD heuristic for defaults
    is_hd = clip.width >= 1280 or clip.height >= 720
    return ColorProps(
        matrix=getattr(clip.format, 'matrix', 1 if is_hd else 5),
        transfer=getattr(clip.format, 'transfer', 1),
        primaries=getattr(clip.format, 'primaries', 1),
        range=getattr(clip.format, 'range', 0)
    )

- Ensure props are kept in sync on the resulting nodes.

Patch 4: FFmpeg fallback parity (optional but recommended)
- When screenshots.use_ffmpeg = true and requires_full_chroma is true:
  - Insert format=yuv444p16 before crop/scale/pad, then format=rgb24 at the end of the graph.
  - Keep filters otherwise identical.
- If FFmpeg lacks a deterministic error-diffusion control for rgb24, prefer ordered or none for parity; document the limitation in the config docs

Example filter graph stitching:
- pre = "format=yuv444p16"
- post = "format=rgb24"
- graph = [pre, crop/pad/scale filters..., post] joined by commas

Patch 5: Tests (planner + renderer)
- Unit tests (fast, no VS required if planner is isolated)
  - Requires_full_chroma logic
    - 4:2:0 + odd vertical → True (auto)
    - 4:2:2 + odd vertical → False (auto)
    - 4:2:2 + odd horizontal → True (auto)
    - Even-only ops → False
    - force_full_chroma → True
    - subsamp_safe → False
- Integration tests (VapourSynth)
  - Create two synthetic 4:2:0 SDR clips (e.g., BlankClip) at 1920×1036 and 1920×1038, same content
  - Plan a 1 px symmetric pad/crop to align without scaling
  - Assert: no exceptions, final dimensions match, applied top/bottom = 1/1
  - Assert: when geometry is even-only, outputs are byte-identical to baseline (no pivot)
  - Optional: 4:2:2 clip with only vertical odd ops does not pivot (and does not error)
- Optional FFmpeg test if available in CI:
  - Ensure graph contains format=yuv444p16 and format=rgb24 when odd ops present
Example Tests:

def test_odd_pixel_padding_420_clips():
    """Test 1px padding on 4:2:0 clips succeeds with full-chroma conversion."""
    # Create two synthetic 4:2:0 YUV420P8 clips
    clip1 = create_test_clip(1920, 1036, format=vs.YUV420P8)
    clip2 = create_test_clip(1920, 1038, format=vs.YUV420P8)
    
    # Configure for odd geometry
    config = ScreenshotConfig(
        mod_crop=2,
        letterbox_pillarbox_aware=True,
        odd_geometry_policy="auto"
    )
    
    # Plan geometry - should require 1px adjustments
    plans = plan_geometry([clip1, clip2], config)
    
    # Assert requires_full_chroma flag is set
    assert plans[0].requires_full_chroma == True
    
    # Execute rendering - should not raise mod 2 errors
    frames = render_frames(clips, plans, config)
    
    # Verify dimensions match
    assert all(f.height == 1037 for f in frames)  # Or whatever the target is

def test_even_operations_skip_conversion():
    """Test that even-only operations stay on fast path."""
    clip1 = create_test_clip(1920, 1036, format=vs.YUV420P8)
    clip2 = create_test_clip(1920, 1040, format=vs.YUV420P8)  # 4px diff = even ops
    
    config = ScreenshotConfig(odd_geometry_policy="auto")
    plans = plan_geometry([clip1, clip2], config)
    
    # Should not require full chroma
    assert all(not p.requires_full_chroma for p in plans)

def test_subsamp_safe_policy():
    """Test subsamp_safe policy prevents odd operations."""
    clip1 = create_test_clip(1920, 1036, format=vs.YUV420P8)
    clip2 = create_test_clip(1920, 1037, format=vs.YUV420P8)  # 1px diff
    
    config = ScreenshotConfig(odd_geometry_policy="subsamp_safe")
    plans = plan_geometry([clip1, clip2], config)
    
    # Verify no odd crops/pads in final plan
    for p in plans:
        assert p.crop_top % 2 == 0
        assert p.crop_bottom % 2 == 0
        assert p.pad_top % 2 == 0
        assert p.pad_bottom % 2 == 0

def test_dithering_determinism():
    """Test RGB conversion with dithering is deterministic."""
    clip = create_test_clip(1920, 1080, format=vs.YUV444P16)
    
    # Convert twice with same settings
    rgb1 = convert_to_rgb24(clip, dither="error_diffusion")
    rgb2 = convert_to_rgb24(clip, dither="error_diffusion")
    
    # Should produce identical output
    assert frames_are_identical(rgb1, rgb2)

def test_rgb_input_skips_promotion():
    """RGB/444 inputs should never trigger promotion."""
    clip = create_test_clip(1920, 1037, format=vs.RGB24)  # Odd height, RGB
    config = ScreenshotConfig(odd_geometry_policy="auto")
    plans = plan_geometry([clip], config)
    assert not plans[0].requires_full_chroma  # Already full-chroma

Patch 6: Docs and log notes
- docs/geometry_pipeline.md (or similar): document why odd-pixel symmetry needs a full-chroma pivot and the quality rationale. Clarify axis-aware promotion (vertical vs horizontal vs subsampling). State dithering occurs only at final 16→8 RGB24 hop; earlier conversions are non-dithered. Call out FFmpeg parity limitation (if any) and chosen default (ordered/none). Reiterate SDR-only pivot; HDR path unchanged.
- docs/config_reference.md: add odd_geometry_policy and rgb_dither
- CHANGELOG: note bugfix (mod-2 errors) and new configuration
- Ensure the Rich console shows a concise note when pivoting (debug/info level)

Implementation details and references

Axis-aware requirement logic:
- vertical_odd = any(x % 2 for x in (crop_top, crop_bottom, pad_top, pad_bottom))
- horizontal_odd = any(x % 2 for x in (crop_left, crop_right, pad_left, pad_right))
- needs_chroma = (vertical_odd and fmt.subsampling_h > 0) or (horizontal_odd and fmt.subsampling_w > 0)
- apply policy gates

Detection of SDR vs HDR:
- Reuse existing project logic (e.g., ColorConfig.enable_tonemap or frame props _Transfer) to decide whether clip is on HDR→SDR pipeline already. Only apply 444 pivot on SDR.

Dithering determinism:
- zimg’s error_diffusion is deterministic by default; ensure no RNG is used.
- If any “random” dithering is present elsewhere, seed for reproducibility.

Preserving current behavior:
- If plan has even-only geometry or source is already 4:4:4 (or RGB), stay on the fast path.
- If odd operations exist but policy == "subsamp_safe", planner should rebalance/align to even-only (current behavior), and log that perfect centering may shift by 1 px.

Acceptance tests (manual sanity)
- Reproduce the failing scenario:
  - 1920×1036 vs 1920×1038, mod_crop=2, letterbox_pillarbox_aware=true, upscale=true, pad_to_canvas="on"
  - Verify run completes and screenshots align with 1 px symmetric adjustments, no scaling.
- Verify identical behavior on clips with even geometry (no pivot logs).
- Verify HDR run path unchanged (no extra conversions, same output as before).

Out-of-scope
- Structural refactors or CI workflow changes.
- Retuning resampling kernels or tonemapping presets.
- Changing the default PNG encoder or compression settings.

How to validate locally
- uv run pyright
- uv run pytest -q
- Manual run: Your 1036/1038 case should complete without mod 2 errors and produce aligned PNGs.
