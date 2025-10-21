# Codex Task — VSPreview **Baseline** Mode → Rich CLI Panel → Docs (in this order)

> **Subtask order (must implement in this sequence):**
> 1) **Preview changes** — VSPreview opens in *baseline* (0‑frame) mode; suggested offset is visible but **never applied** in preview.  
> 2) **CLI cleanup** — add a **Rich** “VSPreview Information” panel (above “At‑a‑Glance”) to highlight the suggestion & mode; demote noisy logs to `--verbose`.  
> 3) **Docs & missing‑dep hints** — document install/run of VSPreview and show a friendly CLI hint when the feature is enabled but missing.

## Phase 1 — VSPreview **Baseline** Mode (Preview changes)

### Requirements
- When `use_vspreview = true`, the generated VSPreview script must:
  - Load **reference** and **target** clips exactly as the pipeline would (tonemap/props/FPS parity with screenshots).
  - Initialize `OFFSET_MAP` to **0** for all targets; **do not** pre‑apply any auto suggestion in preview.
  - Keep even/odd output pairing (0↔1, 2↔3, …). Ensure **Sync Outputs** works as before.
- Compute the **suggested alignment** (frames + seconds) exactly as the pipeline currently does, but **use it only for display** (see overlay & CLI in later phases). It is **guidance only**, never applied in preview.
- **Overlay (ON by default):** draw a small text overlay on the preview outputs with:
  - `Suggested: +{S}f (~{S_secs}s)` and `Applied in preview: 0f (baseline)`
  - Sign hint: `(+ trims target / − pads reference)`
  - Provide a config switch to disable overlay if desired.

### Config additions (names may be adjusted to match your models)
```toml
[audio_alignment]
use_vspreview = true
vspreview_mode = "baseline"          # default; keep "seeded" as an opt‑in if needed
show_suggested_in_preview = true     # overlay is ON by default per product decision
```

### Persistence (unchanged behaviors to keep)
- Persist **only the manual** value the user accepts **after** preview (either typed in CLI or via “read OFFSET_MAP on exit” if that flow exists).  
- Current behavior note: manual selection **persists across reruns** via `generated.audio_alignment` (or similar) until that file is deleted. Keep that behavior unless there’s a clear reason to change it.

### Tests
- Unit: preview emission sets `OFFSET_MAP=0` when `vspreview_mode="baseline"` (regardless of suggestion value).
- Unit: overlay text is composed using the suggestion, *not* the applied offset (which remains 0f).
- Integration: with a non‑zero suggestion, preview shows **baseline** clips; accepting a manual value persists that value only; a rerun reuses the manual value unless the offsets file is removed.

> **Implementation pointer:** centralize the preview emission in **`frame_compare.py`** behind a small “mode” switch (baseline vs seeded), returning both clips and the computed suggestion so UI layers can render overlays without changing clip data.

---

## Phase 2 — CLI **Rich** Panel (“VSPreview Information”) & Noise Control

> Use the project’s existing Rich theme and layout conventions (`src/cli_layout.py`). **Do not invent new color names**; reuse existing role names defined for headers, keys, values, warnings, etc. (see the layout/theme JSON in the repo).

### Panel placement & title
- **Place above the existing “At‑a‑Glance” section**.
- Title it **“VSPreview Information”** (or a close variant consistent with your style guide).

### Panel contents (high‑visibility, minimal)
- **Reference** and **Target** labels (short basenames; include fps/frames only if your CLI already shows them nearby).
- **Suggested alignment**: `+Nf (~Xs)` **GUIDANCE ONLY — not applied in preview**.
- **Preview mode**: `baseline (0f applied to both clips)`.
- **Action**: e.g., `Open VSPreview → align manually → confirm frames in CLI`  
  (or `… → close → we read OFFSET_MAP on exit` if that path is enabled).

### Behavior
- Colorize & box the panel using Rich; fall back to plain text when no TTY / `--no-color`.
- **Demote noise**: third‑party chatter (plugin loads, numpy subnormal warnings, etc.) must be shown only with `--verbose`/`--debug`.  
  Default = WARNING; `--verbose` = INFO; `--debug` = DEBUG. Apply localized warning filters if safe.
- **JSON tail** (non‑breaking): add
  ```json
  { "vspreview_mode": "baseline", "suggested_frames": N, "suggested_seconds": X.XXXXXX }
  ```

### Tests
- Formatting snapshot: the panel renders with stable structure/roles; placement is **above** “At‑a‑Glance”.
- TTY vs non‑TTY: ANSI on terminals; plain text otherwise; `--no-color` honored if present.
- Verbosity: default suppresses plugin/warning noise; `--verbose` shows it.

---

## Phase 3 — Docs & Missing‑Dependency Hint

### Docs (README / pipeline)
- Add **Install & Run VSPreview** section with `uv` commands:
  - **Windows (recommend PySide6)**  
    ```powershell
    uv add vspreview PySide6
    ```
  - **Linux/macOS (recommend PyQt5)**  
    ```bash
    uv add vspreview PyQt5
    ```
- Show how to keep GUI deps **optional** via a project extra (example only; align with your packaging):
  ```toml
  [project.optional-dependencies]
  preview = ["vspreview>=0.7", "PySide6>=6.6"]   # Windows example
  # preview = ["vspreview>=0.7", "PyQt5>=5.15"]  # Linux/macOS example
  ```
  Ephemeral run: `uv run --with .[preview] -- python -m vspreview path/to/vspreview_*.py`

### CLI missing‑dep hint
- When `use_vspreview=true` but `vspreview` or the Qt backend isn’t importable:
  - Do **not** fail the run; render a **Rich warning** near the top with copy‑paste commands (Windows vs Linux/macOS).
  - Show the command we would have run: `python -m vspreview path/to/vspreview_*.py`.
  - Add `{"vspreview_offered": false, "reason": "vspreview-missing"}` to JSON tail (non‑breaking).

### Tests
- Docs lint passes (if present).  
- Warning renders only when missing; otherwise suppressed.  
- JSON tail field present when applicable.

---

## Guardrails / Non‑Goals
- Maintain **parity** between preview clips and screenshot pipeline (same tonemap/props/FPS).  
- Do **not** change offset sign semantics or the persistence file format without approval.  
- Avoid large assumptions about module names or locations; prefer TODOs and lookups where repo context is needed (except the confirmed `frame_compare.py` entrypoint above).

---

## Risks & Mitigations
- **Operator expectation drift** (some expect seeded preview): mitigate with the clearly titled panel and overlay stating *GUIDANCE ONLY — not applied*.
- **Formatting regressions**: reuse existing Rich roles; add/update formatting tests.
- **Dependency noise**: push to `--verbose`; keep default output minimal.


