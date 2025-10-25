# Task — VSPreview-Assisted Manual Alignment

## Context
- Audio correlation already drives automatic trim offsets and falls back to manual file edits when confidence drops (`frame_compare.py:2608`, `frame_compare.py:2700`).
- Alignment previews today rely on generated PNGs and user confirmation; when declined we instruct operators to edit the offsets TOML manually (`docs/audio_alignment_pipeline.md`, `docs/deep_review.md`).
- VapourSynth ingestion, clip planning, and negative-offset handling already exist (`src/vs_core.py`, `frame_compare.py:1180`, `frame_compare.py:1330`), giving us the primitives to seed a VSPreview workflow.
- We must respect workspace containment, interactive vs non-interactive sessions, and current configuration guardrails (`docs/adr/0001-paths-root-lock.md`, `pyrightconfig.json`).

## Scope
Deliver an optional manual-alignment flow that:
- Runs immediately after the audio-alignment phase (when enabled), surfaces the measured offset as guidance without mutating trims automatically, and proceeds even when audio alignment is disabled.
- Offers VSPreview assistance when automatic results are low-confidence or operators simply want visual confirmation.
- Generates a temporary VapourSynth script that mirrors Frame Compare’s clip initialization.
- Launches VSPreview, provides operator guidance, and captures the chosen frame offset.
- Applies the chosen offset to the appropriate clip plan (respecting existing manual trims) and persists it in the offsets TOML with the correct provenance.
- Degrades gracefully when VSPreview or VapourSynth preview dependencies are unavailable (headless runs, Windows without GUI, etc.).

Out of scope:
- Rewriting the existing audio alignment pipeline.
- Introducing generalized GUI integrations beyond VSPreview.
- Replacing the offsets TOML contract.

## Phase 1 – CLI Detection, Config Wiring, and Result Surfacing
### Goals
- Let operators opt into VSPreview alignment, surface the offer immediately after audio alignment runs, and present auto-alignment measurements as a starting hint rather than auto-applying trims.

### Tasks
- Add configuration switch (e.g., `[alignment].use_vspreview` or `[audio_alignment].use_vspreview`) with defaults and validation in `src/datatypes.py` and `src/config_loader.py`.
- Extend CLI option set if we want a one-off `--no-vspreview` escape hatch (keep parity with config precedence).
- In `_maybe_apply_audio_alignment` / surrounding orchestration, ensure VSPreview prompts happen directly after the audio-alignment phase (even when alignment succeeds) when the flag is enabled and the session is interactive. If audio alignment is disabled, the VSPreview phase still executes in the same slot but with no automatic measurement.
- When audio alignment produced measurements, log and display the suggested starting offset without mutating `ClipPlan` trims; present these numbers to operators entering VSPreview so large offsets (hundreds of frames) are easy to dial in.
- When manual trims already exist in config (e.g., `[overrides].trim_start`), summarise them in the VSPreview prompt so the operator knows what baseline is currently in effect before calculating an additional adjustment.
- Ensure the JSON tail/CLI reporter capture the decision point so downstream automation can see whether VSPreview was offered.

### Deliverables
- Updated config schema + docs stub in `docs/README_REFERENCE.md`.
- CLI flowchart documenting when VSPreview launches (add paragraph to `docs/audio_alignment_pipeline.md`, noting sequencing relative to audio alignment).
- UI copy (CLI output) that includes: audio alignment recommendation (if available), existing manual trim summary, VSPreview instructions.

### Success Criteria
- Running with `use_vspreview = false` retains current behaviour (auto alignment still auto-applies trims when configured).
- With VSPreview enabled, audio-alignment measurements are reported as guidance only; no trims change until the operator confirms a value.
- Interactive runs with or without audio alignment display a clear VSPreview prompt after the alignment phase, including existing trim context.

## Phase 2 – VSPreview Session Scaffolding
### Goals
- Generate and launch a safe VapourSynth script that mirrors clip loading and allows quick offset experimentation.

### Tasks
- Build a helper (likely under `src/vs_core.py` or a new module) that accepts the reference/target `ClipPlan`s and emits a temporary `.py` script under the workspace (`_resolve_workspace_subdir` guards).
- Script requirements:
  - Use the same source plugin ordering we rely on in production (`src/vs_core.py`).
  - Preserve the same clip processing the pipeline uses (including HDR tonemap and prop normalization) so the preview matches final screenshots; consider a future “raw mode” toggle only if performance becomes an issue.
  - Seed an `offset = <suggested>` variable using the audio-alignment recommendation when available, otherwise default to 0. Provide comments reminding the operator about existing manual trims so they can derive the final value.
  - Apply the offset as a trim to the target clip (guard for negative values) but clearly comment that the real pipeline remains untouched until the operator confirms within Frame Compare.
  - Call `set_output(0)` / `set_output(1)` so VSPreview can toggle inputs.
  - Harmonise FPS via `core.std.AssumeFPS` when clips disagree (surface a warning if conversion fails).
