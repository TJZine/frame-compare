---
RUN_ID: 2026-01-02__p5-4__report-service
VERSION: v2
TARGET: Phase 5 → Item 5.4 (Report Generator)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/report-viewer-spec.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
  - .agent-workflow/runs/2026-01-02__p5-4__report-service/plan-review-v1.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-4__report-service/plan-v2.md
---

# Implementation Plan: Report Generator Service

## Context

**Phase:** 5
**Module:** `frame_compare.services.report`
**Spec References:**

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md` (Section 6)
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/report-viewer-spec.md` (comprehensive viewer spec)

**Dependencies:**

- `frame_compare.config.schema.ReportConfig` (exists)
- `frame_compare.config.schema.ViewerMode` (exists)
- `frame_compare.errors.ReportError` (exists)
- `frame_compare.services.types.TmdbMetadata` (exists)

---

## Changes from v1

> [!NOTE]
> Changes made in response to `plan-review-v1.md`:

1. **SSOT updated:** `report-viewer-spec.md` Section 9.1 now includes frames/screenshots mapping validation conditions.
2. **SSOT updated:** `report-viewer-spec.md` Section 11 algorithm now specifies deterministic output-path fallback and iteration order.
3. **SSOT updated:** `data-contracts.md` Sections 3 and 4 now note that v2 contract is future; Phase 5.4 governed by `report-viewer-spec.md`.
4. **Added:** Public API signature in required backticked format.
5. **Fixed:** Test count and added missing tests for error conditions and JSON payload assertions.
6. **Fixed:** Replaced "sort clips/screenshots" directive with SSOT-aligned "preserve order" rule.

---

## SSOT Updates This Run

> [!IMPORTANT]
> **For Plan Review context:** This run created a new SSOT document based on a detailed legacy viewer reference provided by the user.

### New Document Created

**File:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/report-viewer-spec.md`

**What was retained from legacy:**

- Four viewer modes (Slider, Overlay, Difference, Blink)
- Dark theme aesthetic
- Filmstrip thumbnail navigation
- Full keyboard shortcuts for power users
- Accessibility patterns (ARIA)

**What was improved:**

| Area | Legacy | 2.0 Improvement |
|:-----|:-------|:----------------|
| Color palette | Pure blue `#9fd2ff` | Warmer `#5ba4e6` (reduced eye strain) |
| Zoom | Complex fit presets + pan | Simplified 25%-200% range for MVP |
| Data format | Separate `data.json` file | Embedded JSON (true single-file) |
| Typography | Custom fonts | System font stack (offline-safe) |
| Complexity | ~2300 lines | Target <1500 lines |

**What was deferred to future:**

- Full zoom/pan with fit presets
- Category-based frame filtering
- localStorage preference persistence
- Fullscreen mode (F key)
- External data.json loading
- Frame/encode metadata cards

### services-module.md Updates

Added sections 6.3 (Viewer Modes) and 6.4 (Keyboard Shortcuts) referencing the new spec.

### data-contracts.md Updates (v2 revision)

Added notes to Sections 3 and 4 marking v2 contract as future; Phase 5.4 governed by `report-viewer-spec.md`.

---

## Scope

This plan covers:

- [x] Create `src/frame_compare/services/report.py`
- [x] Define `ClipInfo` and `ReportData` dataclasses
- [x] Implement `generate_report(data, config, output_path) -> Path`
- [x] Generate self-contained HTML (inline CSS + JS)
- [x] Four viewer modes: Slider, Overlay, Difference, Blink
- [x] Dark theme with design tokens
- [x] Filmstrip thumbnail navigation
- [x] Keyboard shortcuts
- [x] Basic zoom controls (25%-200%)
- [x] Base64 image embedding and relative path modes
- [x] Accessibility (ARIA labels, keyboard navigation)
- [x] Update module exports
- [x] Comprehensive unit tests

This plan does NOT cover:

- Full zoom/pan with fit presets
- Category-based frame filtering
- localStorage preference persistence
- Fullscreen mode
- External data.json loading
- Encode/frame metadata cards

## Contract Impact

**Contracts touched:** NO

