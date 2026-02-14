# LEGACY Frame Compare — Overlay + CLI UX Reference (Spec)

This document captures the **legacy** Frame Compare overlay and CLI “look & feel” from **static code + config + layout specs** in this repo.

## Constraints / Evidence Model

- **macOS runtime note:** The legacy pipeline is not reliably runnable on macOS (VapourSynth + plugins), and this audit environment is also offline (no dependency installs). As a result, **no live `--help` output or real run transcripts were executed** here.
- Everything below is derived from “source-of-truth” artifacts in this repo:
  - Overlay text composition: `src/frame_compare/render/overlay.py`
  - VapourSynth overlay application: `src/frame_compare/screenshot/render.py`
  - FFmpeg overlay application: `src/frame_compare/screenshot/render.py`
  - CLI wiring: `src/frame_compare/cli_entry.py`, `frame_compare.py`, `pyproject.toml`
  - CLI layout + theming spec: `cli_layout.v1.json` and renderer `src/frame_compare/layout/renderer.py`
  - Config defaults and validation: `src/data/config.toml.template`, `src/config_loader.py`, `src/datatypes.py`
  - Overlay regression tests (authoritative ordering/content): `tests/render/test_overlay_text.py`, `tests/runner/test_overlay_diagnostics.py`

## Audit commands executed (evidence sweep)

Commands were run from repo root (`/Users/tristan/Software/frame-compare-legacy`) on **2026-02-10 UTC** (see `date -u +%Y-%m-%d`).

Baseline timestamp:

- `date -u +%Y-%m-%d`

Overlay discovery:

- `rg -n "compose_overlay_text|OVERLAY_STYLE|FRAME_INFO_STYLE|apply_overlay_text|apply_frame_info_overlay|drawtext" -S src/frame_compare`
- `sed -n '1,220p' src/frame_compare/render/overlay.py`
- `sed -n '1,220p' src/frame_compare/screenshot/render.py`
- `sed -n '1440,1625p' src/frame_compare/screenshot/render.py` (FFmpeg `drawtext`)
- `sed -n '1,520p' src/frame_compare/diagnostics.py` (diagnostic line formatting)
- `sed -n '1,260p' tests/render/test_overlay_text.py`

CLI discovery:

- `sed -n '1,240p' frame_compare.py`
- `sed -n '1,420p' src/frame_compare/cli_entry.py` (run entry; JSON tail; slow.pics/report post-run prints)
- `sed -n '430,1040p' src/frame_compare/cli_entry.py` (Click options + subcommands)
- `sed -n '330,720p' src/frame_compare/cli_runtime.py` (output managers + error formatting)
- `cat cli_layout.v1.json` and `nl -ba cli_layout.v1.json | sed -n ...`
- `sed -n '1,360p' cli_layout.v1.json` (theme + section ordering)
- `sed -n '360,460p' cli_layout.v1.json` (folding + json_tail policy)
- `sed -n '360,2335p' src/frame_compare/layout/renderer.py` (box/list/group/table/progress rendering rules)
- `sed -n '1,240p' src/frame_compare/layout/terminal.py` (ANSI color capability detection + `NO_COLOR`/force-256)
- `sed -n '40,220p' src/data/config.toml.template` (defaults for overlay + CLI)
- `sed -n '600,700p' src/config_loader.py` (overlay_mode validation)
- `sed -n '320,430p' src/frame_compare/orchestration/phases/analysis.py` (output frame preview folding)
- `sed -n '120,220p' src/frame_compare/orchestration/phases/render.py` (diagnostic frame metrics injection)

Assets sweep:

- `rg -n "\\.ttf|\\.otf|fonts?/" -S .`
- `find . -type f \\( -iname '*.ttf' -o -iname '*.otf' \\) | sed -n '1,200p'` (found only in `.uv_cache/**`)
- `find . \\( -path './.uv_cache' -o -path './node_modules' -o -path './.venv' -o -path './.git' \\) -prune -o -type f \\( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.webp' \\) -print | sed -n '1,200p'` (no legacy overlay goldens)

FC2 verification (for porting notes):

- `sed -n '1,220p' /Users/tristan/Software/frame-compare/pyproject.toml`
- `sed -n '1,220p' /Users/tristan/Software/frame-compare/src/frame_compare/render/overlay.py`

Attempted (and failed) to run the CLI locally due to offline deps / macOS toolchain constraints:

- `python3 -m frame_compare --help` → `ModuleNotFoundError: No module named 'click'`
- (No network access in this audit environment, so missing deps could not be installed to capture verbatim Rich/Click output.)

---

# 1) Overlay UX (recreate-able spec)

Legacy overlay has two distinct “layers” (both are text):

1. **Frame Info overlay** (small block near the top-left): frame index, picture type, and a clip label.
2. **Overlay Text block** (below the frame info): tonemap/diagnostic text + geometry summary + selection info.

Both are applied during screenshot export, via either:

- **VapourSynth writer path** (preferred): `core.sub.Subtitle(...)` (ASS style) with fallback to `core.text.Text(...)`
- **FFmpeg writer path** (fallback/fast): `-vf drawtext=...` (FFmpeg `drawtext` filter)

## 1.1 What information is shown (every field, in display order)

### A) Frame Info overlay (top-left)

Source: `src/frame_compare/screenshot/render.py` (`apply_frame_info_overlay`).

**Display order (exact line order):**

1. `Frame {display_idx} of {clip_ref.num_frames}`
2. `Picture type: {pict_text}`
3. *(separate subtitle event, same style; starts with padding lines)*
   `title` (derived from clip label; default `"Clip"` if empty)
   Optional: `Selection: {selection_text}` (only when non-empty `selection_label` passed)

**Field notes:**

- `display_idx` is either the **requested frame** (if provided) or the actual VapourSynth callback frame `n`.
- `pict_text` comes from frame prop `_PictType`:
  - bytes → decoded as UTF-8 (errors ignored)
  - str → used as-is
  - otherwise → `"N/A"`

### B) Overlay Text block (below frame info)

Source: `src/frame_compare/render/overlay.py` (`compose_overlay_text`).

Overlay text is a **multi-line string** joined with `\n`. Two modes exist:

#### Mode: “minimal” (and any non-`diagnostic` string)

Display order:

1. `base_text` *(only if provided; typically tonemap template output)*
2. Resolution summary: `format_resolution_summary(plan)` (see below)
3. Frame selection line: `Frame Selection Type: {SelectionLabel}`

Where `SelectionLabel` is normalized via:

- known mappings: `dark→Dark`, `bright→Bright`, `motion→Motion`, `user→User`, `random→Random`, `auto→Auto`, `cached→Cached`
- unknown / blank / None → `"(unknown)"`

#### Mode: “diagnostic”

Display order:

