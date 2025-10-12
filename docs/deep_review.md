# Deep code review status (2025-10-11)

This memo updates the prior deep-dive report with the current
state of the codebase. Each section lists the check outcome and
recommended follow-up, if any.

## CRITICAL: Screenshot cleanup can delete arbitrary directories
**File:** frame_compare.py:3099-3650
**Risk Level:** HIGH
**Impact:** Misconfiguring `screenshots.directory_name` (or a malicious config) can point `out_dir` at any writable path; when slow.pics upload succeeds the default `delete_screen_dir_after_upload` branch recursively deletes that path. In the worst case this wipes the entire input root or another critical directory (for example `..` resolves to the parent), causing catastrophic data loss on every run.
**Evidence:** `out_dir` is resolved without constraint from the configured directory name and later passed directly to `shutil.rmtree` when cleanup runs, while the default config enables that cleanup automatically.【F:frame_compare.py†L3099-L3116】【F:frame_compare.py†L3633-L3650】【F:src/datatypes.py†L36-L95】
**Fix Required:** Normalize the configured directory name and reject absolute paths or segments that escape the input root (e.g. use `Path.is_relative_to`/`os.path.commonpath`) before creating or deleting directories. Guard the deletion branch with an assertion that `out_dir` is a directory descendant of `root` and, ideally, store the actual creation target so only managed paths are removed.
**Timeline:** Immediate

This validation should also cover the audio-alignment preview folder, which currently derives from the same unbounded `screenshots.directory_name` and writes to a resolved path under `root` without confirming containment.【F:frame_compare.py†L2060-L2076】

## Security

### ✅ CLI layout expression sandbox

`CliLayoutRenderer` now parses expressions with `ast.parse`,
validates every node via `_validate_safe_expression`, and executes
in a namespace that only exposes `resolve`, `abs`, `min`, and
`max`. `LayoutContext.resolve` rejects path segments containing
underscores, preventing access to dunder attributes or private
members. Together these guardrails block the arbitrary code
execution scenario highlighted in the earlier review.
【F:src/cli_layout.py†L16-L115】【F:src/cli_layout.py†L492-L537】【F:src/cli_layout.py†L969-L1040】

**Next steps:** Document in contributor guidelines that layout
files remain trusted configuration. The sandbox protects against
opportunistic payloads but does not eliminate the need to vet
custom layouts distributed with releases.

## Performance

### ✅ TMDB cache bounding

`src/tmdb.py` now ships a bounded `_TTLCache` that evicts entries
when the configured `max_entries` limit is exceeded. The cache is
also exposed through `cache_max_entries` in `TMDBConfig`, allowing
operators to shrink it for memory-constrained environments.
【F:src/tmdb.py†L1-L120】

### ⚠️ Close slow.pics sessions after upload

`upload_comparison` constructs a long-lived `requests.Session`
but never closes it, which can leak sockets for hosts that chain
multiple uploads in one process. Wrapping the session in a
context manager or calling `session.close()` in a `finally` block
would tidy resources after each run.
【F:src/slowpics.py†L267-L311】

## Reliability

### ✅ Scoped audio-alignment warning suppression

Instead of muting NumPy warnings globally, the audio alignment
module confines suppression to `_suppress_flush_to_zero_warning`,
which wraps the specific operations that emit the noisy advisory.
Other parts of the application therefore keep their diagnostics.
【F:src/audio_alignment.py†L1-L44】

## Follow-up checklist

- [ ] Decide whether to add a helper that closes the slow.pics
  `requests.Session` once uploads finish.
- [ ] Call out layout file trust expectations in the contributor
  docs so downstream users understand the sandbox boundary.
