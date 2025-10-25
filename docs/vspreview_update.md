# Codex Task — VSPreview Baseline Mode → CLI Panel (layout JSON) → Docs
**Subtask order (must implement in this sequence):**
1) **Preview changes** — baseline mode; show suggestion but **never apply** it in preview  
2) **CLI changes** — add a **Rich panel via layout JSON** above “At‑a‑Glance”; demote noise  
3) **Docs & missing‑dep hint** — installation & usage notes; friendly warning when preview is enabled but missing

> Keep instructions high‑level where repo details matter; do not over‑specify internals. Prefer existing helpers/conventions in the repository.

---

## Repo context you can rely on
- Config: `src/config_loader.py` → dataclasses in `src/datatypes.py`; defaults in `src/data/config.toml.template`.
- CLI rendering: **data‑driven** via `src/cli_layout.py` + a layout JSON (e.g., `cli_layout.v1.json`). Use existing roles/styles and section types (`line`, `box`, `list`, `group`). **Do not** hard‑code Rich logic; extend the layout JSON.
- Decisions/guardrails live in `docs/DECISIONS.md`.
- **Preview emission/launch entrypoint: `frame_compare.py`.** Implement preview changes there; do not rename without coordination.

---

## Phase 1 — Preview changes (Baseline mode)
**Goal:** VSPreview opens with both clips **untrimmed** (0‑frame), regardless of any auto suggestion. The suggestion is visible (overlay optional), but preview clips remain baseline.

### Requirements
- When `use_vspreview = true`, generate VSPreview script that:
  - Builds **reference** and **target** exactly as in screenshot path (tonemap/props/FPS parity).
  - Initializes `OFFSET_MAP[label] = 0` for all targets; **do not** pre‑apply suggestion in preview.
  - Keeps even/odd output pairing (0↔1, 2↔3, …). Ensure “Sync Outputs” still behaves correctly.
- Compute **suggested alignment** (frames + seconds) the same way as today; treat it as **guidance only**.
- **Overlay (ON by default)**: draw small text on outputs (config‑gated) showing:  
  `Suggested: +{S}f (~{S_secs}s) • Applied in preview: 0f (baseline) • (+ trims target / − pads reference)`
- **Persistence (unchanged)**: only the **manual** value is saved after preview (CLI prompt or “read OFFSET_MAP on exit” if present). Manual selection persists across reruns through the existing offsets file until removed.

### Config additions (names may be adapted to dataclasses)
```toml
[audio_alignment]
use_vspreview = true
vspreview_mode = "baseline"          # default; keep "seeded" as opt‑in if ever needed
show_suggested_in_preview = true     # overlay ON by default
```
> Do not change sign semantics or file formats.

### Tests
- **Unit:** when mode=`baseline`, emission sets `OFFSET_MAP=0` regardless of suggestion.
- **Unit:** overlay strings are composed from suggestion while applied offset remains 0f.
- **Integration:** with a non‑zero suggestion, preview shows baseline; setting a manual value persists it; rerun reuses manual unless offsets file is deleted.

---

## Phase 2 — CLI changes via **layout JSON** (Rich panel)
**Goal:** High‑visibility panel that tells users the preview mode and suggested value, without code‑level Rich calls. Implement by editing the **layout JSON** and plumbing values into the renderer context.

### What to add
1) **New section** (type: `box`) **above “At‑a‑Glance”** titled **“VSPreview Information”** (or a consistent variant).  
2) **Lines** (keep minimal, reusing existing **roles** like `header`, `key`, `value`, `warn`, `unit`, etc.):  
   - `Reference`: short label  
   - `Target`  : short label  
   - `Preview mode`: `baseline (0f applied to both clips)`  
   - `Suggested`: `+Nf (~Xs)` + dim note “guidance only — not applied in preview”
3) **Condition**: show this panel only when `audio_alignment.use_vspreview` is true (or equivalent flag in context).  
4) **Highlights** (optional): use existing highlight rules to style values when `abs(suggested_seconds)` exceeds a threshold (e.g., > 0.5 s). Use an existing warning role rather than inventing styles.
5) **Noise control**: default run hides third‑party chatter (plugin load lines, numpy subnormal warnings). Show them under `--verbose`/`--debug` only. Respect existing verbosity flags.

### Implementation notes (keep generic)
- Extend the **layout JSON** by inserting the new `box` section **before** the current “At‑a‑Glance” section. Keep structure consistent with existing sections.
- **Plumb values** into the renderer context (no hard‑coding): provide a small dict under a stable key (e.g., `vspreview.*`) with:
  - `mode` (string)
  - `suggested_frames` (int; may be signed)
  - `suggested_seconds` (float; round at display only)
  - `clips.ref.label`, `clips.tgt.label` (or whatever your context uses)