(Note: `data-contracts.md` was updated to clarify v2 sections are future, not to change contracts.)

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/report-viewer-spec.md`:
  - Section: "2. Data Structure"
  - Section: "3. Visual Design"
  - Section: "4. Viewer Modes"
  - Section: "5. Controls"
  - Section: "6. Keyboard Shortcuts"
  - Section: "7. Filmstrip"
  - Section: "8. Accessibility"
  - Section: "9. Error Handling"
  - Section: "11. Generation Algorithm"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md`:
  - Section: "6. Report Service"
  - Section: "6.1 Types"
  - Section: "6.2 Public API"
  - Section: "7. Error Handling"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md`:
  - Section: "2.2 Section Schemas"
  - Section: "2.3 Enums"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "1.3 Deterministic Test Vector Policy (SSOT)"

## Public API (Signatures)

- `generate_report(data: ReportData, config: ReportConfig, output_path: Path | None = None) -> Path`

## Files to Create/Modify

### 1. `src/frame_compare/services/report.py` [NEW]

**Purpose:** HTML comparison report generator service

**Types (per services-module.md Section 6.1):**

- `ClipInfo` — frozen dataclass with fields: `name`, `path`, `frame_count`, `resolution`, `fps`, `hdr`, `label`
- `ReportData` — frozen dataclass with fields: `clips`, `frames`, `screenshots`, `metadata`, `slowpics_url`

**Constants:**

- `REPORT_VERSION = "1.0"`

**Public API (per services-module.md Section 6.2):**

- `generate_report(data: ReportData, config: ReportConfig, output_path: Path | None = None) -> Path`

**Algorithm:** See report-viewer-spec.md Section 11.

**Error cases (per report-viewer-spec.md Section 9.1):**

- `ReportError("no clips provided")`
- `ReportError("at least 2 clips required for comparison")`
- `ReportError("no screenshots provided")` — for any of: empty frames, empty screenshots dict, missing clip key, empty clip list, length mismatch
- `ReportError("screenshot not found: {path}")`
- `ReportError("failed to encode image: {path}")`
- `ReportError("failed to write report: {reason}")`

### 2. `src/frame_compare/services/__init__.py` [MODIFY]

Add exports: `ClipInfo`, `ReportData`, `generate_report`

### 3. `tests/services/test_report.py` [NEW]

**Tests (27 total):**

| # | Test | Assertion |
|:--|:-----|:----------|
| 1 | `test_generate_report_creates_html_file` | `output_path.exists()` |
| 2 | `test_generate_report_custom_output_path` | uses provided path |
| 3 | `test_generate_report_config_output_dir` | falls back to config |
| 4 | `test_generate_report_default_output_path` | uses `data.screenshots[data.clips[0].name][0].parent / "report.html"` |
| 5 | `test_generate_report_no_clips_raises` | `"no clips provided" in str(exc)` |
| 6 | `test_generate_report_single_clip_raises` | `"at least 2 clips" in str(exc)` |
| 7 | `test_generate_report_empty_frames_raises` | `"no screenshots provided" in str(exc)` |
| 8 | `test_generate_report_empty_screenshots_dict_raises` | `"no screenshots provided" in str(exc)` |
| 9 | `test_generate_report_missing_clip_key_raises` | `"no screenshots provided" in str(exc)` |
| 10 | `test_generate_report_empty_clip_list_raises` | `"no screenshots provided" in str(exc)` |
| 11 | `test_generate_report_length_mismatch_raises` | `"no screenshots provided" in str(exc)` |
| 12 | `test_generate_report_screenshot_not_found_raises` | `"screenshot not found:" in str(exc)` (use non-existent path) |
| 13 | `test_generate_report_encode_failure_raises` | `"failed to encode image:" in str(exc)` (monkeypatch `Path.read_bytes` to raise `OSError`) |
| 14 | `test_generate_report_write_failure_raises` | `"failed to write report:" in str(exc)` (monkeypatch `Path.write_text` to raise `OSError`) |
| 15 | `test_generate_report_embed_images_base64` | `"data:image/png;base64," in html` |
| 16 | `test_generate_report_relative_paths` | `src="` present, no `data:` |
| 17 | `test_generate_report_includes_metadata` | TMDB title in HTML |
| 18 | `test_generate_report_includes_slowpics_url` | URL in header if provided |
| 19 | `test_generate_report_filmstrip_included` | filmstrip class present |
| 20 | `test_generate_report_filmstrip_excluded` | filmstrip absent when disabled |
| 21 | `test_generate_report_mode_slider` | `clip-path` in CSS |
| 22 | `test_generate_report_mode_overlay` | overlay mode JS present |
| 23 | `test_generate_report_mode_diff` | `mix-blend-mode: difference` |
| 24 | `test_generate_report_mode_blink` | `setInterval` in JS |
| 25 | `test_generate_report_creates_parent_dirs` | missing dirs created |
| 26 | `test_generate_report_dark_theme` | `--bg-primary: #0f1115` |
| 27 | `test_generate_report_keyboard_shortcuts` | `ArrowLeft`, `ArrowRight` in JS |
| 28 | `test_generate_report_accessibility` | `aria-label=` present |
| 29 | `test_generate_report_json_payload_structure` | embedded JSON contains `version`, `generated_at`, `default_mode`, `clips`, `frames`; clips order matches `data.clips`; frames order matches `data.frames`; each frame's images order matches clips |
| 30 | `test_clip_info_frozen` | `TypeError` on attribute assignment |
| 31 | `test_report_data_frozen` | `TypeError` on attribute assignment |

