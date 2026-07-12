---
name: runtime-integration-boundaries
description: Use for Frame Compare FFmpeg, ffprobe, VapourSynth, TMDB, slow.pics, Docker, browser-open, Windows portable, or release integration logic.
---

# Runtime Integration Boundaries

Keep subprocess, HTTP, runtime metadata, packaging, and platform policy in their
documented owners. Use argument arrays, explicit timeouts, bounded retries, typed
results, deterministic cleanup, and redacted errors. Treat malformed metadata and
partial external output as real cases; do not silently invent fallback semantics.

Preserve lazy CLI imports and first-class Docker/Windows behavior. Verify through the
real boundary where available. If the current host cannot execute a platform path,
record it as unverified rather than inferring success from source.

Use the runbook's focused, full, Docker, or Windows gate according to the changed
surface.
