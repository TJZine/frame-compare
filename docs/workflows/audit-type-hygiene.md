---
description: Audit codebase for anti-pattern type suppressions and enforce best-practice refactoring
---

# Code Hygiene Audit: Type Suppression Anti-Patterns

## Purpose

Systematically identify and remediate instances where `# type: ignore`, `# pyright: ignore`, `# noqa`, or similar suppression comments were used as shortcuts instead of proper type-safe patterns.

## Scope

This audit covers:

1. **Type checker suppressions** (`# type: ignore`, `# pyright: ignore[...]`)
2. **Linter suppressions** (`# noqa: ...`, `# ruff: noqa`)
3. **Test-specific anti-patterns** (testing private functions directly)
4. **Unsafe casts and Any usage**
5. **Overly broad exception handling**

---

## Phase 1: Discovery

### 1.1 Find All Suppression Comments

```bash
# Type checker ignores
rg --no-heading -n "# type: ignore" src/ tests/
rg --no-heading -n "# pyright: ignore" src/ tests/

# Linter ignores
rg --no-heading -n "# noqa" src/ tests/
rg --no-heading -n "# ruff: noqa" src/ tests/

# Inline ignores in docstrings/strings (false positives, filter out)
rg --no-heading -n "pyright: ignore" src/ tests/ --type py
```

### 1.2 Find Private Function Imports in Tests

```bash
# Tests importing private functions (underscore prefix)
rg --no-heading -n "from .+ import .*\b_[a-z]" tests/
```

### 1.3 Find Unsafe Type Patterns

```bash
# Any usage (should be minimized)
rg --no-heading -n ": Any\b" src/

# Unsafe casts
rg --no-heading -n "cast\(" src/

# Overly broad exception handling
rg --no-heading -n "except Exception:" src/
rg --no-heading -n "except BaseException:" src/
```

### 1.4 Generate Inventory Report

Create a markdown file listing all findings:

```
Location | Suppression Type | Context | Priority
---------|------------------|---------|----------
... | ... | ... | ...
```

Priority levels:

- **P1 (Critical)**: In production code (`src/`), affects type safety
- **P2 (High)**: In production code, cosmetic or import-related
- **P3 (Medium)**: In test code, affects maintainability
- **P4 (Low)**: Justified suppressions (document why)

---

## Phase 2: Classification

For each finding, classify into one of these categories:

### Category A: Refactorable (Should Fix)

| Pattern | Best Practice Alternative |
|---------|---------------------------|
| Test imports private `_func` | Make function public OR test via public API |
| `# type: ignore` on return | Add proper return type annotation |
| `cast(Any, x)` | Define proper generic type |
| `# noqa: F401` unused import | Remove import OR add to `__all__` if re-export |
| `except Exception:` | Catch specific exceptions |

### Category B: Third-Party Quirks (Document)

| Pattern | Explanation |
|---------|-------------|
| Stubs missing for library | Document in `py.typed` or `pyproject.toml` |
| Library type is incorrect | Report upstream, suppress with explicit note |

### Category C: Intentional Escape Hatches (Keep with Justification)

| Pattern | Justification Required |
|---------|------------------------|
| Dynamic plugin loading | Link to ADR explaining pattern |
| Metaprogramming | Explain why types can't be inferred |
| Performance-critical paths | Benchmarks showing type overhead |

---

## Phase 3: Remediation Playbook

### 3.1 Private Function Imports in Tests

**Anti-pattern:**

```python
from my_module import _internal_helper  # pyright: ignore
```

**Best practice options:**

1. **Make it public** if it has a stable contract worth testing
2. **Test through public API** if it's truly internal
3. **Use module-level access** for edge cases:

   ```python
   from my_module import module
   result = module._internal_helper()  # Acceptable in tests
   ```

### 3.2 Dataclass Field Defaults

**Anti-pattern:**

```python
details: dict[str, Any] = field(default_factory=dict)  # Unknown types
```

**Best practice:**

```python
details: dict[str, JSONValue] = field(default_factory=lambda: {})
```

### 3.3 Import Cycles

**Anti-pattern:**

```python
if TYPE_CHECKING:
    from other import Thing
thing: "Thing"  # type: ignore[name-defined]
```

**Best practice:**

```python
from __future__ import annotations
if TYPE_CHECKING:
    from other import Thing
thing: Thing  # Works with PEP 563
```

### 3.4 Dynamic Attributes

**Anti-pattern:**

```python
obj.dynamic_attr  # type: ignore[attr-defined]
```

**Best practice:**

```python
# Use TypedDict, Protocol, or explicit getattr
attr = getattr(obj, "dynamic_attr", default)
```

### 3.5 Mocking in Tests

**Anti-pattern:**

```python
with patch.object(sys, "version_info", (3, 13, 0)):
    version.major  # type: ignore - tuple has no .major
```

**Best practice:**

```python
# Access via index (tuples are structurally typed)
version[0]  # major
```

---

## Phase 4: Execution Checklist

For each finding from Phase 1:

- [ ] **Identify pattern** — Which category (A/B/C)?
- [ ] **Determine fix** — Use playbook or document justification
- [ ] **Apply fix** — Refactor code
- [ ] **Verify** — Run `pyright --warnings` and `ruff check`
- [ ] **Document** — If Category B/C, add inline comment explaining why

---

## Phase 5: Verification Gates

After remediation, all these must pass:

```bash
# Type checking (zero errors, zero warnings)
.venv/bin/pyright --warnings

# Linting (no errors)
.venv/bin/ruff check .

# Tests (all pass)
.venv/bin/pytest -q

# Import layers (contracts kept)
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

---

## Phase 6: Prevention

### 6.1 Pre-commit Hook

Add to `.pre-commit-config.yaml`:

```yaml
- repo: local
  hooks:
    - id: no-blind-ignores
      name: Check for unjustified type ignores
      entry: bash -c 'rg "# (type|pyright): ignore(?!\[)" src/ && exit 1 || exit 0'
      language: system
      types: [python]
```

### 6.2 CI Check

Add to CI workflow:

```yaml
- name: Audit type suppressions
  run: |
    count=$(rg -c "# (type|pyright): ignore" src/ | awk -F: '{sum += $2} END {print sum}')
    if [ "$count" -gt 5 ]; then
      echo "::error::Too many type ignores in src/: $count (max 5)"
      exit 1
    fi
```

### 6.3 Documentation

Maintain a `docs/TYPE_SUPPRESSIONS.md` file documenting all justified suppressions:

```markdown
# Justified Type Suppressions

| File | Line | Suppression | Justification | Ticket |
|------|------|-------------|---------------|--------|
| src/x.py | 42 | pyright: ignore[...] | Third-party stub missing | #123 |
```

---

## Output Artifacts

1. `audit-findings.md` — Inventory of all findings
2. `audit-remediation.md` — Fixes applied with before/after
3. `docs/TYPE_SUPPRESSIONS.md` — Documented justified suppressions
4. Updated `.pre-commit-config.yaml` — Prevention hook
5. Updated `docs/DECISIONS.md` — ADR entry for audit

---

## Success Criteria

- [ ] Zero `# type: ignore` without explicit error code
- [ ] Zero `# pyright: ignore` without explicit error code
- [ ] All justified suppressions documented in `TYPE_SUPPRESSIONS.md`
- [ ] Pre-commit hook prevents new blind ignores
- [ ] CI gate limits total suppression count
