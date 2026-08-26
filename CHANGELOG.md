# Changelog

All notable changes to Frame Compare will be documented in this file.

## Unreleased

## [0.2.0]

### Added

- Add previous-offset reuse controls (`disabled`, `prompt`, and `always`) with shared-cache identity, provenance, stability validation, interactive acceptance, and structured CLI errors.
- Add post-report slow.pics upload confirmation for interactive runs.
- Add a consent-gated, run-only full-window retry when configured lead/trail exclusions leave too little eligible media; authored configuration remains unchanged.
- Add report payload v1.2 with release-aware source identities, distinct comparison/source-frame domains, exact picture type and Dolby Vision RPU facts when observable, file-size context, rendering disclosures, and expanded Inspector, review, and viewport behavior.
- Add code-owned media-runtime identities and scoped fingerprints for analysis, probing, alignment, source indexing, cache invalidation, Docker, Windows portable, and code-only update compatibility.
- Add a guarded immutable release workflow with exact version, tag, and SHA validation; collision checks; draft and asset verification; remote digest checks; and artifact provenance attestations.
- Bundle Inter Regular under the SIL Open Font License 1.1 for deterministic overlay typography.

### Changed

- Bump Frame Compare to 0.2.0 and refresh the managed stack to Python 3.13.15, uv 0.12.5, VapourSynth R79/API R4.2, L-SMASH-Works 1296, vs-placebo 2.0.4, Akarin 1.4.1, and VSZip 22.1.0. Docker includes FFMS2 5.0; Windows portable intentionally excludes FFMS2.
- Make random, dark, bright, and motion frame selection deterministic and temporally stratified while preserving seed reproducibility, minimum-gap behavior, sparse source coordinates, category counts, and selection diagnostics.
- Classify alignment stability and strengthen shared reuse-cache identity and schema validation and previous-offset presentation.
- Improve CLI help, wizard, side-effect-free dry-run planning, chronological human progress output on stderr, JSON output contracts, warnings, and success summaries.
- Carry canonical exact-frame, signal, presentation, geometry, and tonemap facts through rendering, overlays, slow.pics upload planning, and reports.
- Strengthen Frame Compare-owned L-SMASH index naming and media-runtime-aware cache invalidation.
- Expand deterministic Docker and Windows portable runtime, packaging, installer, updater, rollback, provenance, license, and extracted-bundle verification.

### Fixed

- Merge FFprobe HDR color metadata field-by-field only when VapourSynth frame properties are missing, malformed, or H.273-unspecified.
- Capture FFmpeg picture type from the same exact-frame extraction process used to produce the screenshot.
- Improve recoverable selection failures, source-frame range handling, and post-retry fatal error behavior.
- Harden VSPreview startup compatibility checks and redact inherited credential values from surfaced startup diagnostics.

### Security

- Require signed Windows code-only updates to match both dependency and media-runtime fingerprints before replacement, with file-hash verification, backups, and rollback.
- Verify pinned source commits with complete tracked-tree SHA-256 digests and preserve native-library, plugin-manifest, license, and corresponding-source provenance.
- Validate ZIP path safety, case collisions, required bundle contents, bounded process evidence, release asset checksums, remote digests, and publication state before release.

### Upgrade notes

- Windows v0.1.0 portable installations require the complete v0.2.0 bundle because the managed media-runtime fingerprint changed; the code-only updater refuses incompatible runtimes.
- Analysis, probe, alignment, and source-index caches include updated runtime identities and may be invalidated or rebuilt.
- Existing v1.1 reports remain self-contained; regenerated v1.2 reports start with fresh browser-local viewer and review state.
