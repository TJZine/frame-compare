## Scope

Presentation-only. Do **not** change analysis, selection, rendering, upload logic, or flags. Apply purely to how multi-block sections render (primarily **[RENDER]**).

---

## Objectives

1. **Subheading emphasis**

   * In **[RENDER]**, render the subheadings **Writer**, **Canvas**, **Tonemap**, and **Overlay** with:

     * A subtle prefix glyph: `›` (ASCII fallback `>` when `--no-color`).
     * **Bold + accent color** (see Theme roles below).
     * A **thin divider** line directly underneath (cropped to content width).
   * Keep key/value lines that follow **unchanged** in content but with improved alignment/color (see below).

2. **Spacing & alignment**

   * Insert **one blank line** between each sub-block.
   * Within each sub-block, **right-align numeric columns** (frame counts, fps, px, nits, thresholds).
   * **Dim** units (`s`, `fps`, `px`, `nits`, `cd/m²`) and long paths; keep keys slightly accented; values bright.

3. **Degrade gracefully**

   * `--no-color`: show plain text (`>` prefix, ASCII `-----` rule).
   * **Narrow terminals** (`COLUMNS < 80`): omit the rule line but keep accent/bold and spacing consistent.

4. **Ensure all subheading sections are given the same treatment**

   * Apply the same subheading treatment to other multi-block sections (e.g., `[PREPARE]` blocks like Trim/Window/Overrides).
   * Add a small **legend** in `--verbose` explaining tokens and dimming.


## Theme roles (extend existing palette)

Add (or reuse if present):

* `accent_subhead` — color for subheading titles (e.g., blue or section-appropriate accent).
* `rule_dim` — dim color for the divider line.

*Example mapping (do not hardcode exact codes here; use your renderer’s color map):*

* `accent_subhead`: blue (or `accent_render` if already defined)
* `rule_dim`: grey.dim


## Rendering rules (exact behavior)

* Subheading line format:

  * Colored/bold: `[[accent_subhead]]› Writer[[/]]`
    (use the same for **Canvas**, **Tonemap**, **Overlay**)
* Divider line:

  * Next line prints a thin rule using box-drawing `─` repeated to match the **content width** of the widest key/value line in that sub-block (cap at terminal width).
  * In `--no-color` or non-UTF environments, replace with ASCII `-`.
* Body lines immediately follow (no extra blank line before the first body line).
* After each sub-block, insert **one blank line**.


## Alignment & micro-typography

* Numbers right-aligned **within each block’s column**; padding spaces are **not** colored.
* **Units** rendered dim; **paths** middle-ellipsized and dim.
* Keep existing right-label on progress bars (`{fps} fps | ETA | elapsed`) unchanged.


## Acceptance criteria

* In **[RENDER]**, each subheading (**Writer/Canvas/Tonemap/Overlay**) appears:

  * With `›` prefix, bold, and `accent_subhead` color.
  * With a one-line **divider** underneath (suppressed on narrow terminals).
  * Followed by its body lines, then a **single blank line** before the next sub-block.
* Keys/values retain current wording; only emphasis/alignment/spacing change.
* Units and paths are **dim**; numbers are aligned; no text is lost when truncating paths.
* `--no-color`: subheadings readable with `>` prefix and ASCII rule; spacing preserved.
* No changes to content outside **[RENDER]** (unless you opt to apply the same pattern to other multi-block sections later).
