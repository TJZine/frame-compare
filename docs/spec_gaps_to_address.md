Other master-checklist spec gaps (quick scan)

- Phase 5–7 are missing **Reference:** blocks entirely (refs stop at docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-
    checklist.md:305, Phase 5 starts at :365).
- Checklist items that currently have no SSOT backing in module specs:
  - tonemap(clip, preset, **overrides) naming drift (docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-
        checklist.md:277 vs SSOT apply_tonemap at docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-
        module.md:296)
  - Auto-crop + mod-2 padding (docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:316, :317)
  - Audio offsets cache path (docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:373)
  - “local-only mode” semantics (docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:392)

  ———

## Updated Spec-Gap Closure Plan (Spec-only; no runtime implementation)

### Goal

  Close all identified SSOT ↔ master-checklist gaps so future checklist runs can produce implementation-ready plan-v1.md
  with zero design decisions.

### Your constraints baked in

- Local mode is not a separate switch; it means local HTML report UI (slow.pics upload optional).
- All per-video artifacts/caches live together under comparison_videos/, with caches specifically under
    comparison_videos/cache/.
- Auto-cropping default OFF for 1.0 (still spec’d deterministically for later enablement).
- Add an explicit SSOT note: perf_span complements (does not replace) RunMetrics.

  ———

### Part 1 — Legacy Repo Evidence Gathering (single block; run in legacy repo)

  Copy/paste to your legacy-repo agent:

  You are an archaeology agent. Do NOT implement changes. Extract legacy behavior/spec evidence only.

  Return results in this exact format per section:

- Behavior Rules (bullets, deterministic/heuristic rules spelled out)
- Public API (one-line signatures in backticks + file:symbol)
- Defaults (explicit default values + where set)
- Edge Cases (missing metadata, HDR/SDR, overlay/tonemap interactions)
- Cache/Path Schema (if applicable: exact filename, schema keys, versioning, invalidation)
- Tests (exact test names + what they assert)

  A) Render auto-crop detection + mod-2 padding (Phase 4.2)

- Find the code that decides crop bounds and any “mod-2” (or mod-N) padding.
- Include: which frames are sampled (indices), thresholds, confidence rules, and what happens when detection fails.
- Specify padding: which sides, rounding direction, and whether it’s applied before/after crop.

  B) Audio alignment cache (Phase 5.1)

- Find exact cache filename/path (relative + absolute construction).
- Extract schema (TOML/JSON/etc), required fields, version field (if any), stable ordering rules.
- Invalidation: what changes cause recompute (mtime/size/hash/config/preset/version).

  C) Local-report vs upload semantics (Phase 5.3 / report)

- Identify how legacy differentiates “local report only” vs “upload to slow.pics”.
- Confirm whether this was a separate flag or just “disable upload”.
- Enumerate outputs produced in local mode (HTML report, screenshots, metadata JSON, logs).

  D) Tonemap public API naming (Phase 3.5)

- Identify canonical public tonemap function name and signature.
- Document override semantics and how call sites import it.

  You’ll paste those findings back into the planning agent prompt for the SSOT edits.

  ———

### Part 2 — Patch SSOT + Master Checklist (spec-only edits)

#### 2.1 Render spec: auto-crop + mod-2 (default OFF)

  Edit: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md

- Add headings (verbatim, stable):

- ## Auto-crop Detection (SSOT)

- ## Mod-2 Padding (SSOT)

- Under each, define:
  - Backticked one-line signatures for any new public helpers (or explicitly “internal-only in render/geometry.py”).
  - Determinism requirements (exact sampling policy; if heuristic, define confidence gate + fallback behavior).
  - Auto-crop default OFF for v1.0 (and where the flag lives).
  - Mod-2 padding rules (exact rounding + which edges).
  - Exact test names + assertions (pure unit tests; no VS dependency).

#### 2.2 Services spec: alignment cache + local report/upload split

  Edit: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md

- Add:

- ### Audio Alignment Caching (SSOT) (under Audio Alignment)

    - Canonical cache path must align with your new policy: comparison_videos/cache/... (exact filename defined
            here).
    - Schema with explicit version field and stable ordering requirements.
    - Invalidation rules (what changes recompute).

- ### Local Report Mode (SSOT) (under Publishers/Report)

    - Define: local HTML report always generated; slow.pics upload optional.
    - Explicitly state “no separate local-only switch”; it’s derived from the publish/upload setting.

#### 2.3 Workspace/cache policy (single canonical definition; no redundancy)

  Pick one SSOT owner (recommended): docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
  (WorkspacePaths)

- Update WorkspacePaths semantics to support:
  - Default workspace/artifacts root: comparison_videos/
  - Cache location: comparison_videos/cache/
  - Screenshot/report locations (explicit subpaths)
- Add an SSOT note near perf + metrics clarifying:
  - RunMetrics = coarse phase timing
  - perf_span = opt-in fine-grained spans

  (If changing WorkspacePaths fields is required, that must be explicitly specified here as a public API change so
  future implementation runs don’t guess.)

#### 2.4 VS spec: tonemap naming drift (single canonical public name)

  Edit: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md

- Decide one public name (either keep apply_tonemap or rename to tonemap) and specify:
  - Backticked signature(s)
  - Whether any alias exists (and whether it’s public vs internal-only)
- Ensure master checklist matches SSOT (no new behavior introduced only in checklist).

#### 2.5 Master checklist hygiene (Phase 5–7 references + signature alignment)

  Edit: docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md

- Add **Reference:** blocks for Phases 5, 6, 7 (no “floating requirements”).
- Fix checklist signature/path drift to match SSOT exactly:
  - tonemap naming item (docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:277)
  - render auto-crop/mod-2 items (docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:316, :317)
  - audio offsets cache path (docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:373) to
        comparison_videos/cache/...
  - local-only wording (docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md:392) to “local report mode (no
        upload)”

#### 2.6 Decision log + doc consistency

  Edit:

- docs/DECISIONS.md: record the resolved ambiguities (cache layout, local mode semantics, auto-crop default OFF,
    tonemap naming)
- CHANGELOG.md: only if you want to surface “docs/spec clarified” (optional)

  ———

### Verification gates (spec-only run)

- Must-pass:
  - UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
  - UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check (should remain no-
        op)
  - rg -n "\\*\\*Reference:\\*\\*" docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md (Phase 5–7 must have
        refs)
- Pass criteria:
  - No checklist item defines behavior absent from SSOT
  - All new SSOT headings have: signatures + deterministic rules + tests + failure modes

  ———

### Risk / Review Focus (tell Verify/Review agents exactly what to scrutinize)

- Confirm cache-path SSOT is defined once and referenced elsewhere (no competing “generated_dir” vs
    “comparison_videos/cache” definitions).
- Confirm local-report semantics do not introduce a second toggle (no redundant flags).
- Confirm auto-crop is explicitly default OFF and cannot run without an explicit enable flag + deterministic sampling
    policy.
- Confirm tonemap naming has exactly one canonical public entry point (aliases explicitly labeled).

  ———

  If you want this written as an actual run artifact, confirm a meta run id (suggestion: 2025-12-30__meta__spec-gap-
  closure) and I’ll format it into .agent-workflow/runs/<RUN_ID>/plan-v1.md.

  Conventional Commit subject: docs(spec): close SSOT gaps for phases 4–7