- Ensure the renderer’s JSON‑tail append includes non‑breaking fields:
  ```json
  {
    "vspreview_mode": "baseline",
    "suggested_frames": <int>,
    "suggested_seconds": <float with stable rounding>
  }
  ```
- Keep ANSI on TTYs; fall back to plain text for non‑TTY / `--no-color` as your renderer already does.

### Example (illustrative; adapt to your JSON schema)
```json
{
  "id": "vspreview_info",
  "type": "box",
  "title": "VSPreview Information",
  "when": "audio_alignment.use_vspreview",
  "lines": [
    "[[key]]Reference[[/]] [[value]]{clips.ref.label}[[/]]",
    "[[key]]Target[[/]]    [[value]]{clips.tgt.label}[[/]]",
    "[[key]]Preview mode[[/]] [[value]]{vspreview.mode}[[/]]",
    "[[key]]Suggested[[/]] [[value]]{vspreview.suggested_frames:+}[[/]][[unit]]f[[/]] (~[[value]]{vspreview.suggested_seconds:.3f}[[/]][[unit]]s[[/]])  [[dim]]guidance only — not applied in preview[[/]]"
  ]
}
```
```json
{
  "when": "abs_gt",
  "path": "vspreview.suggested_seconds",
  "value": 0.5,
  "role": "number_warn"
}
```

### Tests
- **Formatting/snapshot:** panel renders with stable structure and roles; ordering is above “At‑a‑Glance”.
- **TTY handling:** ANSI styles on terminals; plain on redirected output; `--no-color` honored.
- **Verbosity:** noise hidden by default; visible under `--verbose`/`--debug`.

---

## Phase 3 — Docs & missing‑dependency hint
**Goal:** Document how to install & run VSPreview; print a friendly warning when enabled but missing.

### Docs (README / pipeline)
- Add **Install & Run VSPreview**:
  - **Windows (recommend PySide6)**  
    ```powershell
    uv add vspreview PySide6
    ```
  - **Linux/macOS (recommend PyQt5)**  
    ```bash
    uv add vspreview PyQt5
    ```
- Optional dependency pattern (example; adapt to packaging):
  ```toml
  [project.optional-dependencies]
  preview = ["vspreview>=0.7", "PySide6>=6.6"]
  # or on Linux/macOS: ["vspreview>=0.7", "PyQt5>=5.15"]
  ```
- Ephemeral usage example:  
  `uv run --with .[preview] -- python -m vspreview path/to/vspreview_*.py`

### CLI missing‑dep hint
- When preview is enabled but `vspreview` or its Qt backend isn’t importable:
  - **Do not fail** the run; render a top‑level **warning panel** with copy‑paste commands (Windows vs Linux/macOS).
  - Show the exact command we would have run: `python -m vspreview path/to/vspreview_*.py`.
  - Append to JSON tail: `{"vspreview_offered": false, "reason": "vspreview-missing"}` (non‑breaking).

### Tests
- Docs lint (if present).  
- Warning panel appears only on missing deps; suppressed when present.  
- JSON tail fields appear only when applicable.

---

## Guardrails / Non‑Goals
- Maintain parity between preview and screenshot processing paths (tonemap/props/FPS).  
- Do **not** change sign semantics or persistence file formats without explicit approval.  
- Avoid renaming public flags or section IDs that are referenced by tests unless you update those tests.

---

## Rollback
- Config `vspreview_mode="seeded"` restores previous seed‑applied behavior.  
- Feature flags to disable overlay or the new panel without code removal.  
- Docs live in a standalone section; easy to revert.

---

## Risks & Mitigations
- **Operator habit (seeded previews):** make the panel/overlay explicit: “guidance only — not applied”. Keep `seeded` as opt‑in.
- **Formatting regressions:** use existing roles/section types; update snapshot tests accordingly.
- **Dependency noise:** move plugin/warning chatter behind verbosity flags; keep default output minimal.

---

## Acceptance Criteria (summary)
- Preview opens **baseline** (0f) even when suggestion ≠ 0; overlay shows suggestion + “Applied: 0f” (if enabled).  
- CLI renders a **“VSPreview Information”** **box above At‑a‑Glance**, showing reference/target, preview mode, and suggested alignment flagged as *guidance only*.  
- Only **manual** offsets are persisted; reruns reuse them until the offsets file is removed.  
- Docs include OS‑specific install steps and ephemeral usage; CLI shows a friendly missing‑dep warning with copy‑paste commands.  
- Tests pass: preview emission, panel snapshot/ordering, verbosity behavior, and docs/warning conditions.

---

### Notes for implementers
- Keep specifics (function names, data keys) aligned with existing code; if uncertain, prefer small adapters and TODOs over assumptions.
- All preview changes should be implemented in **`frame_compare.py`** (confirmed entrypoint) or its immediate helpers.
