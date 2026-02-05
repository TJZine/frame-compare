# Phase 8 Orchestrator Playbook (Windows Portable Bundle)

This playbook is written for a **human orchestrator** directing an AI agent. Phase 8 does *not* fit the normal FC2
“one checklist item per run” workflow well because it is dominated by:

- External, pinned binary artifacts (URLs, sha256, licenses)
- Windows-only behavior (PowerShell, PATH/registry quirks)
- CI-produced artifacts (where the real truth lives)
- Deterministic reproducibility requirements

Use this as a practical guide to scope Phase 8 work into safe slices with minimal ambiguity.

---

## Core Principles (Non-Negotiable)

1. **No “latest”**: every external artifact must be pinned by version + sha256.
2. **Single source of truth**: record pins in-repo (manifest + decisions) so CI and humans match.
3. **Determinism first**: assembly must be reproducible from pinned inputs, with stable directory layout.
4. **CI is truth for Windows**: prefer Windows CI execution over local assumptions.
5. **Never hand-edit derived views**: if any derived docs/views are stale, regenerate via canonical scripts.

---

## Recommended Operating Model

### Prefer “session-style” orchestration

Phase 8 is best executed as **manual, verification-heavy sessions** rather than the full multi-agent FC2 loop for each
checkbox. You *can* still use the FC2 run directory system, but keep runs:

- small
- bounded
- deterministic
- explicitly pinned

### Session Outputs

For each Phase 8 subphase session, produce:

- A short report file:
  - `docs/OPUS_REBUILD_FRAME_COMPARE/phase-8-<subphase>-report-YYYY-MM-DD.md`
- Any decision updates:
  - `docs/DECISIONS.md`
- Pinned artifact manifest updates (target file chosen by the plan; see 8.2)
- CI workflow updates as needed under `.github/workflows/`

Report files should include: artifact name, version, URL(s), sha256, license references, and the exact commands run.

---

## Subphase Guidance

### 8.1 Spec + Decisions (Docs-Only, No Downloads)

**Goal:** Lock the “shape” of the portable bundle and the policy decisions before pinning binaries.

Checklist items (from master checklist):
- Supported Windows versions
- Supported architectures
- Packaging strategy (embedded Python vs PyInstaller)
- Record baseline decisions in `docs/DECISIONS.md`
- Finalize SSOT bundle layout + env rules (`07-windows-portable-bundle/01-bundle-spec.md`, `02-support-matrix.md`)

**Best practice:**
- Keep this subphase *purely documentary*. Do not implement scripts yet.
- Prefer explicit “MUST/SHOULD/MAY” language for env rules.

**Decisions you must lock here (example format):**
- Windows versions: `10/11`
- Arch: `x64 baseline`; ARM64 as best-effort or explicitly deferred
- Bundle approach: embedded Python + venv-like site-packages vs PyInstaller
- Where configuration lives and how it is discovered
- How the launcher sets:
  - `PATH`
  - `PYTHONHOME` / `PYTHONPATH` (if applicable)
  - `VAPOURSYNTH_PLUGIN_PATH`
  - Any `FRAME_COMPARE_*` env vars required for “doctor”

**STOP conditions for 8.1:**
- Any decision is written as “TBD” or “we’ll decide later”.
- The bundle spec does not define deterministic paths.

---

### 8.2 Pinned Artifact Set (Pins + Hashes + Licenses)

**Goal:** Produce a complete manifest schema and a pinned list of artifacts required for the baseline bundle.

Checklist items:
- Define `manifest.json` schema (versions + sha256 + license notes)
- Pin and source Windows artifacts:
  - VapourSynth runtime (Windows)
  - Plugins: L-SMASH Works, vs-placebo, ffms2 (as applicable)
  - FFmpeg (Windows)

**Best practice:**
- The manifest schema must be stable and future-proof.
- Prefer explicit fields over implied meaning. Example fields:
  - `name`
  - `version`
  - `platform` (`windows`)
  - `arch` (`x64`, `arm64`)
  - `url`
  - `sha256`
  - `license` (SPDX id if possible)
  - `license_url`
  - `notes` (for provenance)

**How to instruct the AI agent:**
- “Search official sources, pick one artifact per dependency, record URL + sha256, and cite the upstream release.”
- Require the agent to include the sha256 computation method for any downloaded binary (CI-friendly).

**STOP conditions for 8.2:**
- Any artifact pin is missing sha256.
- Any artifact provenance is unclear (random mirrors without justification).
- License references are missing for redistributed binaries.

---

### 8.3 Bundle Assembly + Launch (PowerShell + Deterministic Layout)

**Goal:** Implement scripts that assemble the bundle deterministically from the manifest and launch it reliably.

Checklist items:
- Add Windows bundle assembly scripts (PowerShell)
- Add bundle launcher(s) that set PATH + `VAPOURSYNTH_PLUGIN_PATH` deterministically
- Ensure `frame-compare doctor --json` runs in the portable bundle

**Best practice for assembly scripts:**
- Make the assembly script idempotent:
  - Running it twice yields the same directory structure and hashes.
- Download step:
  - verify sha256 before extracting/installing
- Extraction step:
  - avoid non-deterministic timestamps where possible
- Output:
  - emit a final “bundle manifest” file in the output directory

**Launcher design tips:**
- Keep launcher logic minimal; do not embed decision logic.
- Explicitly set environment variables before invoking the bundled Python entrypoint.
- Use absolute paths derived from launcher location.

**Verification expectations:**
- Local smoke: run `frame-compare doctor --json` inside the assembled bundle directory (Windows).
- CI smoke: same command, same expected JSON structure.

**STOP conditions for 8.3:**
- Bundle layout does not match the SSOT bundle spec.
- Launcher relies on machine-global dependencies (system Python, random PATH state).

---

### 8.4 Windows CI + Smoke Verification

**Goal:** Codify the bundle build and smoke checks in CI so it is repeatable and reviewable.

Checklist items:
- Add Windows CI job to assemble portable bundle artifact
- Add Windows smoke checks:
  - `frame-compare doctor --json` exits 0
  - VS clip creation works
  - Tonemap does not raise (fallback allowed)

**Best practice:**
- CI should:
  - generate bundle
  - run smoke checks
  - upload artifact
  - optionally publish on tags

**Test scoping:**
- Smoke tests should be small and deterministic.
- “VS clip creation works” can be a minimal script that:
  - imports VapourSynth
  - creates a blank clip
  - exits 0
- “Tonemap does not raise” should be written so it passes even when optional GPU paths are unavailable, consistent with
  existing code/test policy (“fallback allowed”).

**STOP conditions for 8.4:**
- CI job is not pinned to the manifest artifacts.
- Smoke checks are flaky or depend on external network beyond pinned downloads.

---

## Phase 8 Quality Gate ✓ (When To Run It)

Only declare Phase 8 quality gate complete when:

- Bundle assembles deterministically from pinned artifacts
- Windows CI smoke checks pass
- Documentation published (install/run instructions + support matrix)

Best practice: treat this as a final “release candidate” validation session.

---

## How To Write Good AI Prompts For Phase 8

When instructing an AI agent, include:

- The exact checklist section title and bullet list being targeted
- “No latest” rule + pin requirements
- Required output files (manifest, decisions, scripts)
- The verification commands that must pass
- STOP conditions (missing sha256, missing licenses, non-deterministic paths)

Example prompt skeleton:

> You are implementing Phase 8.2 pinned artifacts. You MUST produce `manifest.json` schema and fill it with pinned
> URLs + sha256 + license references for Windows x64 baseline. STOP if any artifact lacks sha256 or official provenance.
> End with a report listing each artifact and its pin.