### 4. `docs/DECISIONS.md` [MODIFY]

**Facts to record:**

- RUN_ID: `2026-01-02__p5-4__report-service`
- Created new SSOT: `report-viewer-spec.md`
- Updated SSOT: `services-module.md` Section 6 (added 6.3, 6.4)
- Updated SSOT: `data-contracts.md` Sections 3, 4 (marked v2 as future)
- Scope: MVP report viewer with 4 modes, dark theme, filmstrip, keyboard shortcuts
- Deferred: zoom/pan, categories, localStorage, fullscreen
- Design rationale: simplify for MVP, warmer color palette, embedded JSON

### 5. `CHANGELOG.md` [MODIFY]

```markdown
### Added
- HTML comparison report generator with Slider, Overlay, Difference, and Blink modes
- Dark theme with modern styling
- Filmstrip thumbnail navigation
- Keyboard shortcuts (←/→ frames, ↑/↓ encodes, S/O/D/B modes)
- Basic zoom controls (25%-200%)
- Accessibility features (ARIA labels, keyboard navigation)
```

## Acceptance Criteria

- [ ] GIVEN valid ReportData WHEN `generate_report()` called THEN HTML file created
- [ ] GIVEN `config.embed_images=True` THEN images base64 encoded
- [ ] GIVEN `config.embed_images=False` THEN images use relative paths
- [ ] GIVEN `config.include_filmstrip=True` THEN filmstrip present
- [ ] GIVEN empty clips THEN `ReportError("no clips provided")`
- [ ] GIVEN 1 clip THEN `ReportError("at least 2 clips required for comparison")`
- [ ] GIVEN any screenshots validation failure THEN `ReportError("no screenshots provided")`
- [ ] GIVEN missing screenshot file THEN `ReportError("screenshot not found: {path}")`
- [ ] GIVEN OSError reading image THEN `ReportError("failed to encode image: {path}")`
- [ ] GIVEN OSError writing file THEN `ReportError("failed to write report: {reason}")`
- [ ] HTML includes dark theme CSS variables per spec Section 3.1
- [ ] HTML includes keyboard handlers per spec Section 6
- [ ] HTML includes ARIA labels per spec Section 8
- [ ] Embedded JSON preserves `data.clips` and `data.frames` order

## Verification Commands

```bash
# Quality gates
.venv/bin/pyright --warnings src/frame_compare/services/report.py
.venv/bin/ruff check src/frame_compare/services/report.py
.venv/bin/pytest -v tests/services/test_report.py

# Full module verification
.venv/bin/pyright --warnings src/frame_compare/services/
.venv/bin/ruff check src/frame_compare/services/
.venv/bin/pytest -v tests/services/

# Import linter
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0.

## Notes for Coding Agent

1. **Import pattern:** `ReportConfig`, `ViewerMode` from `frame_compare.config`

2. **Color palette:** Use exact CSS custom properties from report-viewer-spec.md Section 3.1

3. **Viewer modes:** Use exact CSS/JS patterns from report-viewer-spec.md Section 4

4. **Keyboard shortcuts:** Implement full table from report-viewer-spec.md Section 6

5. **ARIA:** Follow report-viewer-spec.md Section 8 for accessibility

6. **Error messages:** Match exact strings from report-viewer-spec.md Section 9.1

7. **HTML structure:** Follow layout from report-viewer-spec.md Section 3.3

8. **JSON embedding:** Use `<script type="application/json" id="report-data">`

9. **CSS class naming:** Use `rv-` prefix per report-viewer-spec.md Appendix A

10. **Deterministic output (SSOT-aligned):** Preserve `data.clips` and `data.frames` order; do not sort. Iterate `data.screenshots` by indexing with clip names from `data.clips` (do not rely on dict iteration order).

11. **Output-path fallback:** Use `data.screenshots[data.clips[0].name][0].parent / "report.html"` per SSOT Section 11.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-02__p5-4__report-service

## Plan to Review

Read file: .agent-workflow/runs/2026-01-02__p5-4__report-service/plan-v2.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/report-viewer-spec.md
4. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/data-contracts.md

## Previous Review

Read file: .agent-workflow/runs/2026-01-02__p5-4__report-service/plan-review-v1.md

## Your Task

Validate the plan using the 9-point checklist. Confirm all issues from plan-review-v1.md are addressed.

## Output

Write file: .agent-workflow/runs/2026-01-02__p5-4__report-service/plan-review-v2.md