1. `base_text` *(only if provided)*
2. Resolution summary: `format_resolution_summary(plan)`
3. `MDL: ...` mastering display luminance line *(only when `tonemap_info.applied == True`)*
4. `HDR: ...` (MaxCLL/MaxFALL) *(only when present in frame props)*
5. `DoVi: ...` (Dolby Vision line) *(only when it renders non-empty)*
6. `DV RPU Level 1 ...` *(only when present)*
7. `DV L5 Active Area: ...` *(only when present)*
8. `DV L6 Metadata: ...` *(only when present)*
9. `Range: Limited|Full` *(only when `_ColorRange`/`_colorrange` present)*
10. `Measurement MAX/AVG: ...` *(only when per-frame metrics were injected; see §1.5)*
11. Frame selection line: `Frame Selection Type: {SelectionLabel}`

**Resolution summary formatting**

Source: `src/frame_compare/layout_utils.py` (`format_resolution_summary`).

- Uses `plan["cropped_w"], plan["cropped_h"]` and `plan["final"]`.
- If final equals cropped: `"{W} × {H}  (native)"`
- Else: `"{W} × {H} → {finalW} × {finalH}  (original → target)"`

## 1.2 Where it appears (anchors/positions, margins, alignment, safe areas)

### VapourSynth writer path (ASS style)

Overlay uses `core.sub.Subtitle(...)` with ASS `style=` strings:

- `FRAME_INFO_STYLE` (frame info): `src/frame_compare/render/overlay.py`
- `OVERLAY_STYLE` (overlay text block): `src/frame_compare/render/overlay.py`

**ASS Alignment + Margins (source-of-truth):**

Both styles set `Alignment=7` (top-left anchor).

- Frame info margin: `MarginL=10`, `MarginR=10`, `MarginV=10`
- Overlay text margin: `MarginL=10`, `MarginR=10`, `MarginV=140`

Interpretation:

- Both blocks are anchored to the **top-left** safe area.
- “Safe area” is effectively the ASS margins (10px inset on left/right; 10px down for frame info; 140px down for overlay text).

**Additional spacing behavior for the label/title (frame info)**

`apply_frame_info_overlay` renders the title label as a second subtitle call with a prefix:

```text
" " + ("\n" * 3) + label_text
```

So the label block starts after **4 “lines”** (one line containing a single space, then three empty lines), ensuring it appears below the `Frame … / Picture type …` lines even though it shares the same ASS style/margins.

#### ASS style strings (decoded fields)

Source: `src/frame_compare/render/overlay.py` (`FRAME_INFO_STYLE`, `OVERLAY_STYLE`).

The legacy strings are serialized ASS “Style:” fields in this shape:

`Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding"`

**ASS color encoding note (important for correctness):** colors are encoded as `&HAABBGGRR` (alpha, blue, green, red).
So `&H00FFFFFF` = opaque-ish white, `&H00000000` = black, and `&H000000FF` = red.

For pixel-accurate replication, treat the literal strings below as the source of truth (even if some fields are effectively unused by libass/VapourSynth in this usage):

```text
FRAME_INFO_STYLE = 'sans-serif,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"0,0,0,0,100,100,0,0,1,2,0,7,10,10,10,1"'
OVERLAY_STYLE     = 'sans-serif,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"0,0,0,0,100,100,0,0,1,2,0,7,10,10,140,1"'
```

**`FRAME_INFO_STYLE`**

- Font: `sans-serif`, size `20`
- Colors:
  - Primary (fill): `&H00FFFFFF` (white)
  - Outline: `&H00000000` (black)
  - Secondary: `&H000000FF` (red; typically unused for non-karaoke subtitles)
  - Back: `&H00000000` (black; used for shadow when `Shadow>0`, but legacy sets `Shadow=0`)
- Outline/shadow:
  - `BorderStyle=1`
  - `Outline=2`
  - `Shadow=0`
- Placement:
  - `Alignment=7` (top-left)
  - `MarginL=10`, `MarginR=10`, `MarginV=10`

**`OVERLAY_STYLE`**

Same as `FRAME_INFO_STYLE` except:

- `MarginV=140`

### FFmpeg writer path (`drawtext`)

Source: `src/frame_compare/screenshot/render.py` (`save_frame_with_ffmpeg`).

Frame info drawtext:

- `x=10`, `y=10`
- Text content:
  - Always: `Frame {frame_idx}`
  - Optional: `Content Type: {selection_label}`

Overlay text drawtext:

- `x=10`, `y=80`
- Text content: the multi-line `overlay_text`

## 1.3 Typography (font family source/path, size rules, weight, casing)

### VapourSynth (ASS style)

Font:

- Font name: `sans-serif`
- Font size: `20`

No explicit font file is bundled in legacy; font resolution depends on the host system’s fontconfig/libass resolution of `"sans-serif"`.

### FFmpeg `drawtext`

No explicit `fontfile=` or `font=` is set in legacy drawtext filters. FFmpeg therefore uses its default font discovery (varies by platform/build).

### Determinism note (important for pixel-accuracy)

Because legacy does **not** ship a `.ttf/.otf` and does **not** pin font selection for either backend:

- You can match **positions, font size, outline width, and colors** and still get different glyph metrics across OSes/builds.
- If FC2 requires cross-platform pixel determinism, bundling a font and explicitly selecting it (VapourSynth ASS + FFmpeg `fontfile=`) is the pragmatic approach, but it is a behavioral change relative to legacy.

## 1.4 Styling (fill colors, stroke/outline width, shadow, opacity, separators)

### VapourSynth (ASS style)

Both styles share these core values (from `FRAME_INFO_STYLE` / `OVERLAY_STYLE`):

- Primary (fill) color: white `&H00FFFFFF`
- Outline color: black `&H00000000`
- Border style: `1`
- Outline width: `2`
- Shadow: `0`
- Alignment: `7` (top-left)

Frame info uses `MarginV=10`; overlay block uses `MarginV=140`.

### FFmpeg `drawtext`

Both drawtext blocks share:

- `fontcolor=white`
- `borderw=2`
- `bordercolor=black`
- `box=0` (no rectangle background)
- `shadowx=1`, `shadowy=1`, `shadowcolor=black`

## 1.5 Conditional logic (when fields appear/disappear)

### Overlay enabled/disabled

Source: `src/frame_compare/render/overlay.py` (`compose_overlay_text`).

- If `color_cfg.overlay_enabled == false`: `compose_overlay_text(...)` returns `None` and **no overlay text block is applied**.

### Overlay mode

Source: `src/config_loader.py` enforces:

- `[color].overlay_mode` must be `"minimal"` or `"diagnostic"` (normalized to lower-case).

Runtime behavior:

- `compose_overlay_text` treats any mode other than `"diagnostic"` as “minimal”.

### Whether `base_text` exists

`base_text` is primarily set by the tonemap stage:

Source: `src/frame_compare/vs/tonemap.py` (`process_clip_for_screenshot`).

- For HDR sources where tonemapping is applied and overlays are enabled:
  `overlay_text = overlay_text_template.format(...)`
- For SDR sources (tonemap bypass) and/or when overlays are disabled: `overlay_text = None`

So in practice, the first overlay line (“Tonemapping Algorithm: …”) usually appears only when HDR tonemap is active.

#### Overlay template keys (what `{...}` can reference)

Source: `src/frame_compare/vs/tonemap.py` (`_format_overlay_text`).

The legacy `[color].overlay_text_template` is a Python `str.format` template. It can reference:

