---
description: What a run writes to the generated-data root and which files you can move or delete.
---

# Output layout

Frame Compare writes files beneath one configured generated-data root. A normal run
keeps its report, screenshots, metadata, and result record together. Runs share caches
that Frame Compare can reuse.

## Canonical layout

```text
<generated-data-root>/
├── cache/
│   ├── analysis/
│   │   └── <source-and-request-identity>.compframes
│   ├── alignment/
│   │   └── alignment_reuse.toml
│   └── tmdb.toml
├── clip_probe.toml
└── <run-name>/
    ├── report.html
    ├── screenshots/
    │   └── <frame> - <source-stem>.png
    ├── alignment_diagnostics/
    │   └── comparison-<n>.json
    ├── generated/
    │   ├── clip_probe.toml
    │   └── vsview_sessions/
    ├── run_info.toml
    └── run_result.toml
```

The intermediate files in a run folder vary with the enabled features. Write scripts
that rely only on documented artifacts.

## Ownership

| Path | Owner and purpose |
| --- | --- |
| `cache/analysis/` | Reusable luminance and motion metrics keyed by the effective metric request and runtime identity |
| `cache/alignment/` | Reusable applied source offsets |
| `cache/tmdb.toml` | Bounded reusable TMDB search and alternative-title responses; contains no API key or final match decision |
| `clip_probe.toml` | Shared compatible source-probe evidence |
| `<run>/report.html` | Canonical offline report entry point |
| `<run>/screenshots/` | Rendered comparison images referenced by the normal report |
| `<run>/generated/` | Run-local generated state and intermediates |
| `<run>/alignment_diagnostics/` | Per-comparison alignment evidence; diagnostic only |
| `<run>/generated/vsview_sessions/` | Generated VSView sessions and their saved panel results |
| `<run>/run_info.toml` | Write-only run identity and provenance recorded at reservation |
| `<run>/run_result.toml` | Completed or failed lifecycle record used by history |

Files ending in `.lock` coordinate concurrent writers; leave them alone.

Frame Compare writes its L-SMASH-Works `.lwi` indexes beside each source. Their filename
includes a runtime-scoped token. Frame Compare does not adopt ambiguous legacy
`<media>.lwi` files.

When media is mounted read-only, as on the default Docker route, no index file can be
written. A usable existing Frame Compare-owned index can still be reused. If no usable
index is available and index construction fails, the cache-free fallback rebuilds it
in memory each time the source loads; see [Docker](../getting-started/docker.md#the-index-warning).

## Portability

To move or archive one comparison:

<div class="fc-steps" markdown>

1. **Copy the complete reserved run folder.**
2. **Keep `report.html` and `screenshots/` in their relative positions.**
3. **Remember that browser-local review notes are not files in the run folder.**
4. **Use embedded images only when a single-file artifact is required.**

</div>

Shared caches are not required to view an existing report.

The TMDB cache can reveal previously resolved media titles even though its lookup keys
do not store plain query text. Delete `cache/tmdb.toml` to remove that history or force
fresh metadata requests; Frame Compare recreates it as successful lookups occur.

## Windows portable persistence

The default generated-data root can be inside the bundle. Choose an external normal
user directory when results must survive bundle replacement. The updater, rollback,
reinstall flow, and uninstaller preserve that external root.

Moving source media or the bundle can change path-based cache identity. Existing reports
remain viewable as long as their run folder is intact.

## Docker persistence

The default Compose route binds the host `generated/` directory to
`/workspace/generated`. Reports, screenshots, lifecycle records, and shared caches remain
on the host after the container exits.

Mount a custom container path to a host-owned location to preserve its files.

## Cache identity caveat

For performance, Frame Compare checks source freshness by path, size, and modification
time. It does
not hash the full source file. Frame Compare considers a replacement that preserves
all three to be the same source. Advance the modification time or clear the relevant
cache when such a replacement occurs.

For exact schemas and persistence behavior, see [Current architecture](../current-architecture.md)
and the [CLI behavioral contract](../current-cli-contract.md).
