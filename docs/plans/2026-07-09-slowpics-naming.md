Status: Active
Scope: slow.pics naming and upload fixes
Owner: Antigravity

# Plan - slow.pics Naming and Upload Options

This plan outlines the implementation to restore naming precision and configure missing upload fields for slow.pics.

## 1. Context & Risk Analysis

- **Task Family**: CLI/config contract change & hotspot/runtime pipeline change.
- **Risk Tier**: **High Risk** (modifies config validation schema, CLI contract files, and post-render orchestration).
- **Invariants to Preserve**:
  - Keep VapourSynth-heavy imports lazy (no VS module imports at CLI load time).
  - Preserving immutable config architecture (do not mutate config or RunContext instances in-place).
  - Outbound HTTP integrations remain strictly inside `services.publishers`.

---

## 2. Goals & Non-Goals

### Goals
- Support explicit gallery overrides via `slowpics.title` and `slowpics.title_suffix`.
- Default to `"{metadata.title} ({metadata.year})"` for automatic title resolution when TMDB is active, falling back to the screenshot directory name.
- Align slow.pics column headers (image names) with `clip.label` instead of the raw video file stem.
- Allow users to override specific clip labels using a new `label` field in `[sources.overrides]`.
- Map and deliver `tmdbId` (auto-resolved or explicit), `is_hentai` (as `hentai`), and `remove_after_days` (as `removeAfter`) to slow.pics upload metadata.
- Keep `docs/current-cli-contract.md` fully up to date.

### Non-Goals
- No legacy string.Template variable interpolation support (we use the simplified `title` + `title_suffix` design).
- No changes to physical screenshot file naming on disk.

---

## 3. Owner Seams & Files in Scope

### Files in Scope
- `src/frame_compare/config/schema_models.py` (Add new config definitions and validation rules for safe strings and positive ints)
- `src/frame_compare/orchestration/selection_domain.py` (Add override label support and strictly validate label uniqueness to prevent upstream render crashes)
- `src/frame_compare/orchestration/phase_post_render.py` (Orchestrate slow.pics gallery title resolution with `(year)` fallback logic and image labeling)
- `src/frame_compare/services/publishers.py` (Build and map slow.pics API payload fields)
- `docs/current-cli-contract.md` (Authority CLI/Config contract doc)

### Files Out of Scope
- `src/frame_compare/analysis/**`
- `src/frame_compare/render/**`

---

## 4. Contract Specifications

### Config-Only `[slowpics]` Fields
The following fields will be added to the public `[slowpics]` configuration:
- `title: str = ""` - Explicit gallery title. (Validators will strip control characters and newlines)
- `title_suffix: str = ""` - Appended suffix (e.g. `"HDR"`) separated by a space. (Validators will strip control characters and newlines)
- `remove_after_days: int = 0` - Image auto-removal setting sent to the remote API (must be >= 0, maps 0 to empty string for API).
- `is_hentai: bool = False` - Hentai flag.
- `tmdb_id: str = ""` - TMDB override string.
- `tmdb_category: Literal["movie", "tv"] | None = None` - Required if a raw numeric `tmdb_id` is provided without remote metadata access.

### Clip Override `[sources.overrides]` Field
The following field will be added to per-source overrides:
- `label: str | None = None` - Custom label override (must not be empty/whitespace and must not contain control characters).

---

## 5. Verification Strategy

- **Primary Verification Mode**: `contract-first`
- **Plan Classification**: `new regression/contract test required`

### Why this depth matches the risk
This changes the validated public configuration surface and public HTTP request payloads. Full test coverage is required to verify config loading, schema serialization, label propagation, and correct multipart boundary formatting.

### Verification Commands
```bash
# Static type checking
.venv/bin/pyright --warnings

# Check syntax and style
.venv/bin/ruff check .

# Execute full test suite
.venv/bin/pytest -q

# Verify import layers
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

---

## 6. Rollback & Stop Conditions

- **Rollback Surface**:
  - Run `git checkout -- <file>` on any touched files to revert.
- **Stop and Replan Triggers**:
  - If adding `label` to `SourceOverrideConfig` breaks Pydantic parsing of existing workspace override configurations.
  - If slow.pics upload endpoints reject the resolved `tmdbId` format (e.g. `MOVIE_123` / `TV_456`).
  - If the new `tmdb_category` and validation logic cannot reliably resolve an explicit `tmdbId` into the expected string.
