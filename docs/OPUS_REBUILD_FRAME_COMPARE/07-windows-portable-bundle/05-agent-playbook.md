# Windows Portable Bundle — Agent Playbook (Step-by-Step)

> **Module:** Distribution
> **Version:** 1.0
> **Purpose:** Concrete, low-ambiguity execution steps for agents

---

## 1. Baseline Decisions (Already Resolved)

From `03-user-interview.md`:

- Windows 10 + 11
- x86_64 (amd64) baseline only
- Pinned portable folder with embedded Python runtime
- BYO VapourSynth best-effort; baseline bundle is supported/CI-tested
- GPU/libplacebo optional; fallback must always work

---

## 2. Execution Workflow (Agent Loop)

Follow the canonical run-artifact workflow in:

- `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md`

### 2.1 Run IDs (Recommended)

Use a dedicated RUN_ID per slice, e.g.:

- `YYYY-MM-DD__p8-1__win-bundle-spec`
- `YYYY-MM-DD__p8-2__win-bundle-build`
- `YYYY-MM-DD__p8-3__win-bundle-ci`

---

## 3. Planning Agent Steps (User Back-and-Forth Included)

### Step A — Collect Pin Inputs (STOP if missing)

Use `03-user-interview.md` and collect **exact artifact sources** for:

- VapourSynth Windows runtime
- Plugins (Windows builds): L-SMASH Works, vs-placebo, ffms2 (if included)
- FFmpeg Windows build
- Embedded Python distribution choice (exact version + URL)

For each artifact, record:

- version/tag/commit
- download URL(s)
- sha256
- license note (link)

If any artifact inputs are missing: STOP (do not guess “latest”).

### Step B — Update SSOT (facts only)

Update/extend SSOT docs as needed:

- `01-bundle-spec.md` (layout + launcher env rules)
- `02-support-matrix.md`
- `deployment.md` (Windows section)

Record the decision facts in `docs/DECISIONS.md`.

### Step C — Write a Plan (implementation-ready)

Write `.agent-workflow/runs/<RUN_ID>/plan-v1.md` that mandates:

- file list (scripts, manifests, CI workflow files)
- exact artifact download + hash verification behavior
- exact bundle layout
- exact smoke tests + pass criteria

---

## 4. Plan Review Agent Steps (Anti-Churn)

Approve only if:

- The plan contains no TBDs or alternative “pick one” paths.
- Artifact URLs + sha256 values are present (or explicitly deferred with STOP gates).
- Tests assert “tonemap works without raising (fallback allowed)” as baseline.
- If a GPU-required test exists, it is explicitly opt-in and not part of the baseline.

---

## 5. Coding Agent Steps (Implementation)

Implement exactly what the plan specifies, typically:

1. Add PowerShell build script(s) to assemble the portable bundle.
2. Add a `manifest.json` generator/checker:
   - writes versions + sha256
   - verifies downloads match hashes before packaging
3. Add launcher scripts:
   - set `PATH`, `VAPOURSYNTH_PLUGIN_PATH`
   - run `frame-compare` entrypoint
4. Add Windows CI workflow that:
   - builds the portable bundle
   - runs smoke checks
   - uploads bundle artifact

---

## 6. Verification Agent Steps (Gates)

Run required quality gates plus Windows checks:

- `.venv/bin/pyright --warnings`
- `.venv/bin/ruff check .`
- `.venv/bin/pytest -q`

Windows smoke checks (exact commands per plan), e.g.:

- `frame-compare doctor --json` exits 0
- creates a `vs.VideoNode` clip
- exercises tonemap and confirms no exception (fallback allowed)

Update:

- `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md` Phase 8 items as they become true.

---

## 7. Review Agent Steps (Release Readiness)

Confirm:

- Bundle spec is satisfied (layout, manifest presence, launcher env wiring).
- Windows CI is green and artifacts are reproducible.
- Docs match shipped baseline (versions/hashes).