- `tone_curve` (alias: `curve`)
- `dynamic_peak_detection` (numeric), `dpd` (numeric)
- `dynamic_peak_detection_bool` (bool), `dpd_bool` (bool)
- `target_nits` (int when whole-number, else float)
- `target_nits_float` (always float)
- `preset`
- `reason`
- `dst_min_nits`, `knee_offset`
- `dpd_preset`, `dpd_black_cutoff`
- `post_gamma`, `post_gamma_enabled`
- `smoothing_period`, `scene_threshold_low`, `scene_threshold_high`
- `percentile`, `contrast_recovery`
- `metadata`, `use_dovi`
- `visualize_lut`, `show_clipping`

Failure behavior:

- If formatting fails (missing key, bad format spec), legacy returns the raw template string unchanged (it does not crash the run).

### Per-frame “Measurement …” line (diagnostic only)

This line appears only when:

1. `[color].overlay_mode = "diagnostic"`, **and**
2. `[diagnostics].per_frame_nits = true` (or overridden on CLI), **and**
3. a frame has a valid selection score to convert into nits, **and**
4. the orchestrator injects `selection_detail["diagnostics"]["frame_metrics"]`

Source: `src/frame_compare/orchestration/phases/render.py` (builds `selection_overlay_details`).

### Debug-color disables overlays

Source: `src/frame_compare/screenshot/orchestrator.py`:

- When `debug_color` is enabled: overlay text is not generated/applied and FFmpeg writer is disabled.

### Frame info overlay enable/disable

Source: `src/frame_compare/screenshot/orchestrator.py`:

- `frame_info_allowed_default = bool(cfg.screenshots.add_frame_info and not debug_enabled)`

So:

- `[screenshots].add_frame_info=false` disables the frame info overlay
- debug-color implicitly disables it

### Backend differences / fallbacks

- VapourSynth overlay prefers `core.sub.Subtitle`; if unavailable it tries `core.text.Text(..., alignment=9)` (style differs and is plugin-dependent).
- FFmpeg path uses `drawtext` and is only available if `ffmpeg` exists on PATH.

## 1.6 Backend differences / edge cases (must replicate if you want true legacy parity)

### 1.7.1 Frame number shown: requested vs resolved

Legacy can show different “Frame N” numbers depending on backend:

- VapourSynth writer (`save_frame_with_fpng` in `src/frame_compare/screenshot/render.py`):
  - signature includes both:
    - `frame_idx`: the actual frame index used to fetch/render
    - `requested_frame`: the user-requested index (pre mapping/clamping)
  - `apply_frame_info_overlay(..., requested_frame=...)` displays **requested_frame**
- FFmpeg writer (`save_frame_with_ffmpeg` in `src/frame_compare/screenshot/render.py`):
  - only has one index: the resolved `frame_idx` used by `select=eq(n\\,{frame_idx})`
  - the drawtext block displays **resolved frame_idx**

Implication:

- When alignment maps or trim offsets shift indices, and you switch backend (`[screenshots].use_ffmpeg`), the overlaid “Frame …” line can change even if the exported filename still uses the requested frame index.

### 1.7.2 Overlay placement changes under the VapourSynth fallback

Overlay text application (`apply_overlay_text`) falls back from:

- `core.sub.Subtitle(clip, text=[...], style=OVERLAY_STYLE)`

to:

- `core.text.Text(clip, text, alignment=9)`

Two important changes:

1. the style changes (no ASS outline/margins; depends on plugin defaults)
2. `alignment=9` typically anchors to **top-right** (numpad-style), not top-left

Frame info overlay (`apply_frame_info_overlay`) does **not** have this fallback; if `Subtitle` is missing, frame-info overlay is skipped.

### 1.7.3 Overlay range normalization step (VapourSynth writer)

Before applying any text, `save_frame_with_fpng` normalizes the render clip for overlay:

- converts to `RGB24` using `core.resize.Point(..., dither_type="none")` when possible
- sets/normalizes `_ColorRange` to match the “overlay input range”
- applies overlays (frame info + overlay text)
- restores original format + range (best-effort) after overlay

This is gated by:

- `frame_info_allowed` OR (`overlays_allowed` AND `overlay_text` is non-empty)

Debugging knobs:

- `FRAME_COMPARE_LOG_OVERLAY_RANGE=1` emits per-frame overlay range logs (pre/normalized/restored).

### 1.7.4 Drawtext escaping (FFmpeg writer)

FFmpeg overlays call:

- `escape_drawtext(text)` (delegates to `src/frame_compare/render/encoders.py`)

Exact escaping mapping (legacy behavior):

- `\` → `\\`
- `:` → `\:`
- `=` → `\=`
- `,` → `\,`
- `[` → `\[`
- `]` → `\]`
- `'` → `\'`
- newline `\n` → literal sequence `\\n` (so FFmpeg drawtext renders a line break)

Otherwise, overlay text will render incorrectly or the ffmpeg filter chain will fail to parse.

## 1.7 Examples (text payloads you must reproduce)

These examples are based on the overlay regression tests (authoritative ordering):

- `tests/render/test_overlay_text.py`

### Repo screenshots / goldens

No first-party overlay “golden” screenshots were found in the legacy repo outside dependency caches (for example `.uv_cache/.../*.png` from unrelated packages). The overlay UX spec here is therefore derived from code and tests rather than reference images.

### Example 1 — “simple” (minimal)

```text
Base
1920 × 1080  (native)
Frame Selection Type: Dark
```

### Example 2 — “busy” (diagnostic)

Representative diagnostic output contains a superset of these lines (exact presence depends on frame props):

```text
Base
1920 × 1080  (native)
MDL: min: 0.005 cd/m², max: 1000 cd/m²
HDR: MaxCLL 900 / MaxFALL 300
DoVi: on (Target: 800nits) L2 2/10 target 800 nits
DV RPU Level 1 MAX/AVG: 450nits / 12.5nits
Range: Limited
Measurement MAX/AVG: 180.0nits / 120.5nits (highlight)
Frame Selection Type: Bright
```

---

# 2) CLI UX (help + transcripts + formatting)

## 2.1 Primary CLI entrypoint(s)

Source of truth:

- Console script: `pyproject.toml` → `frame-compare = "frame_compare:main"`
- Shim: `frame_compare.py` → `main = src.frame_compare.cli_entry.main`
- Click wiring: `src/frame_compare/cli_entry.py`

### Commands (legacy)

`frame-compare` is a Click group (`@click.group(invoke_without_command=True)`):

- default (no subcommand): runs the full pipeline
- `run`: explicit alias for the default pipeline
- `doctor`: dependency diagnostics (`--json` optional)
- `wizard`: interactive config wizard (`--preset` optional)
- `preset list`: list preset names
- `preset apply <name>`: apply a preset and write config

## 2.2 `--help` output (reconstructed from Click decorators)

Because live execution is unavailable in this audit, the following is a **reconstruction** of the legacy help surface based on the Click decorators in `src/frame_compare/cli_entry.py`.

### `frame-compare --help`

Options (names + help strings are exact):

