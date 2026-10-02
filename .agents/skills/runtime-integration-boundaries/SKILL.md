---
name: runtime-integration-boundaries
description: Protect Frame Compare external execution and transport contracts for FFmpeg, VapourSynth/VSView, HTTP, browser launch, Docker, packaging, and updates. Use when boundary behavior or platform assumptions change.
---

# Runtime Integration Boundaries

Keep subprocess, HTTP, runtime metadata, packaging, and platform policy in their
documented owners. Use argument arrays, explicit timeouts, bounded retries, typed
results, deterministic cleanup, and redacted errors. Treat malformed metadata and
partial external output as real cases; do not silently invent fallback semantics.

Preserve lazy CLI imports and first-class Docker/Windows behavior. Verify through the
real boundary where available. If the current host cannot execute a platform path,
record it as unverified rather than inferring success from source.

Choose proof from the changed external call, not its directory: analysis metrics
and audio alignment also invoke native media tools, and VSView has a separate
plugin/process/UI boundary. Use the runbook's Python, Docker/native, report-browser,
distribution, or Windows route. A skipped test or an untriggered CI job is not proof.
Keep transport details in the current architecture's External Boundaries section;
the isolated webhook transport must not inherit the publishing client's state.
