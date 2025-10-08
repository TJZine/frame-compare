### Goals

1. Improve readability by **coloring values semantically** and **dimming glue text**.
2. Add **rule-based highlights** (thresholds, anomalies, booleans) driven by the JSON spec—no hardcoded colors in code.
3. Keep compatibility with `--no-color`, narrow terminals, and your current output order/strings.

---

## A) Palette & roles (update the spec)

Expand `theme.colors` to include phase accents + value semantics:

```json
"theme": {
  "colors": {
    "header": "cyan.bold",
    "accent": "blue.bright",
    "accent_prepare": "blue",
    "accent_analyze": "purple.bright",
    "accent_render": "magenta.bright",
    "accent_publish": "green.bright",
    "value": "white.bright",
    "unit": "grey.dim",
    "key": "blue",
    "bool_true": "green",
    "bool_false": "red",
    "number_ok": "green",
    "number_warn": "yellow",
    "number_bad": "red",
    "path": "grey.dim",
    "success": "green",
    "warn": "yellow",
    "error": "red",
    "dim": "grey.dim"
  }
}
```

> Keep 16-color fallbacks as before; if unsupported, the renderer must strip colors gracefully.

---

## B) Inline style spans (tiny DSL)

Teach the renderer to parse **style spans** in templates:

* `[[role]]text[[/]]` → wrap `text` with the ANSI for `role` (e.g., `value`, `unit`, `key`).
* You can nest spans (inner takes precedence).
* When `--no-color`, spans render as plain text.

**Examples inside templates:**

* `step=[[value]]{analysis.step}[[/]]  downscale=[[value]]{analysis.downscale_height}[[/]][[unit]]px[[/]]`
* `writer=[[key]]writer[[/]]=[[value]]{render.writer}[[/]]`

---

## C) Rule-based highlights

Add a new `highlights` block to the spec; renderer applies them **after** templating:

```json
"highlights": [
  { "when": "isbool", "path": "audio_alignment.enabled", "true_role": "bool_true", "false_role": "bool_false" },
  { "when": "gt", "path": "analysis.counts.motion", "value": 0, "role": "accent_analyze" },
  { "when": "lt", "path": "render.fps", "value": 1.0, "role": "number_warn" },
  { "when": "abs_gt", "path": "audio_alignment.offsets_sec", "value": 1.0, "role": "number_warn" },
  { "when": "gt", "path": "verify.delta.max", "value": "{tonemap.verify_luma_threshold}", "role": "number_bad" }
]
```

* Each rule can target a specific **value occurrence** in a line by tokenizing `{path}` placeholders, or you can expose **named tokens** in context (e.g., `verify.delta.max`).
* On a match, color **just the formatted value**, not the whole line.

---

## D) Phase accents by section

Apply section-specific accent roles:

* `[DISCOVER]` / banner: `header`
* `[PREPARE]`: `accent_prepare`
* `[ANALYZE]`: `accent_analyze`
* `[RENDER]`: `accent_render`
* `[PUBLISH]`: `accent_publish`

Keep body text neutral; only **keys** and **values** get color, **units** stay dim.

---

## E) Concrete edits to your current templates

1. **At-a-Glance lines** (make numbers pop, dim units):

```
Clips=[[value]]{clips.count}[[/]] • Step=[[value]]{analysis.step}[[/]] • Downscale=[[value]]{analysis.downscale_height}[[/]][[unit]]px[[/]] • Plan: Dark=[[value]]{analysis.counts.dark}[[/]] Bright=[[value]]{analysis.counts.bright}[[/]] Motion=[[value]]{analysis.counts.motion}[[/]]
Window: lead=[[value]]{window.ignore_lead_seconds:.2f}[[/]][[unit]]s[[/]] trail=[[value]]{window.ignore_trail_seconds:.2f}[[/]][[unit]]s[[/]] • Align(audio)=[[value]]{audio_alignment.enabled}[[/]] [[unit]]({audio_alignment.offsets_sec:+.3f}s)[[/]]
```

2. **Prepare → Trim** (align numbers, dim units):

```
• Ref:  lead=[[value]]{trims.ref.lead_f:>4}[[/]][[unit]]f[[/]] ([[value]]{trims.ref.lead_s:>5.2f}[[/]][[unit]]s[[/]])  trail=[[value]]{trims.ref.trail_f:>4}[[/]][[unit]]f[[/]] ([[value]]{trims.ref.trail_s:>5.2f}[[/]][[unit]]s[[/]])
```

3. **Analyze/Render headers**:

```
Config: step=[[value]]{analysis.step}[[/]]  method=[[value]]{analysis.motion_method}[[/]]  scenecut_q=[[value]]{analysis.motion_scenecut_quantile}[[/]]  diff_radius=[[value]]{analysis.motion_diff_radius}[[/]]  downscale=[[value]]{analysis.downscale_height}[[/]][[unit]]px[[/]]
Tonemap: curve=[[value]]{tonemap.tone_curve}[[/]]  dpd=[[value]]{tonemap.dynamic_peak_detection}[[/]]  target=[[value]]{tonemap.target_nits}[[/]][[unit]]nits[[/]]  verify_luma_thresh=[[value]]{tonemap.verify_luma_threshold}[[/]]
```

4. **Publish title preview** (Phase 2): color final title:

```
final="[[accent_publish]]{slowpics.title.final}[[/]]"
```

5. **Warnings table**: color the **type** (yellow) and **counts** (value):

```
• [[warn]]{warning.type}[[/]] — [[value]]{warning.count}[[/]] occurrence(s){warning.labels?`: ${warning.labels}`:''}
```

---

## F) Progress bars (subtle color)

* Bar itself uses the **section accent**; the **right label** dims units and highlights changing numbers:

  * Example: `[[value]]11.7[[/]] [[unit]]fps[[/]] | ETA [[value]]00:00:00[[/]] | elapsed [[value]]00:00:37[[/]]`

---

## G) Accessibility & contrast

* Add `theme.options.color_blind_safe=true` to switch the palette to **cyan/blue/purple/orange** (avoid red/green only).
* Never rely on color alone: keep **tokens** (`✓ ! ✗`) and keywords (`WARN`, `ERROR`) visible.

---

## H) Acceptance criteria

* Values that users tune (step, downscale, window seconds, tonemap target) render with the **`value`** color; units (`s`, `px`, `nits`) are **dim**.
* Booleans (e.g., `overlay.enabled`, `audio_alignment.enabled`) are **green “true”** / **red “false”**.
* Offsets show **sign-aware** coloring: positive red-tinted if `abs(offset) > 1s` (rule), neutral otherwise.
* Verify deltas beyond `verify_luma_threshold` are **red**; near (±10%) are **yellow**.
* Each phase badge uses its accent; body text stays neutral.
* `--no-color` renders clean ASCII; `--color-blind-safe` swaps red/green semantics to orange/blue.
* Wide vs narrow terminals render identically except for wrapping; colors never split tokens mid-word.

---

## I) Quick “beauty” tweaks (small wins)

* **Dim file paths** everywhere (`path` role).
* **Right-align** all numeric columns inside a block; color the digits, not the padding.
* **Space rhythm**: one blank line before `[ANALYZE]` and `[RENDER]`, none between their header and progress bar.

---