- Detect VSPreview availability:
  - Prefer `vspreview` executable on `PATH`; fall back to `python -m vspreview` if installed module is detected.
  - Respect non-interactive sessions or missing binaries by skipping to legacy behaviour with a warning.
- Launch the preview using `subprocess.run`, inheriting environment variables (document expectation to install vs-preview).
- Print concise operator instructions (number keys to switch, editing offset + reload with Ctrl+R).

### Deliverables
- Helper tests covering script generation (parse resulting file to ensure we emit `set_output` calls).
- CLI log entries referencing the script path for debugging.

### Success Criteria
- When dependencies exist, VSPreview opens with two clips ready, and the temporary script is cleaned up afterwards.
- When dependencies are missing, the CLI reports the fallback path without crashing.

## Phase 3 – Offset Capture & Persistence
### Goals
- Collect manual offsets from the operator, reconcile them with any pre-existing manual trims, and feed the result into the existing trim pipeline.

### Tasks
- After VSPreview closes, prompt for a signed integer offset; reuse `click.prompt` with validation and remind the operator about any manual trims already applied.
- Interpret positive vs negative offsets consistently with `_maybe_apply_audio_alignment` (negative values adjust the reference via `_extend_with_blank`, positive values trim the target). Combine the new value with existing manual trims or override entries so the persisted result reflects the total trim the pipeline should use (e.g., existing 120-frame trim + VSPreview delta 7 → final 127). Allow negative deltas to reduce the effective trim or migrate adjustment to the reference clip when the original trim overshoots.
- Update each `ClipPlan`’s `trim_start` before we proceed to frame selection.
- Record the chosen offset in the offsets TOML (`src/audio_alignment.py:update_offsets_file`) with `status="manual"` and a note indicating “VSPreview”.
- Surface the manual offset in the CLI summary / JSON tail for traceability.
- Persist offsets for each target clip when multiple clips exist—loop through targets sequentially, always comparing to the chosen reference.

### Deliverables
- Unit tests covering positive, zero, and negative offsets (see `tests/test_audio_alignment.py`, `tests/test_frame_compare.py`).
- Snapshot adjustments for JSON tail metadata when manual offsets are captured.

### Success Criteria
- Rerunning the CLI after accepting a VSPreview offset reuses the persisted value (no prompt) and includes any prior manual trims in the reported baseline.
- Negative offsets leave the target trim at zero and pad the reference clip correctly (verify `frame_compare.py:1300` logic).

## Phase 4 – Documentation, UX, and QA
### Goals
- Document the feature, ensure UX polish, and extend coverage.

### Tasks
- Update `README.md` quick-start alignment section and `docs/README_REFERENCE.md` entry for the new flag.
- Add a focused section to `docs/audio_alignment_pipeline.md` describing the VSPreview workflow, prerequisites, and headless limitations.
- Extend CLI help text (e.g., `--help`) to mention VSPreview alignment hooks.
- Add integration tests if feasible (may rely on injecting fake VSPreview command); otherwise, design a harness that verifies fallback path via dependency injection.
- Ensure pyright coverage (add stubs if we import VSPreview modules).
- Capture the decision in `docs/DECISIONS.md` after implementation.

### Deliverables
- Updated docs, help text, and changelog entry draft.
- QA checklist for manual testing across macOS/Linux/Windows (documented in `docs/tests_plan_paths_root_lock.md` style), including scenarios with pre-existing manual trims and large auto-alignment suggestions.

### Success Criteria
- Documentation changes reviewed by maintainers.
- Pyright/pytest remain green.
- Manual test notes confirm VSPreview prompt, fallback, and persistence.

## Risks & Mitigations
- **VSPreview not installed** — Detect early, warn, and fall back to existing manual-edit instructions.
- **Headless environments** — Skip launch when `sys.stdin.isatty()` is false or when `$DISPLAY`/equivalent missing.
- **Script path containment** — Ensure temp files live under `_resolve_workspace_subdir` to avoid breaking ADR 0001.
- **Multiple targets** — Explicit loop ensures offsets are collected per target without overwriting reference state.
- **Windows shell quoting** — Use `subprocess.run` with `shell=False` and handle `.py` association correctly.
- **User cancels** — Allow aborting the prompt (empty input) and revert to legacy manual-edit flow.
- **Manual trim accumulation** — Make sure we don’t double-count existing overrides when recording VSPreview adjustments; always communicate and compute relative to the current baseline.
- **Over-trimmed sources** — If a pre-configured trim removes more leading frames than available, warn the user that the clip cannot be shifted backwards without restoring the original footage; support negative deltas that reduce the manual trim or reassign the adjustment to the reference clip via blank-frame padding.
- **Long-running previews** — Keep VSPreview open indefinitely and document that behaviour; in headless or automated runs, detect missing GUI support early and fall back to the existing manual-edit instructions instead of forcing a timeout.


## References
- `frame_compare.py:1180-1427`, `frame_compare.py:2608-2720`
- `src/audio_alignment.py:291-504`
- `src/vs_core.py`
- `docs/audio_alignment_pipeline.md`
- `docs/adr/0001-paths-root-lock.md`