- `--root` — “Workspace root override. Defaults to FRAME_COMPARE_ROOT or sentinel discovery.”
- `--config` — optional config path help text (see `_DEFAULT_CONFIG_HELP` in `src/frame_compare/core.py`)
- `--input` — “Override [paths.input_dir] from config.toml”
- `--audio-align-track label=index` — “Manual audio track override in the form label=index. Repeatable.”
- `--quiet` — “Suppress verbose output; show At-a-Glance, progress, and JSON only.”
- `--verbose` — “Show additional diagnostic output during run.”
- `--no-color` — “Disable ANSI colour output.”
- `--json-pretty` — “Pretty-print the JSON tail output.”
- `--no-cache` — “Force recomputation even when cached analysis artifacts exist.”
- `--from-cache-only` — “Render cached CLI output without recomputing; fails when no snapshot exists.”
- `--show-partial` — “Display sections marked as partial when rendering cached runs.”
- `--show-missing/--hide-missing` — “Toggle placeholder blocks for sections the cache cannot reconstruct…”
- `--diagnose-paths` — “Print the resolved config/input/output paths as JSON and exit.”
- `--write-config` — “Ensure the workspace config exists … and exit.”
- `--no-wizard` — “Skip automatic wizard prompts when creating a new config.”
- `--html-report` — “Enable HTML report generation regardless of config.”
- `--no-html-report` — “Disable HTML report generation regardless of config.”
- `--debug-color` — “Enable colour pipeline debugging (logs plane stats, dumps intermediate PNGs).”
- `--diagnostic-frame-metrics` / `--no-diagnostic-frame-metrics` — enable/disable per-frame metric overlay injection
- `--tm-*` options — tonemap overrides (preset/curve/target/dst-min/knee/dpd/gamma/etc.)

Subcommands shown in help:

- `run`, `doctor`, `wizard`, `preset`

#### As-implemented note: `--quiet` behavior differs from the help string

The help text says:

- `--quiet` — “Suppress verbose output; show At-a-Glance, progress, and JSON only.”

But the reporter selection code uses a dedicated “null” output manager when `quiet=True`:

- `src/frame_compare/orchestration/reporting.py:create_reporter` chooses `NullCliOutputManager` when `request.quiet` is true.
- `NullCliOutputManager` discards all layout rendering and progress output.

So as implemented, `--quiet` primarily yields:

- minimal non-layout prints that happen outside the reporter (e.g., slow.pics / report summary lines in `src/frame_compare/cli_entry.py`)
- optional JSON tail (if `[cli].emit_json_tail=true`)

If FC2 aims to “match legacy UX”, decide whether to preserve the *help text intent* (At-a-Glance + progress) or the *current code behavior* (suppress the whole dashboard).

### `frame-compare doctor --help`

- `--json` — “Emit machine-readable diagnostics.”

## 2.3 Output style (human-readable) — the “layout dashboard”

The main pipeline renders a **data-driven dashboard** using:

- Layout spec: `cli_layout.v1.json`
- Renderer: `src/frame_compare/layout/renderer.py` (`CliLayoutRenderer`)

### Section order (as rendered by layout spec)

`cli_layout.v1.json` defines these sections in order:

1. `vspreview_missing` (box; conditional)
2. `vspreview_info` (box; conditional)
3. `at_a_glance` (box; always, and is allowed even in `--quiet`)
4. `discover` (list)
5. `prepare` (group)
6. `audio_align` (group; conditional)
7. `analyze` (group)
8. `render` (group)
9. `publish` (group)
10. `warnings` (table)
11. `summary` (list)

### Boxes

Source: `src/frame_compare/layout/renderer.py` (`_render_box_section`).

- Unicode borders: `┌ ┐ └ ┘` and `─`
- Title is injected into the top border as `┌ {title} ───┐`
- Width is computed as:
  - `width = min(console_width, max(20, max_visible_line_len + 4, title_visible_len + 2))`
  - `inner_width = width - 4`
  - Each line is truncated/padded to `inner_width` and rendered as `│ {line} │`

### Group subtitles

Source: `src/frame_compare/layout/renderer.py` (`_format_subtitle`, `_build_rule_line`).

- Subtitle prefix:
  - Unicode mode: `› Subtitle`
  - ASCII fallback (or when `--no-color`): `> Subtitle`
- Decorative rule line (only when terminal width ≥ 80):
  - Unicode mode: dim `─` line
  - ASCII fallback: `-` line

### Colors, roles, and symbols

Source: `cli_layout.v1.json` theme + `src/frame_compare/layout/terminal.py`.

- Color roles come from `theme.colors` (e.g. `header=cyan.bold`, `warn=yellow`, etc.)
- Role spans are written in layout strings as `[[role]]...[[/]]` and translated into ANSI.
- `--no-color` or `NO_COLOR=1` disables color entirely.
- The renderer can force 256-color mapping via `FRAME_COMPARE_FORCE_256_COLOR=1`.

Additional renderer styling behaviors (easy to miss):

- **Key token auto-highlighting:** after applying `[[role]]` spans, the renderer scans for key-ish tokens and colors them even if the template did not include explicit role spans:
  - `word=` at a token boundary (e.g., `writer=`) gets the `accent` role on the key
  - `word:` (but not `://`) gets the `accent` role on the key
- **Boolean word highlighting:** the words `yes/no/true/false/enabled/disabled/ok` are mapped to `success` or `warn` roles (when colors enabled).

### Theme details (role tokens and values)

Source: `cli_layout.v1.json` → `theme.colors`, `theme.symbols`, `theme.units`, `layout.*`, `highlights`.

Roles → style tokens (exact legacy values):

- `header = cyan.bold`
- `accent = blue.bright`
- `accent_prepare = blue`
- `accent_analyze = purple.bright`
- `accent_render = magenta.bright`
- `accent_publish = green.bright`
- `section_discover = cyan.bold`
- `section_prepare = cyan.bold`
- `section_analyze = cyan.bold`
- `section_render = cyan.bold`
- `section_publish = cyan.bold`
- `section_warnings = yellow.bold`
- `section_summary = green.bold`
- `accent_subhead = yellow.bright`
- `value = white.bright`
- `unit = grey.dim`
- `key = blue`
- `path = grey.dim`
- `success = green`
- `warn = yellow`
- `error = red`
- `dim = grey.dim`
- `rule_dim = grey.dim`
- boolean / numeric highlight roles:
  - `bool_true = green`
  - `bool_false = red`
  - `number_ok = green`
  - `number_warn = yellow`
  - `number_bad = red`

Symbols (exact legacy values):

- `ok = ✓`, `warn = !`, `err = ✗`
- ASCII versions exist (`ascii_ok`, etc.), but the renderer’s ASCII-vs-Unicode mode is effectively:
  - ASCII when `--no-color` (or `NO_COLOR=1`) OR console encoding does not look UTF-compatible

Units (exact legacy values):

- `seconds_decimals = 2` (default float formatting precision)
- `offset_decimals = 3` (used by some templates that explicitly format offsets)
- `timecode_ms = 3`
- `thousands_sep = true` (enables `1,234` formatting for integers)

Layout (exact legacy values):

