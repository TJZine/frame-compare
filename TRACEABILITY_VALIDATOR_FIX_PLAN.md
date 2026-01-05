# Traceability Validator Fix Plan (Standalone)

> **Goal:** Make `scripts/validate_traceability.py --check` a reliable design-time consistency gate after adding Phase 6 subphases / Phase 8, without requiring churny manual “stub everything” workarounds.
>
> **Scope:** Planning only. This document is not a run artifact and does not create `.agent-workflow/` entries.

---

## 0) Optional Implementation Persona (Recommended)

If you delegate this plan to an agent, use this persona to prevent scope creep:

- **Persona:** “Maintenance Engineer (Determinism-First)”
- **Primary objective:** Fix `scripts/validate_traceability.py` so it matches the traceability matrix’s intent and produces deterministic, debuggable output.
- **Hard constraints:**
  - Do not change semantics of requirements in `requirements-traceability.md`.
  - Do not add bulk scaffold stubs as a workaround (only add stubs for remaining *PLANNED* refs per §3).
  - Do not refactor unrelated code or reformat unrelated files.
  - Do not require network.
- **Stop conditions:**
  - If parsing rules in §1.2–§1.5 cannot be implemented without changing the matrix format, stop and propose a matrix-format extension explicitly (do not silently change behavior).

## 0) Current Observations (Fact Base)

### 0.1 Repro command and current failure

