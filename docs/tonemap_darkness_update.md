
# Codex Task: HDR→SDR Tonemap Shadow-Preservation + Operator Controls (VapourSynth + libplacebo)

**Owner:** frame-compare  
**Priority:** High (regression: near‑black crush with limited‑range SDR PNGs)  
**Target version:** next minor (e.g., `v0.x+1`)  
**Affected areas:** `vs_core.py`, `frame_compare.py` (CLI UX & overlays), `config_loader.py` / `datatypes.py` (schema), `config.toml` / template, docs (`hdr_tonemap_overview.md`, `config_reference.md`, `README.md`), tests, CI

---

## 0) Objective

Implement and expose *robust, standards‑aligned* tonemapping controls to **preserve shadow detail** while keeping highlights intact when converting **HDR (PQ/BT.2020)** to **SDR (BT.709 limited)** *stills* using libplacebo’s `Tonemap`. This includes:

- Tunable **toe** via `dst_min_nits`, `target_nits`, **BT.2390 knee** parameter, and an **optional post‑tonemap gamma lift** (limited‑safe).
- **Dynamic Peak Detection (DPD)** with a selectable preset matching libplacebo’s conservative “HQ” behavior.
- Clean **config + CLI** ergonomics, overlay visibility, and reproducible defaults suitable for 2024–2025 pipelines.

---

## 1) Scope (what will change)

1. **libplacebo call surface** in `vs_core.py`:
   - Add support for `tone_mapping_param` (BT.2390 knee offset) and `peak_detection_preset` (DPD presets), and optional `black_cutoff`.
   - Ensure `dst_min` (black floor) and `dst_max`/`target_nits` are wired from config.
   - Keep `gamut_mapping=perceptual` default; keep `use_dovi=True` as today unless disabled by user.

2. **Post‑tonemap gamma lift** (limited‑aware):
   - Implement an opt‑in **tiny gamma lift** stage after tonemap and before overlays → geometry → dithering/export.
   - Two implementations allowed (choose one):
     - **VapourSynth** `std.Levels(gamma=...)` with `(min_in,max_in,min_out,max_out)=(16,235,16,235)`
     - **libplacebo color adjustment** gamma (if we keep everything in placebo), but must remain *very small* and disabled by default.
   - The VS `Levels` variant is safer/explicit for our limited‑range stills.

3. **Configuration schema** (`[color]` section, TOML):
   - New keys (with sensible defaults):
     ```toml
     [color]
     # Existing
     enable_tonemap = true
     preset = "custom"                # "reference" | "filmic" | "contrast" | "bt2390_spec" | "bt2446a" | "spline" | "custom"
     tone_curve = "bt.2390"           # When preset="custom"
     dynamic_peak_detection = true
     target_nits = 100.0              # SDR reference white; 110.0 optional
     dst_min_nits = 0.18              # Toe lift to avoid near‑black crush

     # New
     knee_offset = 0.50               # -> libplacebo tone_mapping_param (BT.2390 spec value)
     dpd_preset = "high_quality"      # "off" | "fast" | "balanced" | "high_quality"
     dpd_black_cutoff = 0.01          # Optional PQ black cutoff fraction (0.0–0.05); set 0.01 default
     post_gamma_enable = false
     post_gamma = 0.95                # Gentle lift (0.90–1.05); applied as VS Levels in limited
     ```
- **Preset map** (see implementation §3): “reference” = `bt.2390/100nits/dpd=on` (smoothing 45f, percentile `99.995`, contrast `0.30`); “filmic” = `bt.2446a/100nits/dpd=on`; “contrast” = `bt.2390/110nits/dpd=on/contrast=0.45`; “bt2390_spec” = `bt.2390/100nits/dpd=on` with neutral cutoff; “spline” = `spline/105nits/dpd=on`; “bright_lift” = `bt.2390/130nits/dpd=on`; “highlight_guard” = `bt.2390/90nits/dpd=on`.

4. **CLI & overlays**:
   - Ensure current overlay text can display new fields: `{knee_offset}`, `{dpd_preset}`, `{dst_min_nits}`, `{target_nits}`.
   - Optional short CLI flags (non‑breaking): `--tm-preset`, `--tm-target`, `--tm-dst-min`, `--tm-curve`, `--tm-knee`, `--tm-dpd-preset`, `--tm-gamma` (behind “advanced” group). If we prefer config‑only, keep read‑only overlays but **add** a `preset` command that writes a TOML fragment to the workspace (we already have preset plumbing; see §2.2).
   - `cli_layout.*` should surface these in the `[COLOR]` block with consistent labeling.

