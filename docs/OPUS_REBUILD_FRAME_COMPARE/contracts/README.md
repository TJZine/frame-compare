# Contract Files

> **Source of Truth**: Canonical YAML/JSON contract definitions for Frame Compare 2.0

---

## Files

| File | Purpose | Derived Views |
|:-----|:--------|:--------------|
| `cli_flags.yaml` | CLI flag definitions | cli-flags-canonical.md, `cli/_generated.py` |
| `error_codes.yaml` | Error code registry | error-codes.md |
| `error_output_schema.json` | JSON error envelope schema | *(validated by tests)* |
| `config_schema.json` | Config field inventory | config-reference.md (Field Inventory block) |
| `phase_ordering.yaml` | Pipeline phase execution order | orchestration-module.md (reference) |
| `doctor_report_schema.json` | `doctor --json` output schema | *(pending test)* |

---

## Regeneration

Run from project root:

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py          # Regenerate all derived views
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check  # CI check (exit 1 if stale)
```

**Generated files:**

- `05-implementation/cli-flags-canonical.md`
- `05-implementation/error-codes.md`
- `05-implementation/config-reference.md` (Field Inventory block only)
- `03-architecture/dependency-graph.md` (import-linter block only)
- `scaffold/src/frame_compare/cli/_generated.py`

---

## Contract Authority Map

| Domain | Canonical Source | Derived View(s) | Generator |
|:-------|:-----------------|:----------------|:----------|
| CLI Flags | `cli_flags.yaml` | `cli-flags-canonical.md`, `cli/_generated.py` | `generate_contract_views.py` |
| Error Codes | `error_codes.yaml` | `error-codes.md` | `generate_contract_views.py` |
| Error Output | `error_output_schema.json` | — (validated by tests) | — |
| Config Schema | `config_schema.json` | `config-reference.md` (Field Inventory block) | `generate_contract_views.py` |
| Import Layers | `scaffold/pyproject.toml` | `dependency-graph.md` (layers block) | `generate_contract_views.py` |
| Phase Ordering | `phase_ordering.yaml` | — (documentation reference) | — |
| Doctor Report | `doctor_report_schema.json` | — (validated by tests) | — |

### Authority Rules

- **Canonical sources**: Files in this directory are the **single source of truth**
- **Derived views**: Markdown docs and `_generated.py` are regenerated from these
- **Never edit derived blocks**: Edit canonical YAML/JSON, then regenerate
- **Sentinel markers**: Generated blocks are wrapped in `<!-- BEGIN/END GENERATED:name -->`
- **Freshness check**: CI runs `--check` to fail if derived views are stale

---

## Contract Evolution Policy

### Additive Changes (non-breaking)

1. Add new fields/flags/errors to canonical YAML/JSON
2. Run `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py` to regenerate derived views
3. **No test edits needed** — contract tests compare against canonical files

### Breaking Changes

1. Bump contract version in the affected file
2. Update schema/YAML with new structure
3. Regenerate derived views
4. Update test expectations **once** (in the test file that failed)

### Best Practices

- Prefer "presence + type + stable IDs" over exact counts or ordering
- Enforce strictness via canonical files + generator freshness, not ad-hoc assertions
- Use sentinel markers (`<!-- BEGIN GENERATED:name -->`) for generated blocks
- Keep contract tests focused on interfaces and invariants, not incidental structure
