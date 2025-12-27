# Module Dependency Graph

> **Module:** Architecture  
> **Version:** 1.0

---

## 1. Visual Dependency Graph

```text
                                ┌─────────────────┐
                                │   CLI Entry     │
                                │  (cli_entry.py) │
                                └────────┬────────┘
                                         │
                                         ▼
                                ┌─────────────────┐
                                │     Runner      │
                                │   (runner.py)   │
                                └────────┬────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
                    ▼                    ▼                    ▼
           ┌────────────────┐   ┌────────────────┐   ┌────────────────┐
           │   Preflight    │   │  Orchestration │   │    Progress    │
           │ (preflight.py) │   │ (coordinator)  │   │  (reporters)   │
           └───────┬────────┘   └───────┬────────┘   └────────────────┘
                   │                    │
                   ▼                    │
           ┌────────────────┐           │
           │    Config      │           │
           │  (config/)     │◀──────────┤
           └───────┬────────┘           │
                   │                    │
                   ▼                    ▼
           ┌───────────────────────────────────────┐
           │            Pipeline Phases            │
           ├───────────┬───────────┬───────────────┤
           │           │           │               │
           ▼           ▼           ▼               ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────┐
    │ Analysis │ │ Alignment│ │  Render  │ │  Publish    │
    │ (phase)  │ │ (phase)  │ │ (phase)  │ │  (phase)    │
    └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬──────┘
         │            │            │              │
         ▼            ▼            ▼              ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────┐
    │ analysis/│ │ services/│ │  render/ │ │  services/  │
    │ (module) │ │alignment │ │ (module) │ │  publishers │
    └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────────────┘
         │            │            │
         │            │            │
         └────────────┴────────────┘
                      │
                      ▼
              ┌────────────────┐
              │   VapourSynth  │
              │   (vs/)        │
              └────────┬───────┘
                       │
                       ▼
              ┌────────────────┐
              │   Utilities    │
              │   (utils/)     │
              │  - result.py   │
              │  - types.py    │
              │  - logging.py  │
              │  - progress.py │
              │  - paths.py    │
              │  - subproc.py  │
              └────────────────┘
```

---

## 2. Module Dependency Matrix

| Module | Depends On |
|--------|------------|
| **cli_entry** | runner, config, errors |
| **runner** | orchestration, config, errors |
| **orchestration** | vs, analysis, render, services, config, utils, errors |
| **config** | errors, utils |
| **analysis** | vs, config, utils, errors |
| **render** | vs, config, utils, errors |
| **services/alignment** | config, utils, errors |
| **services/dovi** | config, utils/subproc, errors |
| **services/metadata** | config, utils, errors |
| **services/publishers** | config, utils, errors |
| **services/report** | config, utils |
| **vs** | config, utils, errors |
| **utils** | (none - leaf) |
| **errors** | (none - leaf) |

---

## 3. Implementation Order

### Phase 0: Foundation (Build Order 0)

```text
errors.py          ← No dependencies (leaf module)
utils/result.py    ← errors (uses error types)
utils/types.py     ← errors (WorkspacePaths, RunMetrics)
utils/logging.py   ← errors (logs error context)
utils/paths.py     ← errors (PathEscapesRootError)
```

### Phase 1: Core Infrastructure (Build Order 1)

```text
config/schema.py   ← errors
config/loader.py   ← errors, utils
config/           ← Complete config module
```

### Phase 2: VapourSynth Layer (Build Order 2)

```text
vs/env.py          ← errors
vs/source.py       ← errors
vs/props.py        ← (none)
vs/color.py        ← props
vs/tonemap.py      ← env, color
vs/                ← Complete vs module
```

### Phase 3: Analysis (Build Order 3)

```text
analysis/types.py    ← (none)
analysis/metrics.py  ← vs, types, errors
analysis/selection.py← types
analysis/cache_io.py ← types, errors
analysis/            ← Complete analysis module
```

### Phase 4: Render (Build Order 4)

```text
render/types.py       ← (none)
render/geometry.py    ← (none)
render/naming.py      ← (none)
render/overlay.py     ← types
render/encoders.py    ← vs, types, errors
render/orchestrator.py← all above
render/               ← Complete render module
```

### Phase 5: Services (Build Order 5)

```text
services/types.py     ← (none)
services/alignment.py ← config, utils/subproc, errors
services/dovi.py      ← config, utils/subproc, errors
services/metadata.py  ← config, errors
services/publishers.py← config, errors
services/report.py    ← config
services/             ← Complete services module
```

### Phase 6: Orchestration (Build Order 6)

```text
orchestration/context.py    ← config, utils
orchestration/phases.py     ← analysis, render, services
orchestration/coordinator.py← phases, context
preflight.py                ← config, errors
doctor.py                   ← vs, config
runner.py                   ← orchestration, preflight
cli_entry.py                ← runner, doctor, config
```

---

## 4. Parallel Implementation Opportunities

Modules that can be implemented in parallel:

### Group A (after Phase 1)

- `analysis/` and `render/` can be developed in parallel
- Both depend on `vs/` and `config/`

### Group B (after Phase 2)

- `services/alignment` and `services/publishers` can be developed in parallel
- Neither depends on the other

### Group C (after Phase 3)

- `services/metadata` and `services/report` can be developed in parallel

---

## 5. Critical Path

```text
errors → config → vs → analysis → orchestration → cli_entry
                     └→ render ──┘
```

The critical path is **6 sequential dependencies**.

---

## 6. Import Contract Rules

### ✅ Allowed Imports

| From | Can Import |
|------|------------|
| cli_entry | Any module |
| runner | orchestration, config, preflight, progress |
| orchestration | analysis, render, services, config |
| analysis | vs, config, utils, errors |
| render | vs, config, utils, errors |
| services | config, utils, errors |
| vs | config, utils, errors |
| config | errors, utils |
| utils | errors only |
| errors | nothing |

### ❌ Forbidden Imports

| From | Cannot Import |
|------|---------------|
| errors | Any other module |
| utils | config, vs, analysis, render, services |
| config | vs, analysis, render, services, orchestration |
| vs | analysis, render, services, orchestration, cli |
| analysis | render, services, orchestration, cli |
| render | analysis, services, orchestration, cli |
| services | analysis, render, orchestration, cli |

---

## 7. import-linter Configuration

> [!NOTE]
> This block is synced from `scaffold/pyproject.toml`.
> Run `python scripts/generate_contract_views.py` to regenerate.

<!-- BEGIN GENERATED:importlinter -->
```toml
# pyproject.toml

[tool.importlinter]
root_package = "frame_compare"

[[tool.importlinter.contracts]]
name = "Layered Architecture"
type = "layers"
layers = [
    "frame_compare.cli_entry",
    "frame_compare.runner",
    "frame_compare.orchestration",
    "(frame_compare.analysis | frame_compare.render | frame_compare.services)",
    "frame_compare.vs",
    "frame_compare.config",
    "frame_compare.utils",
    "frame_compare.errors",
]

[[tool.importlinter.contracts]]
name = "No circular dependencies"
type = "independence"
modules = [
    "frame_compare.analysis",
    "frame_compare.render",
    "frame_compare.services",
]
```
<!-- END GENERATED:importlinter -->

---

## 8. Agent Implementation Notes

When implementing a module:

1. **Check dependencies first** — Make sure all upstream modules exist
2. **Start with types** — Define types.py before implementation
3. **Follow layer rules** — Never import from upper layers
4. **Run import-linter** — `uv run lint-imports` after each module