5. **Tests & CI**:
   - Type‑checked Python 3.13 / Pyright clean.
   - Unit tests for config→kwargs wiring, value bounds, and stage ordering (tonemap → optional gamma → overlays → geometry → dither).
   - Golden image tests using synthetic clips (PQ ramps + low‑APL scenes) to assert near‑black code‑value preservation within a small delta.
   - GitHub Actions updated to run the new tests on Linux and Windows (VS headless).

6. **Docs**: Update `hdr_tonemap_overview.md`, `config_reference.md`, `README.md` with rationale, defaults, and tuning advice.

> **Out of scope:** re‑grading aesthetics, full color‑managed screenshot export, or viewer colorimetry changes.

---

## 2) Implementation details

### 2.1 `vs_core.py` — libplacebo Tonemap call

- In `_tonemap_with_retries(...)` add new kwargs and plumb from config:
  ```python
  kwargs = dict(
      dst_csp=0, dst_prim=1, dst_max=float(target_nits), dst_min=float(dst_min),
      dynamic_peak_detection=int(dpd),
      # NEW:
      peak_detection_preset=str(cfg.dpd_preset) if dpd else "off",
      black_cutoff=float(cfg.dpd_black_cutoff) if dpd else 0.0,
      tone_mapping_function_s=tone_curve,
      tone_mapping_param=float(cfg.knee_offset) if tone_curve.startswith("bt.2390") else 0.0,
      smoothing_period=2.0,
      scene_threshold_low=0.15, scene_threshold_high=0.30,
      gamut_mapping=1, use_dovi=True, log_level=2,
  )
  ```
  - Guard for libplacebo versions lacking `peak_detection_preset` or `tone_mapping_param` by feature‑probing: `hasattr(placebo.Tonemap, "__signature__")` or try/except with a downgraded fallback and a single WARN.

- After the Tonemap node returns, insert **optional** gamma lift when `post_gamma_enable`:
  ```python
  if getattr(cfg, "post_gamma_enable", False):
      gamma = float(getattr(cfg, "post_gamma", 1.0))
      # Limited‑safe tiny lift:
      node = core.std.Levels(node, gamma=gamma, min_in=16, max_in=235, min_out=16, max_out=235)
  ```

- Ensure our stage order for screenshots remains:
  `HDR normalize → Tonemap → (opt) gamma → overlays → geometry → dither/export`.
  Add a one‑line DEBUG to the color log describing the exact kwargs and the gamma stage decision.

### 2.2 Preset resolution

- **Bug:** `_resolve_tonemap_settings` references `_TONEMAP_PRESETS` but no dict exists. Implement:
  ```python
  _TONEMAP_PRESETS: dict[str, dict[str, object]] = {
      "reference":     {"tone_curve": "bt.2390", "target_nits": 100.0, "dynamic_peak_detection": True, "knee_offset": 0.50, "dst_min_nits": 0.18},
      "bt2390_spec":   {"tone_curve": "bt.2390", "target_nits": 100.0, "dynamic_peak_detection": True, "knee_offset": 0.50, "dst_min_nits": 0.18},
      "filmic":        {"tone_curve": "bt.2446a", "target_nits": 100.0, "dynamic_peak_detection": True, "dst_min_nits": 0.18},
      "spline":        {"tone_curve": "spline",  "target_nits": 100.0, "dynamic_peak_detection": True, "dst_min_nits": 0.18},
     "contrast":      {"tone_curve": "bt.2390", "target_nits": 110.0, "dynamic_peak_detection": True,  "dst_min_nits": 0.15},
  }
  ```
- Extend `_resolve_tonemap_settings` to also adopt `knee_offset`, `dst_min_nits`, and later `dpd_preset` if not explicitly provided by user. Return payload expanded or set them in `resolve_effective_tonemap`.

### 2.3 Config schema & loader

- In `datatypes.py` / `config_loader.py` add new fields with types and bounds:
  ```python
  knee_offset: float = 0.50          # 0.0–1.0 for BT.2390
  dpd_preset: str = "high_quality"   # enum: {"off","fast","balanced","high_quality"}
  dpd_black_cutoff: float = 0.01     # 0.0–0.05
  post_gamma_enable: bool = False
  post_gamma: float = 1.00           # clamp 0.90–1.10
  ```