- `two_column_min_cols = 120` (switch list sections to two columns)
- `blank_line_between_sections = true` (inserts a blank line between sections)
- `path_ellipsis = "middle"` (truncate paths by preserving the last segment)
- `truncate_right_label_min_cols = 100` (when narrower, progress right label truncates at first ` | `)

### Value formatting rules (renderer behavior)

Source: `src/frame_compare/layout/renderer.py` (`_format_value`, `_apply_filter`, `apply_path_ellipsis`).

- Booleans format as literal `true` / `false`.
- Integers use thousands separators because `theme.units.thousands_sep` is truthy.
- Floats format with `seconds_decimals` (=2) by default unless an explicit format spec is used in the template (e.g. `:.3f`).
- Filters used by templates include:
  - `|bool` → `true/false`
  - `|ellipsis` → middle-ellipsis truncation
  - `|tallest` → prints `"tallest"` when value is falsy
  - `|none` / `|unchanged` → placeholder behavior for missing values
  - `|wrap_indent2` / `|summary_wrap` → line wrapping with hanging indents

### Highlight rules (what gets emphasized in color)

Legacy highlight triggers from `cli_layout.v1.json`:

- `audio_alignment.enabled`, `overlay.enabled`, `render.add_frame_info`, `render.upscale`:
  - highlight role: `bool_true` vs `bool_false`
- `audio_alignment.offsets_sec` absolute > 1.0 → `number_warn`
- `vspreview.suggested_seconds` absolute > 0.5 → `number_warn`
- `analysis.counts.motion` > 0 → `accent_analyze`
- `progress.fps` < 1.0 → `number_warn`
- `verify.delta.max`:
  - > `{tonemap.verify_luma_threshold}` → `number_bad`
  - abs > `{tonemap.verify_luma_threshold} * 0.9` → `number_warn`

### Error formatting + stdout/stderr conventions

Sources:

- `src/frame_compare/cli_runtime.py` (`CLIAppError`, `CliOutputManager.error`)
- `src/frame_compare/cli_entry.py` (prints `exc.rich_message`, catches exceptions)
- `src/frame_compare/orchestration/setup.py` (`emit_dovi_debug`)

Legacy behaviors:

- Most dashboard output is printed via a Rich `Console` attached to the reporter (default: stdout).
- `CLIAppError` carries:
  - `message` (plain)
  - `rich_message` (Rich markup); Click entrypoints print `rich_message`.
- Reporter “error” lines (when used) render as:
  - `[bold red]Error:[/bold red] {escaped_message}`
- Additional “post-run” status lines (slow.pics + HTML report) are printed directly in `src/frame_compare/cli_entry.py` using `from rich import print` and are *not* suppressed by `--quiet` (because they bypass the reporter).
- `FRAME_COMPARE_DOVI_DEBUG=1` emits lines prefixed with `[DOVI_DEBUG]` as JSON to **stderr**.
- Unhandled exceptions in the default `frame-compare` invocation path print a Python traceback via `Console().print_exception()` and then exit 1.

## 2.4 Progress bars

Progress blocks are declared in `cli_layout.v1.json` via `"type": "progress"` with IDs:

- `analyze_bar`
- `render_bar`
- `render_clip_bar`
- `upload_bar`

Progress style is configured via:

- config: `[cli.progress].style = "fill" | "dot"` in `config.toml`
- applied at runtime in `src/frame_compare/orchestration/phases/setup.py`

Behavior (source: `src/frame_compare/layout/renderer.py`):

- `fill` uses Rich `BarColumn`
- `dot` uses Rich `SpinnerColumn`

## 2.4.1 Warnings table semantics (as implemented)

The layout JSON describes a warnings “table” with grouping/folding knobs, but the **grouping and folding are implemented in the runner**, not in `CliLayoutRenderer`.

Source: `src/frame_compare/orchestration/phases/result.py`.

As implemented:

- the runner collects warnings as a flat list of strings (`reporter.warn(...)`)
- it de-duplicates while preserving order (`list(dict.fromkeys(...))`)
- it always produces a single synthetic row for the `warnings` section:
  - `warning.type = "general"`
  - `warning.count = len(warnings_list)`
  - `warning.labels = folded labels`
- folding defaults are taken from `cli_layout.v1.json` (`fold_labels`) with fallbacks:
  - `head=2`, `tail=1`, `joiner=", "`
  - folding is enabled when `when` evaluates truthy; legacy uses `when: "!verbose"`

So in practice, the warnings “table” is a **single bullet row** like:

`• general — 3 occurrence(s): ...`

## 2.5 JSON tail output (machine-readable) and `--json-pretty`

At the end of a run, legacy prints a JSON object (“JSON tail”) when enabled:

- config: `[cli].emit_json_tail` (default `true`)
- CLI: `--json-pretty` controls indent vs compact separators

Source: `src/frame_compare/cli_entry.py` (end of `_run_cli_entry`).

## 2.5.1 JSON tail schema (what keys exist, and who writes them)

The “JSON tail” is initialized before any heavy work and then incrementally populated across phases.

Initialization:

- `src/frame_compare/orchestration/reporting.py:create_initial_json_tail`

Population (high-level):

- Setup / paths / cache snapshot wiring:
  - `src/frame_compare/orchestration/phases/setup.py`
  - `src/frame_compare/result_snapshot.py` (snapshot contract)
- Discovery, loader, analysis, render, publish:
  - `src/frame_compare/orchestration/phases/*`
- Final warnings + snapshot + rendering:
  - `src/frame_compare/orchestration/phases/result.py`

Common top-level keys (not exhaustive, but these are stable “shape anchors”):

- `clips`: list of per-clip records (labels, fps, dimensions, etc.)
- `trims`: per-clip trim summary (`lead_f`, `trail_f`, seconds equivalents)
- `window`: ignore lead/trail + min window seconds
- `alignment`: manual alignment start/end seconds
- `audio_alignment`: enabled/use_vspreview + offsets + suggestions + captured streams
- `analysis`: selection config, counts, cache status, selected frames list/preview
- `render`: writer backend, out_dir, canvas/crop/pad settings, compression, timeouts
- `tonemap`: effective tonemap settings + derived labels (`metadata_label`, `use_dovi_label`)
- `overlay`: enabled/template/mode + (in diagnostic mode) `diagnostics` block
- `verify`: verification summaries and thresholds
- `slowpics`, `report`, `viewer`: publish/report destinations
- `warnings`: final warning list
- `cache`: cached-run metadata and snapshot path/state

If FC2 wants to preserve legacy automation affordances, porting this JSON tail (or a clearly versioned successor) is usually the highest leverage move.

### Output frame list folding (CLI-only formatting detail)

Legacy intentionally folds the “output frames preview” string that appears in the dashboard/summary when not verbose.

Sources:

- Folding rule definition: `cli_layout.v1.json` → `folding.frames_preview`
- Folding implementation: `src/frame_compare/orchestration/phases/analysis.py` (Preview Rule Logic) → `runtime_utils.fold_sequence(...)`

Legacy defaults (from layout JSON):

- `head=4`, `tail=4`, `joiner=", "`, `when="!verbose"`

Implication:

