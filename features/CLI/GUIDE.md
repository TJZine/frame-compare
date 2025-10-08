## General Task
 - implement these overlay updates
## Scope (presentation only)
* Do **not** change frame selection, rendering, or file outputs.
* Only affect overlay text content based on a config switch.
* Respect all existing behavior in **minimal** mode.

---

## Config

Add a mode switch (default should preserve current behavior):

```toml
[color]
overlay_enabled = true
overlay_mode = "minimal"      # "minimal" (today’s overlay) or "diagnostic"
```

* When `overlay_enabled=false`, render nothing (unchanged).
* When `overlay_mode="minimal"`, render **exactly** today’s overlay—**no** extra lines.
* When `overlay_mode="diagnostic"`, render **today’s overlay verbatim** + the extra lines specified below.

---

## Behavior by mode

### minimal (unchanged)

* Print **exactly** the current overlay (title and any existing fields).
* If the current overlay includes a tonemap summary line, keep it **once**.

### diagnostic (extended)

* First, print **the same minimal overlay block** *without modification*.
* Then append **these lines** (each on its own line, in this order):

1. **Resolution / Scaling**

   * If resized:
     `1920 × 1080 → 3840 × 2160  (original → target)`
     (Use `src_w × src_h` → `dst_w × dst_h`; `×` character, not `x`.)
   * If not resized:
     `3840 × 2160  (native)`

2. **HDR Mastering Display Luminance (MDL)**

   * `MDL: min: <min_nits> cd/m², max: <max_nits> cd/m²`
   * If absent: `MDL: Insufficient data`

3. **Per-frame Measurement**

   * `Measurement MAX/AVG: <max_nits>nits / <avg_nits>nits`
   * If unavailable: `Measurement: Insufficient data`

4. **Frame Selection Type**

   * `Frame Selection Type: <Dark|Bright|Motion|User|Random>`
   * If unknown: `Frame Selection Type: (unknown)` (or omit consistently)

> **Do not** append any extra tonemap/settings line in diagnostic; the overlay must contain **at most one** tonemap summary (the one already present in minimal, if any).


## Data sources (expected)

* **Resolution/Scale:**

  * `original` = decoded frame dims before canvas/upscale/pad.
  * `target`   = final canvas/output dims used for the screenshot.
* **MDL:** ST.2086 mastering metadata (`minLuminance`, `maxLuminance`), reported in **cd/m²** (nits). If missing, print “Insufficient data”.
* **Measurement:** display-referred luminance for the *current* frame (post-pipeline, same stage used for verification/tonemap checks). If you don’t have a cheap path, print “Insufficient data”.
* **Frame Selection Type:** the category that chose this frame (Dark/Bright/Motion/User/Random) from the selection pipeline.


## Formatting rules

* Use the **multiplication symbol** `×` (U+00D7) between width and height.
* **Arrow** between original and target: `→` (U+2192).
* **Units:** `cd/m²` (fallback `cd/m2` if font lacks superscript).
* **Rounding:**

  * MDL min/max: if `< 1.0`, show up to **4 decimals** (e.g., `0.0001`); otherwise **1 decimal** (e.g., `1000.0`).
  * Measurement: `MAX` → **integer**; `AVG` → **one decimal** (e.g., `192nits / 4.1nits`).
* **Wording/Order:** exact strings above; single space around arrows and inside parentheses.

## Guardrails

* **No duplicates:** if minimal already prints a resolution line in a different format, prefer **one standardized** resolution line (as above) and suppress the duplicate **only in diagnostic mode**.
* **Missing data:** always print “Insufficient data” rather than `0` or `N/A`.
* **Performance:** do not add heavy reprocessing; if measurement isn’t readily available, use the wording fallback.

## Acceptance criteria

* With `overlay_mode="minimal"`: output is **bit-for-bit identical** to today’s overlay (title unchanged; nothing extra).
* With `overlay_mode="diagnostic"`: the minimal overlay prints first (unchanged), followed by **exactly four** added lines in the order listed.
* **Resolution** line shows `original → target` or `(native)` correctly.
* **MDL** and **Measurement** lines follow the formatting/rounding rules or show “Insufficient data”.
* **Frame Selection Type** prints one of the five categories (or the agreed fallback).
* There is **no duplication** of tonemap settings; if minimal contains one tonemap line, the final overlay still has **one** such line.