- Validate ranges; coerce `dpd_preset="off"` when `dynamic_peak_detection=false`.

- **Templates:** Update `config.toml` and `config_template.py` to include the keys + comments and adjust defaults:
  - `target_nits = 100.0` (or 110.0 if we keep the current default; prefer 100 for reference)
  - `dst_min_nits = 0.18` (current `0.3` is a bit milky; leave as project default only if visually approved).

### 2.4 CLI ergonomics

- If we already have a **TOML preset system** (`frame_compare.py` has `preset` I/O helpers), add/extend a subcommand:
  - `frame-compare preset tonemap reference|filmic|contrast|bt2390_spec|spline` → writes a TOML fragment under `.presets/color/tonemap/*.toml` and switches config to `preset="custom"` or updates `[color]` fields.
- If exposing direct flags, group them under an **Advanced Color** panel and ensure `cli_layout.v1.json` shows values in `[COLOR]` with clear labels (avoid duplication bugs noted in earlier CLI tasks).

### 2.5 Overlays, range, export

- Keep overlays **after** tonemap (and optional gamma), **before** geometry; ensure they act in **limited range**.
- Ensure final export dither keeps the 16–235 range stable (no auto expansion). Add an integration test to catch regressions.

---

## 3) Tests (Pytest)

> Use synthetic HDR patterns to assert toe preservation; no external footage required.

1. **Config→kwargs wiring** (`tests/test_color_config.py`)
   - Build a mock `cfg` with each field set and assert the resulting placebo kwargs match expectations (including `tone_mapping_param`, `peak_detection_preset`, `dst_min`, `dst_max`).

2. **Preset adoption** (`tests/test_tonemap_presets.py`)
   - With `preset="reference"` and nothing else provided, assert knee=0.5, curve=bt.2390, target=100, dpd on, `dst_min_nits=0.18`.
   - With user overrides present, assert “provided” keys win.

3. **Toe regression** (`tests/test_tonemap_toe.py`)
   - Generate a PQ near‑black ramp into BT.2020 → run through pipeline → convert to RGB24 limited.
   - Compute histogram in code values 16–24; assert **monotonic increase** and that code 17/18 retain >N counts (no collapse to pure 16). Parametrize over `dst_min_nits` in {0.10, 0.18, 0.25}.

4. **Gamma stage order** (`tests/test_gamma_stage.py`)
   - Enable `post_gamma_enable` and ensure overlays text color does not shift out of 16–235 by sampling overlay glyph pixels.

5. **CI headless** (`.github/workflows/ci.yml`)
   - Run Pyright, Ruff, Pytest.
   - Matrix: ubuntu‑latest & windows‑latest (mark VS tests as `-m vapoursynth` and skip when core not available; but run pure wiring tests universally).

---

## 4) Documentation

- **`hdr_tonemap_overview.md`**
  - Add a table: when to tune `dst_min_nits` vs `post_gamma`, and interplay with limited PNGs.
  - Document defaults (reference profile) and note “legacy” status of Möbius/Hable (still available via preset).

- **`config_reference.md`**
  - New keys + concise advice:
    - `knee_offset`: *BT.2390 spec is 0.50; larger increases shoulder, smaller increases micro‑contrast in mids.*
    - `dst_min_nits`: *0.18–0.25 uncrushes textured blacks for limited SDR stills; too high looks hazy.*
    - `dpd_preset`: *Use `high_quality` for stills; `off` for strict cross‑frame reproducibility.*
    - `post_gamma`: *Use sparingly (0.95–1.05). Prefer `dst_min_nits` first.*

- **`README.md`**
  - “Quick recipes” section with two presets:
    - **Reference SDR (BT.2390)** — `target_nits=100`, `dst_min_nits=0.18`, `dpd_preset="high_quality"`, `knee_offset=0.5`.
    - **BT.2446A Filmic** — for well‑mastered content; keep a small `dst_min_nits`.

- **Changelog** (`CHANGELOG.md`)
  - Add “Added: BT.2390 knee_offset, DPD presets, limited‑safe gamma lift; Fixed: missing `_TONEMAP_PRESETS` dict; Improved: overlay shows tonemap parameters.”

---

## 5) Acceptance criteria (DoD)

