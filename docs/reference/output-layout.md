# Output layout

Frame Compare writes generated state beneath one configured generated-data root. A
normal run keeps its report, screenshots, metadata, and lifecycle result together while
sharing only explicitly reusable cache state across runs.

## Canonical layout

```text
<generated-data-root>/
├── cache/
│   ├── analysis/
│   │   └── <source-and-request-identity>.compframes
│   └── alignment/
│       └── alignment_reuse.toml
├── clip_probe.toml
└── <reserved-run-name>/
    ├── report.html
    ├── screenshots/
    │   └── <frame-and-source>.png
    ├── generated/
    │   └── <run-local intermediates>
    ├── run_info.toml
    └── run_result.toml
```

The exact set of run-local intermediates can vary by enabled features. Scripts should
rely only on documented artifacts rather than assuming every internal file is stable.

## Ownership

| Path | Owner and purpose |
| --- | --- |
| `cache/analysis/` | Reusable luminance and motion metrics keyed by the effective metric request and runtime identity |
| `cache/alignment/` | Reusable accepted source offsets |
| `clip_probe.toml` | Shared compatible source-probe evidence |
| `<run>/report.html` | Canonical offline report entry point |
| `<run>/screenshots/` | Rendered comparison images referenced by the normal report |
| `<run>/generated/` | Run-local generated state and intermediates |
| `<run>/run_info.toml` | Write-only run identity and provenance recorded at reservation |
| `<run>/run_result.toml` | Completed or failed lifecycle record used by history |

Frame Compare-owned L-SMASH-Works `.lwi` indexes are adjacent to the media source rather
than beneath this root. Their filename includes a runtime-scoped token. Ambiguous legacy
`<media>.lwi` files are not silently adopted.

## Portability

To move or archive one comparison:

- copy the complete reserved run folder;
- keep `report.html` and `screenshots/` in their relative positions;
- remember that browser-local review notes are not files in the run folder;
- use embedded images only when a single-file artifact is required.

Shared caches are not required to view an existing report.

## Windows portable persistence

The default generated-data location can be inside the bundle, but an external normal
user directory is recommended when results must survive bundle replacement. The updater,
rollback, reinstall flow, and uninstaller leave that external root outside their managed
replacement boundary.

Moving source media or the bundle can change path-based cache identity. Existing reports
remain viewable as long as their run folder is intact.

## Docker persistence

The default Compose route binds the host `generated/` directory to
`/workspace/generated`. Reports, screenshots, lifecycle records, and shared caches remain
on the host after the container exits.

A custom container path is durable only when it is explicitly mounted to a host-owned
location.

## Cache identity caveat

Source freshness is performance-first: path, size, and modification time are used rather
than hashing the full media file. A replacement that preserves all three is intentionally
considered the same source. Advance the modification time or clear the relevant cache
when such a replacement occurs.

For exact schemas and persistence behavior, see [Current Architecture](../current-architecture.md)
and the [CLI Behavioral Contract](../current-cli-contract.md).