- In default runs, the CLI typically shows only the first 4 and last 4 selected frames with a single `…` in the middle.
- In `--verbose` runs, the preview is unfolded (full list) unless other downstream truncation occurs (terminal width, wrapping).

#### Cache snapshot file (used by `--from-cache-only`)

Legacy persists a snapshot JSON file after runs (including rendered values/flags/section availability + JSON tail). This file is what `--from-cache-only` re-renders.

Sources:

- Snapshot building/writing: `src/frame_compare/result_snapshot.py` (`build_snapshot`, `write_snapshot`, `snapshot_path`)
- Snapshot write call site: `src/frame_compare/orchestration/phases/result.py`

## 2.6 Copy/paste transcripts (templates)

These transcripts are **templates** showing the exact legacy formatting rules and line templates; substitute runtime values as needed.

### Happy path (no-color template)

Command:

```bash
frame-compare --no-color --root /path/to/workspace
```

Output skeleton (sections/lines as defined by `cli_layout.v1.json`):

```text
┌ At-a-Glance ───────────────────────────────┐
│ Clips: {clips.count}  Step {analysis.step}  Downscale {analysis.downscale_height}px │
│ Frames kept {analysis.output_frame_count}  scanned {analysis.scanned}  Cache {cache.status} │
│ Viewer {viewer.mode_display} → {viewer.destination_label} │
│ Window lead {window.ignore_lead_seconds:.2f}s  trail {window.ignore_trail_seconds:.2f}s  min {window.min_window_seconds:.2f}s │
│ Plan dark {analysis.counts.dark}  bright {analysis.counts.bright}  motion {analysis.counts.motion}  random {analysis.counts.random}  user {analysis.counts.user} │
│ Audio align {audio_alignment.enabled|bool} │
│ Canvas single_res {render.single_res|tallest}px  upscale {render.upscale|bool}  pad {render.center_pad|bool} │
│ Tonemap {tonemap.preset} → {tonemap.target_nits:.0f}nits  Curve {tonemap.tone_curve} │
└────────────────────────────────────────────┘

[DISCOVER]
• ref={clips.ref.label}  {clips.ref.width}x{clips.ref.height} @ {clips.ref.fps:.3f}fps  frames={clips.ref.frames}  dur={clips.ref.duration_tc}
• tgt={clips.tgt.label}  {clips.tgt.width}x{clips.tgt.height} @ {clips.tgt.fps:.3f}fps  frames={clips.tgt.frames}  dur={clips.tgt.duration_tc}
TMDB: {tmdb.category}/{tmdb.id} “{tmdb.title} ({tmdb.year})”  lang={tmdb.lang}

[PREPARE]
> Trim
----------------
• Ref: lead={trims.ref.lead_f:>4}f ({trims.ref.lead_s:>5.2f}s)  trail={trims.ref.trail_f:>4}f ({trims.ref.trail_s:>5.2f}s)
• Tgt: lead={trims.tgt.lead_f:>4}f ({trims.tgt.lead_s:>5.2f}s)  trail={trims.tgt.trail_f:>4}f ({trims.tgt.trail_s:>5.2f}s)

> Window
----------------
ignore_lead={window.ignore_lead_seconds:.2f}s  ignore_trail={window.ignore_trail_seconds:.2f}s  min={window.min_window_seconds:.2f}s  downscale={analysis.downscale_height}px

> Alignment(manual)
----------------
start={alignment.manual_start_s}s  end={alignment.manual_end_s|unchanged}s

> Overrides
----------------
change_fps={overrides.change_fps|none}

[PREPARE · Audio]
{audio_alignment.stream_lines_text|wrap_indent2}
{audio_alignment.offset_lines_text|wrap_indent2}
Offsets file: {audio_alignment.offsets_filename.e} (manual edit suggested)

[ANALYZE]
> Config
----------------
Config: step={analysis.step}  method={analysis.motion_method}  scenecut_q={analysis.motion_scenecut_quantile}  diff_radius={analysis.motion_diff_radius}  downscale={analysis.downscale_height}px

> Plan
----------------
Plan: Dark={analysis.counts.dark}  Bright={analysis.counts.bright}  Motion={analysis.counts.motion}  Random={analysis.counts.random}  User={analysis.counts.user}  sep={analysis.screen_separation_sec:.1f}s  Seed={analysis.random_seed}

{analysis.cache_progress_message}
{analyze_bar}

[RENDER]
> Writer
----------------
writer={render.writer} out_dir={render.out_dir.e} add_frame_info={render.add_frame_info|bool}

> Canvas
----------------
single_res={render.single_res|tallest}px upscale={render.upscale|bool} crop=mod{render.mod_crop} letterbox_aware={render.letterbox_pillarbox_aware|bool} pad={render.center_pad|bool} tol={render.letterbox_px_tolerance}px

> Tonemap
----------------
curve={tonemap.tone_curve} target={tonemap.target_nits:.0f}nits dst_min={tonemap.dst_min_nits:.2f} knee={tonemap.knee_offset:.2f}
dpd={tonemap.dpd|bool} ({tonemap.dpd_preset}) cutoff={tonemap.dpd_black_cutoff:.3f} gamma={tonemap.post_gamma:.2f}*

> Overlay
----------------
enabled={overlay.enabled|bool} mode={overlay.mode}

{render_bar}
> Active Clip
{render_clip_bar}

[PUBLISH]
> slow.pics
----------------
collection={slowpics.collection_name} auto={slowpics.auto_upload|bool}
status={slowpics.status}
{upload_bar}

[WARNINGS]
• general — {warning.count} occurrence(s): {warning.labels}

[SUMMARY]
• Clips: {clips.count}
  Window lead {window.ignore_lead_seconds:.2f}s  trail {window.ignore_trail_seconds:.2f}s
  Step {analysis.step}  Downscale {analysis.downscale_height}px
• Align
  audio {audio_alignment.enabled|bool}  offset {audio_alignment.offsets_sec:+.3f}s
  file {audio_alignment.offsets_filename.e}
• Plan
  dark {analysis.counts.dark}  bright {analysis.counts.bright}  motion {analysis.counts.motion}
  random {analysis.counts.random}  user {analysis.counts.user}  sep {analysis.screen_separation_sec:.1f}s
• Canvas
  single_res {render.single_res|tallest}px  upscale {render.upscale|bool}
  crop mod{render.mod_crop}  pad {render.center_pad|bool}
• Tonemap
  curve {tonemap.tone_curve}  target {tonemap.target_nits:.0f}nits  dst_min {tonemap.dst_min_nits:.2f}  knee {tonemap.knee_offset:.2f}
  dpd {tonemap.dpd|bool} ({tonemap.dpd_preset})  cutoff {tonemap.dpd_black_cutoff:.3f}  smooth {tonemap.smoothing_period:.1f}  scene {tonemap.scene_threshold_low:.2f}→{tonemap.scene_threshold_high:.2f}  pct {tonemap.percentile:.3f}
  contrast {tonemap.contrast_recovery:.3f}  meta {tonemap.metadata_label}  dovi {tonemap.use_dovi_label}  lut {tonemap.visualize_lut|bool}  clip {tonemap.show_clipping|bool}  gamma {tonemap.post_gamma:.2f}*  Δ={verify.delta.max}
• Output
  dir {render.out_dir.e}  compression {render.compression}
• Cache
  file {cache.file}  status {cache.status}
• Comparison
  {comparison.viewer_mode}  {comparison.viewer_source}
• Output frames ({analysis.output_frame_count})
  {emit_json_tail?preview {analysis.output_frames_preview}  (full list in JSON{verbose?' and above':''}):{analysis.output_frames_full|summary_wrap}}

[✓] slow.pics: verifying & saving shortcut
slow.pics URL: {slowpics_url} (copied to clipboard)
Shortcut: {shortcut_path_str or "(disabled)"}
Cleaned up screenshots after upload
  {resolved_created_path}

[✓] HTML report: {report_path}

{json_tail}
```