Run:

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
```

Current failure highlights:

- **False module-spec failure:** `plan-module.md NOT FOUND` even though the matrix contains `frame-plan-module.md`.
- **Many missing tests:** Validator reports `test_loader`, `test_cache_io`, etc. “NOT FOUND in scaffold tests”.

### 0.2 Root causes in the current validator implementation

File: `scripts/validate_traceability.py`

1. **Incorrect module spec regex**
   - Current: `([a-z]+-module\.md)`
   - Effect: `frame-plan-module.md` is incorrectly reduced to `plan-module.md`.

2. **Incorrect test reference extraction**
   - Current: extracts tokens like `test_loader` from file paths like ``tests/vs/test_loader.py``.
   - Then validates *only* by searching for `def test_loader` in `docs/.../scaffold/tests/**`.
   - This mismatches the matrix, which primarily references real repo tests under `tests/**`.

3. **Buggy test function matching**
   - Current: substring check `if f"def {test_name}" in content`.
   - Effect: false positives (e.g. `test_report` “found” because `def test_report_html` exists).

---

## 1) Design Constraints (No Decisions Left for Implementer)

### 1.1 Source of truth

- The matrix is: `docs/OPUS_REBUILD_FRAME_COMPARE/02-requirements/requirements-traceability.md`
- Module specs live in: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/`
- Real tests live in: `tests/`
- Scaffold tests live in: `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/`

### 1.2 Parsing rule (MUST implement exactly)

The validator MUST only consider **inline code spans** (backticks) in the traceability document as references.

- Parse every line of `requirements-traceability.md`
- For each line, extract all code spans with:
  - Regex (Python): `r"`([^`]+)`"`
- Each extracted code span is a candidate reference.

**Normalization (MUST implement exactly):**

For each extracted `ref` string:

1. Strip leading/trailing whitespace: `ref = ref.strip()`.
2. Normalize path separators for test refs:
   - If `ref` starts with `tests\\`, replace backslashes with slashes.
   - If `ref` contains `\\` anywhere, replace `\\` with `/`.
3. Do not otherwise modify case or content.

**Duplicate handling (MUST implement exactly):**

- Keep a `set` of `(kind, ref, planned)` triples to avoid duplicate validations.
- If duplicates occur on different line numbers, keep the lowest `line_no` for reporting.

### 1.3 Reference classification (MUST implement exactly)

Given a code span content `ref`:

1. **Module spec reference**
   - If it matches this full-filename regex:
     - `r"^[a-z0-9]+(?:-[a-z0-9]+)*-module\.md$"`
   - Validate existence at:
     - `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/<ref>`

2. **Test file or test function reference**
   - If it starts with `tests/` and ends with `.py`, optionally with `::test_name`.
   - Valid forms:
     - `tests/<...>/test_*.py`
     - `tests/<...>/test_*.py::test_<...>`

3. **Everything else**
   - Ignore for traceability validation (do not fail; do not print).
   - Rationale: the traceability doc contains other code spans (flags, commands, etc.) that are not artifacts.

### 1.4 Planned vs implemented policy (MUST implement exactly)

For a test reference, compute:

- `planned = "PLANNED:" in line_text_before_this_code_span`
  - Implementation rule: for each line, if the substring `PLANNED:` appears anywhere on that line *before* the backtick that opened this code span, treat it as planned.

Validation behavior:

- If `planned == False`: validate in the real test tree (`<repo_root>/<ref_path>`).
- If `planned == True`: validate in **either** location (first match wins):
  1. `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/<ref_path_relative_to_tests/>`
  2. `<repo_root>/<ref_path>`

This rule avoids additional status churn in the matrix when a “planned” test becomes implemented early.

**Multi-code-span lines (MUST implement exactly):**

If a line contains multiple code spans, compute `planned` independently for each code span using “text before the opening backtick for that specific code span”.

### 1.5 Test file vs test function validation (MUST implement exactly)

For a test reference:

- If reference is `tests/.../file.py` (no `::`):
  - Existence check only: file must exist per planned/implemented policy.
  - Do NOT attempt to infer or validate a specific test function name.

- If reference is `tests/.../file.py::test_func`:
  - File must exist per planned/implemented policy, AND the file must contain a function definition:
    - Regex (Python, multiline): `rf"(?m)^def\\s+{re.escape(test_func)}\\s*\\("`
  - Note: allow leading whitespace before `def` (optional). Recommended strict version:
    - `rf"(?m)^\\s*def\\s+{re.escape(test_func)}\\s*\\("`

---

## 2) Exact Implementation Tasks

### 2.1 Update validator: parsing + classification

File: `scripts/validate_traceability.py`

Replace `extract_module_refs()` and `extract_test_refs()` with a unified extractor that returns structured refs:

- Input: entire traceability markdown as `list[str]` lines
- Output: list of dicts (or a small `@dataclass`) with:
  - `kind`: `"module_spec"` or `"test"`
  - `ref`: original code span string (e.g. `frame-plan-module.md`, `tests/cli/test_cli_commands.py::test_run_stub_executes`)
  - `planned`: `bool` (only meaningful for `kind="test"`)
  - `line_no`: `int` (1-based) for better error messages

MUST implement classification rules in §1.3 and planned policy in §1.4.

### 2.2 Fix module spec regex bug

Do NOT use `([a-z]+-module\.md)`.

Use the full-filename regex in §1.3.1:

- `r"^[a-z0-9]+(?:-[a-z0-9]+)*-module\.md$"`

This makes `frame-plan-module.md` valid and eliminates the `plan-module.md` false failure.

### 2.3 Replace test validation logic

Remove the existing `extract_test_refs()` and `validate_test()` logic that:
- extracts bare `test_*` tokens, and
- searches for `def test_*` only in `docs/.../scaffold/tests`.

Replace with:

1. Parse `tests/...` path references (with optional `::test_func`).
2. Resolve a candidate file path according to §1.4.
3. Validate file existence and optionally the `::test_func` definition according to §1.5.

### 2.4 Output requirements (MUST implement exactly)

The script’s printed output MUST remain human-friendly and deterministic:

- Print `Validating module spec references...` then lines in deterministic sorted order by `ref`.
- Print `Validating test references...` then lines in deterministic sorted order by `ref`.
- Each failure line MUST include:
  - the missing reference
  - the expected path(s) that were checked
  - line number in `requirements-traceability.md`

Exit codes remain:
- `0` success
- `1` missing references

**Deterministic ordering (MUST implement exactly):**

- When printing validation lines, sort by:
  1. `kind` (`module_spec` first, then `test`)
  2. `ref` (case-sensitive string sort)
  3. `planned` (`False` before `True` for readability)

### 2.5 Backwards compatibility requirements (MUST implement exactly)

- Keep CLI: `python scripts/validate_traceability.py` and `--check` behavior.
- Keep file locations as currently defined at top of script, but add:
  - `REPO_TESTS_DIR = PROJECT_ROOT / "tests"`

### 2.6 Implementation sketch (MUST follow; no alternative designs)

This sketch is the intended control flow. Implement it directly.

1. Read `requirements-traceability.md` as `lines = TRACEABILITY_PATH.read_text().splitlines()`.
2. For each line `i, line in enumerate(lines, start=1)`:
   - Find all code spans and their start indices with `re.finditer(r"`([^`]+)`", line)`.
   - For each match:
     - `ref = match.group(1).strip()`
     - `prefix = line[:match.start()]`
     - Determine `planned` per §1.4 (only meaningful for tests).
     - Classify `ref` per §1.3:
       - If module spec, emit a `module_spec` ref object with `planned=False`.
       - If tests ref, emit a `test` ref object with `planned=<computed>`.
3. Deduplicate per §1.2 and keep lowest `line_no`.
4. Validate:
   - For each `module_spec` ref:
     - Check `MODULE_SPECS_DIR / ref` exists.
   - For each `test` ref:
     - Parse `ref` into `path_part` and optional `func_part` by splitting on `::` once.
     - Determine candidate filesystem paths to check:
       - Implemented: `[PROJECT_ROOT / path_part]`
       - Planned: `[SCAFFOLD_TESTS_DIR / path_part.removeprefix("tests/"), PROJECT_ROOT / path_part]`
     - Select the first existing file; if none exist, fail with a message listing all candidates.
     - If `func_part` exists, validate exact function definition using §1.5 regex.
5. Print sections and summary; exit `1` iff any failures.

### 2.7 Error message templates (MUST implement exactly)

Use these exact message shapes so failures are easy to grep:

- Module spec missing:
  - `✗ <ref> NOT FOUND (line <N>): expected <full_path>`
- Test file missing:
  - `✗ <ref> NOT FOUND (line <N>): checked <path1>, <path2>`
- Test function missing:
  - `✗ <ref> NOT FOUND (line <N>): function <test_func> missing in <resolved_file_path>`

---

## 3) Scaffold Changes (Only If Needed)

This section is intentionally minimal because the validator should validate real tests for non-PLANNED items.

### 3.1 After implementing the validator changes, run:

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
```

If any remaining failures are for **PLANNED** `tests/...` refs that exist nowhere:

Create scaffold stubs under:

`docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/<same relative path under tests/>`

Example:

- Matrix contains: `PLANNED: `tests/render/test_tonemap_wiring.py``
- Create: `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/render/test_tonemap_wiring.py`

Stub file template (exact):

```python
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Traceability stub: planned test not implemented yet")


def test_tonemap_wiring() -> None:
    pass
```

Do NOT add unplanned stub trees (no bulk file creation); only add stubs for remaining *planned* references that do not exist in real tests.

### 3.2 Canonical stub placement rule (MUST implement exactly if stubs are added)

If the matrix references `PLANNED: `tests/<A>/<B>/test_x.py`` then the stub must be created at:

- `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/<A>/<B>/test_x.py`

Do not create any other stub location(s).

---

## 4) Acceptance Criteria (Must All Pass)

1. `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check` exits `0`.
2. The validator no longer reports `plan-module.md` (it correctly validates `frame-plan-module.md`).
3. For implemented features, the validator validates against `tests/**` rather than requiring `docs/.../scaffold/tests/**`.
4. For `PLANNED:` tests, the validator accepts either a scaffold stub or an implemented real test file.
5. No substring false positives:
   - Example: `test_report` must NOT be satisfied by `test_report_html`; only exact `def test_report(` counts when a `::test_report` reference exists.

---

## 5) Verification Commands (Exact)

```bash
# Core check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check

# Keep repo gates healthy
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
```

---

## 6) Notes / Non-Goals

- Do NOT “fix” the matrix by replacing `frame-plan-module.md` with `plan-module.md`. That is a validator bug.
- Do NOT mass-create scaffold stubs for every test name; the validator should validate real repo tests for implemented items.
- This plan does not change Phase structure or checklist content; it only makes the traceability gate robust.

## 7) Known Edge Cases (Decided Upfront)

These are pre-decided so the implementer does not have to choose behavior:

1. **Markdown code spans inside links:** still treated as code spans if they use backticks (common in tables). No special handling required beyond §1.2.
2. **Multiple tests in one code span:** not supported. If a code span contains commas/spaces (e.g., `tests/a.py, tests/b.py`), it is ignored (falls under “everything else” in §1.3.3).
3. **Non-test python files under tests/**: if referenced and ends with `.py`, it is treated as a test artifact and existence-checked (function existence only checked when `::` is present).
4. **Case sensitivity:** do not normalize case. On case-sensitive filesystems a mismatch is a real failure.

## 8) Documentation Addendum (So Humans Don’t Fight the Tool)

Add a short “How to update the matrix without breaking validation” note to:

- `docs/OPUS_REBUILD_FRAME_COMPARE/02-requirements/requirements-traceability.md` (append near top)

Content requirements (MUST implement exactly):

- “Only references in backticks are validated.”
- “Use full module spec filenames (e.g. `frame-plan-module.md`).”
- “For tests, use `tests/.../file.py` or `tests/.../file.py::test_func`.”
- “Prefix planned artifacts with `PLANNED:` on the same line before the backtick.”

This reduces future traceability churn when phases/subphases are edited.

## 9) Rollback Plan (Pre-Decided)

If the validator change causes unexpected failures in CI:

1. Revert only `scripts/validate_traceability.py` and `tests/test_validate_traceability.py`.
2. Do NOT revert `requirements-traceability.md` edits unless they were strictly for the addendum in §9.
3. Re-run:
   - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check`
   - `.venv/bin/pytest -q`