- ✅ `vs_core` passes all new kwargs (or logs a single WARN and hard‑fallbacks when running against older libplacebo).
- ✅ With **`[color] preset="reference"`**, the runtime log prints: `curve=bt.2390 knee=0.50 target=100 dst_min=0.18 dpd=high_quality`.
- ✅ Near‑black histogram test proves **no crush** for typical still exports; overlays remain 16–235.
- ✅ Pyright (strict) is clean; CI green on Linux + Windows.
- ✅ Docs updated; sample TOML fragment works out of the box.
- ✅ No regressions to SDR‑input path (tonemap remains bypassed).

---

## 6) Risks & mitigations (critical self‑review)

- **Libplacebo API drift**: Some builds may lack `peak_detection_preset`/`black_cutoff`/`tone_mapping_param`.
  - *Mitigation*: feature‑probe and gracefully degrade with a single WARN; keep behavior equivalent to current pipeline.

- **Double‑gamma or hazy blacks** if users combine high `dst_min_nits` with `post_gamma`.
  - *Mitigation*: docs recommend **tuning `dst_min_nits` first**, keep `post_gamma_enable=false` by default, clamp ranges.

- **Preset surprise**: Users on “contrast” (Mobius/120 nits) may like the old punchy look.
  - *Mitigation*: preserve legacy preset, mark as “legacy look,” document trade‑offs.

- **Overlay range contamination**: If overlay happens in full‑range, stills may expand unexpectedly.
  - *Mitigation*: keep overlay path limited‑aware; add test sampling overlay glyph pixels to assert 16–235.

---

## 7) Implementation checklist (step‑by‑step)

1. **Schema**: Add new fields in `datatypes.py` → parse in `config_loader.py` with bounds and defaults.
2. **Presets**: Implement `_TONEMAP_PRESETS` in `vs_core.py`; extend `_resolve_tonemap_settings` to adopt `knee_offset`, `dst_min_nits`, `dpd_preset`.
3. **Tonemap call**: Add new kwargs (`tone_mapping_param`, `peak_detection_preset`, `black_cutoff`) with feature‑probe fallback.
4. **Gamma stage**: Implement optional `std.Levels(gamma=...)` limited‑safe block.
5. **Overlay template**: Add tokens and ensure formatting won’t crash if a token is missing (fallback to blank).
6. **CLI/UX**: Option A: presets subcommand; Option B: advanced flags. Update `cli_layout.v1.json` labels.
7. **Tests**: Add new test modules; add markers for VS‑dependent tests; wire into CI.
8. **Docs**: Update the three docs; insert examples; regenerate any reference screenshots if we keep them under version control.
9. **CHANGELOG**: Write entries; bump version in `pyproject.toml`.
10. **Smoke test**: Run on 2–3 HDR samples + 1 SDR sample; confirm overlays and histograms.

---

## 8) TOML fragments (drop‑in)

```toml
[color]
preset = "reference"
tone_curve = "bt.2390"
knee_offset = 0.50
target_nits = 100.0
dst_min_nits = 0.18
dynamic_peak_detection = true
dpd_preset = "high_quality"
dpd_black_cutoff = 0.01
post_gamma_enable = false
post_gamma = 0.95
overlay_text_template = "{tone_curve} knee={knee_offset:.2f} dpd={dpd_preset} dst={target_nits:g} nits dst_min={dst_min_nits:g}"
```
```toml
[color]
preset = "filmic"     # Alternative
tone_curve = "bt.2446a"
target_nits = 100.0
dst_min_nits = 0.18
dynamic_peak_detection = true
dpd_preset = "high_quality"
post_gamma_enable = false
```
```toml
[color]
preset = "contrast"
tone_curve = "bt.2390"
target_nits = 110.0
dst_min_nits = 0.15
dynamic_peak_detection = true
dpd_preset = "high_quality"
dpd_black_cutoff = 0.008
smoothing_period = 30.0
scene_threshold_low = 0.8
scene_threshold_high = 2.2
percentile = 99.99
contrast_recovery = 0.45
post_gamma_enable = false
```

---

### Notes for maintainers
- Keep `dst_min_nits` default conservative (0.18) to avoid near-black crush; raising beyond ~0.25 can introduce haze.
- Prefer **100 nits** reference unless a specific preset aims to brighten (`bright_lift`) or dim (`highlight_guard`) the output.
- If we later add “export full‑range PNG” as an option, revisit presets to ensure range expansion pairs well with the chosen tone curve.