Notes for readers trying to reproduce the transcript above:

- The rule line under each subtitle is **dynamic**: the renderer uses `-` (no-color/ascii) or `─` (unicode) and sizes it based on subtitle width and the widest line in that block. See §2.3 “Group subtitles”.
- Several lines/sections are conditional in `cli_layout.v1.json` (TMDB line, audio block, overrides block, cache progress message, etc.); the transcript above intentionally shows a “busy” happy-path run where those are populated.
- Progress bars (`{analyze_bar}`, `{render_bar}`, `{render_clip_bar}`, `{upload_bar}`) are Rich live-rendered output; exact on-screen appearance depends on terminal width/capabilities and `[cli.progress].style`.

### Failure transcript template — cache-only missing snapshot

Command:

```bash
frame-compare --from-cache-only
```

Error message string (source: `src/frame_compare/orchestration/phases/setup.py`):

```text
[red]Cached run unavailable.[/red] Run without --from-cache-only or delete {result_snapshot_path}.
```

### `doctor` output (human-readable)

Command:

```bash
frame-compare doctor
```

Exact output row format (source: `src/frame_compare/doctor.py`):

```text
{ICON} {Label padded} — {message}
Notes:
  - {note}
```

Where ICON is one of: ✅ ❌ ⚠️

## 2.7 How to capture *exact* transcripts on a supported legacy environment (recommended)

This audit could not run legacy end-to-end, but you can capture canonical transcripts elsewhere (Windows/Linux with VapourSynth + plugins):

1. Capture `--help` outputs (verbatim):
   - `frame-compare --help`
   - `frame-compare doctor --help`
   - `frame-compare wizard --help`
   - `frame-compare preset --help`
2. Capture a stable “happy path” run:
   - Prefer `--no-color` to minimize terminal variance.
   - Use a fixed terminal width if possible (so wrapping matches across machines).
3. Capture a stable “failure path” run:
   - `frame-compare --from-cache-only` in a workspace where `<screens_dir>/.frame_compare.run.json` does not exist.
4. Paste the raw transcripts into §2.6 without reformatting.

Notes:

- The dashboard output is driven by `cli_layout.v1.json`, so most “lines” are stable, but wrapping can still vary by terminal width.
- `FRAME_COMPARE_DOVI_DEBUG=1` adds extra stderr output; keep it off when capturing baseline transcripts.

---

# 3) Implementation Map (code pointers)

## 3.1 Overlay rendering / compositing (end-to-end call path)

Primary call path:

1. CLI run enters workflow: `frame_compare.py:run_cli` → `src/frame_compare/runner.py:run`
2. Pipeline render phase: `src/frame_compare/orchestration/phases/render.py:RenderPhase.execute`
3. Screenshot orchestration: `src/frame_compare/screenshot/orchestrator.py:generate_screenshots`
4. Per-frame overlay text composition:
   - base (tonemap overlay template): `src/frame_compare/vs/tonemap.py:process_clip_for_screenshot` → `overlay_text`
   - final overlay block: `src/frame_compare/render/overlay.py:compose_overlay_text`
5. Overlay application to pixels:
   - VapourSynth path: `src/frame_compare/screenshot/render.py:apply_frame_info_overlay` then `apply_overlay_text`
   - FFmpeg path: `src/frame_compare/screenshot/render.py:save_frame_with_ffmpeg` (`drawtext` filters)

Source-of-truth constants/config:

- ASS styles: `src/frame_compare/render/overlay.py` (`FRAME_INFO_STYLE`, `OVERLAY_STYLE`)
- FFmpeg drawtext coordinates & styling: `src/frame_compare/screenshot/render.py` (`save_frame_with_ffmpeg`)
- Overlay text mode + enable flags: `src/datatypes.py:ColorConfig`, `src/data/config.toml.template`
- Diagnostic metrics gating: `src/datatypes.py:DiagnosticsConfig`, `src/frame_compare/orchestration/phases/render.py`

## 3.2 CLI printing / progress / error formatting

Entrypoints and wiring:

- `pyproject.toml` → `frame-compare` → `frame_compare.py:main` → `src/frame_compare/cli_entry.py:main`

CLI rendering:

- Output manager: `src/frame_compare/cli_runtime.py:CliOutputManager` / `NullCliOutputManager`
- Layout renderer: `src/frame_compare/layout/renderer.py:CliLayoutRenderer`
- Layout spec + theme: `cli_layout.v1.json`

Progress:

- Progress style flag: `src/frame_compare/orchestration/phases/setup.py` sets `progress_style` from `[cli.progress].style`
- Progress creation: `src/frame_compare/layout/renderer.py:create_progress`

Errors:

- Typed error: `src/frame_compare/cli_runtime.py:CLIAppError` with `rich_message`
- Click catches: `src/frame_compare/cli_entry.py` prints `exc.rich_message` (Rich markup)

---

# 4) Knobs / Config (overlay + CLI formatting)

## 4.1 CLI flags affecting formatting

Source: `src/frame_compare/cli_entry.py` and README “CLI Reference”.

- `--quiet` / `--verbose`
- `--no-color` (plus env `NO_COLOR`)
- `--json-pretty`
- `--from-cache-only`, `--show-partial`, `--show-missing/--hide-missing`
- `--diagnostic-frame-metrics` / `--no-diagnostic-frame-metrics` (affects overlay *content*)

Tonemap override flags (affect overlay base line + HDR processing):

- `--tm-preset`, `--tm-curve`, `--tm-target`, `--tm-dst-min`, `--tm-knee`, etc.

## 4.2 Environment variables affecting formatting

- `NO_COLOR=1` disables ANSI colors (in addition to `--no-color`)
- `FRAME_COMPARE_FORCE_256_COLOR=1` forces 256-color ANSI mapping
- `FRAME_COMPARE_DOVI_DEBUG=1` emits `[DOVI_DEBUG] ...` JSON lines to **stderr**
- Terminal capability env vars (affect 16-color vs 256-color styling heuristics when not forced):
  - `COLORTERM` (checks for `truecolor` / `24bit`)
  - `TERM` (checks for `256color` / `truecolor`)
  - Windows heuristics: `WT_SESSION`, `TERM_PROGRAM` (used to decide modern-terminal behavior)

Workspace/config discovery env vars (affect run behavior, indirectly output):

- `FRAME_COMPARE_ROOT`
- `FRAME_COMPARE_CONFIG`
- `FRAME_COMPARE_TEMPLATE_PATH`
- `FRAME_COMPARE_NO_WIZARD`

Overlay debug env vars:

- `FRAME_COMPARE_DEBUG_GEOMETRY=1` logs geometry planning diagnostics
- `FRAME_COMPARE_LOG_OVERLAY_RANGE=1` logs range normalization stages

## 4.3 Config values affecting overlay + CLI formatting

Overlay-related (from `src/data/config.toml.template`):

- `[color].overlay_enabled` (default `true`)
- `[color].overlay_text_template` (default is the “Tonemapping Algorithm: …” string)
- `[color].overlay_mode` (`"minimal"` or `"diagnostic"`)
- `[diagnostics].per_frame_nits` (only affects diagnostic overlay content)
- `[screenshots].add_frame_info` (frame info overlay on/off)
- `[screenshots].use_ffmpeg` (switches FFmpeg drawtext vs VapourSynth ASS subtitle)

CLI-related:

- `[cli].emit_json_tail` (default `true`)
- `[cli.progress].style` (`"fill"` or `"dot"`)

## 4.4 Default values + precedence rules (high-level)

Workspace root discovery (from `README.md` + `src/frame_compare/preflight.py`):

1. `--root`
2. `$FRAME_COMPARE_ROOT`
3. nearest ancestor containing one of: `pyproject.toml`, `.git`, `comparison_videos`
4. current working directory

Tonemap override precedence (from `src/frame_compare/orchestration/setup.py`):

- CLI `--tm-*` flags are applied as overrides onto the loaded config before the run.

Overlay/CLI mode precedence:

- CLI flags affect runtime flags (quiet/verbose/no_color/json_pretty/show_missing/etc.)
- Config controls overlay enable/mode/template and CLI progress style / JSON tail emission.

---

# 5) Dependencies

## 5.1 CLI libraries (legacy)

From `pyproject.toml`:

- `click` (command parsing)
- `rich` (console rendering + progress)
- `tqdm` (present as a dependency; main dashboard uses Rich progress)
- `colorama` (Windows console compatibility; optional)

## 5.2 Overlay/render libraries (legacy)

Python deps and external tooling:

- `vapoursynth` (primary renderer path)
  - Requires plugins/namespaces:
    - `core.sub.Subtitle` (ASS-style subtitles)
    - `core.text.Text` (fallback)
    - `core.libplacebo.Tonemap` or `core.placebo.Tonemap` (HDR tonemapping)
- VapourSynth PNG writer path expects `core.fpng.Write` (fpng plugin) in `save_frame_with_fpng`.
- `ffmpeg` binary (FFmpeg writer and fallback renderer, and audio tooling)
- `ffprobe` binary (metadata probing; doctor checks for it alongside ffmpeg)
- FFmpeg filter: `drawtext`

## 5.3 Font assets + licensing

- No `.ttf`/`.otf` fonts are bundled in this legacy repo (excluding dependency caches like `.uv_cache/**`).
- VapourSynth ASS style requests `sans-serif`; FFmpeg drawtext uses default font discovery.
- Font licensing is therefore **host-system-dependent** (document in FC2 if you decide to bundle a font for determinism).

---

# 6) Porting Notes to Frame Compare 2.0 (verified against FC2 repo)

Verification source (FC2 repo on disk):

- FC2 `pyproject.toml` includes: `typer`, `rich`, `structlog`, `pillow`, `pydantic`, etc.
- FC2 overlay implementation exists: `/Users/tristan/Software/frame-compare/src/frame_compare/render/overlay.py`
- FC2 overlay positioning helper exists: `/Users/tristan/Software/frame-compare/src/frame_compare/render/geometry.py`
- FC2 CLI entry exists: `/Users/tristan/Software/frame-compare/src/frame_compare/cli_entry.py`

## 6.0 Important: “overlay” means different things in legacy vs FC2

In legacy, “overlay” is **burn-in text rendered into the exported PNGs** (VapourSynth subtitles or FFmpeg drawtext).

In FC2, “overlay” appears in two contexts:

1. Screenshot burn-in overlay (Pillow text overlay): `/Users/tristan/Software/frame-compare/src/frame_compare/render/overlay.py`
2. HTML report UI overlays (“labels overlay”, CSS/UI chrome): `/Users/tristan/Software/frame-compare/src/frame_compare/services/report.py`

When porting, keep these separate:

- “screenshot overlay” (pixel-level burn-in, the legacy feature)
- “report viewer overlay” (DOM/CSS overlay, a different feature)

## 6.1 Legacy overlay features → FC2 portability

- **Overlay text composition (minimal/diagnostic line ordering)** — *Directly portable with existing FC2 libs* (pure string composition). Implement legacy line order/content on top of FC2’s `OverlayConfig`.
- **Overlay rendering (white text + black outline, no background box)** — *Directly portable with existing FC2 libs* (Pillow is already present), but FC2’s current burn-in overlay differs:
  - FC2 draws a semi-transparent background rectangle (`fill=(0, 0, 0, 180)`) and uses a 1px shadow + white foreground.
  - Legacy uses no box (FFmpeg path) and a 2px outline (ASS and drawtext border).
  - To match legacy, FC2 likely needs an “outline/stroke” rendering path (Pillow supports stroke on some versions, or you can emulate with multiple offset draws) and a switch to disable the rectangle fill.
- **Frame info overlay (frame count + picture type + label + optional selection)** — *Needs new FC2 implementation* (no new external dependency). FC2 overlay currently formats label/frame/resolution; legacy has a separate frame-info block and includes picture type.
- **Backend-specific coordinates (VS margins vs FFmpeg x/y)** — *Directly portable with existing FC2 libs* if FC2 supports per-backend placement; otherwise needs small refactor to allow `y=10` vs `y=80` dual-block placement.
- **Per-frame “Measurement … nits” line gated by `[diagnostics].per_frame_nits` and `overlay_mode=diagnostic`** — *Directly portable with existing FC2 libs* (FC2 already has diagnostics config; compute line from selection score and include only when enabled).
- **DoVi/HDR/range diagnostic lines** — *Directly portable with existing FC2 libs* if FC2 already has equivalent metadata extraction; otherwise *needs new code* but no special libraries beyond whatever is already used to read frame props / HDR metadata.

## 6.2 Legacy CLI features → FC2 portability

- **Data-driven dashboard layout (`cli_layout.v1.json`)** — *Needs new internal module*, but **no new dependency** (FC2 already uses Rich). Port options:
  - bring over legacy layout engine + renderer concept, or
  - re-implement a comparable dashboard directly in Rich, using legacy’s section order/lines as the UX spec.
- **Legacy section ordering / content (“At-a-Glance”, “[DISCOVER]…”, etc.)** — *Directly portable with existing FC2 libs* (Rich) once you choose how to render sections.
- **`--no-color` + `NO_COLOR` semantics** — *Directly portable*; FC2 already has `--no-color`.
- **JSON tail appended as the final output block** — *Directly portable*, but FC2 currently uses `--json` for a different JSON envelope; decide whether to keep both (legacy tail vs FC2 structured result JSON).
