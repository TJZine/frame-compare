# Task: Harden VSPreview Helper Script for Windows Console Encodings (ASCII-only prints + UTF‑8-friendly I/O)

**Target branch:** `feature/vspreview-console-safe` → PR into `Develop`  
**Impacted area:** `frame_compare.py` (functions `_write_vspreview_script`, `_launch_vspreview`), generated `vspreview/*.py`, docs

---

## Why

On some Windows consoles (default code page `cp1252`), the auto-generated VSPreview helper script crashes when `print()` emits Unicode arrows (`→`, `↔`). The console tries to encode them with `cp1252`, raising:

```
UnicodeEncodeError: 'charmap' codec can't encode character '\u2194' in position ...
```

We must make the generated script **console-safe across encodings** without degrading behavior on UTF‑8 terminals.

---

## Objectives

1) **Replace non-ASCII glyphs** in **printed** messages with ASCII fallbacks (`->`, `<->`).  
2) **Add a defensive UTF‑8 stdout/stderr reconfiguration** in the generated script (best-effort, with `errors="replace"`), so any future stray non‑ASCII does not crash.  
3) **Keep the overlay/draw text unaffected** (glyphs inside video frames are fine).  
4) **Run and update type checks (Pyright/Pylance)** and **CI** to cover these code paths.  
5) **Update documentation** (README/CLI guide/Config/VSPreview section) per best practices.

---

## Best‑Practice Notes (self‑critique included)

- **Prefer ASCII in CLI stdout**: It’s a long‑standing portability best practice for cross‑platform CLIs. Unicode is fine, but only when terminals are guaranteed UTF‑8. We don’t control VSPreview’s run environment, so **ASCII for prints** avoids fragile assumptions.  
  - *Critique:* We lose pretty arrows in the console. This is acceptable; clarity and reliability trump ornamentation in logs.

- **`sys.stdout.reconfigure(encoding="utf-8", errors="replace")`**: As a **belt-and-suspenders** fallback in the generated script.  
  - *Critique:* Mutating global streams can surprise embedders. Here the script is a disposable helper launched for interactive inspection; risk is minimal. We set `errors="replace"` to avoid hard failures, not `ignore` to preserve maximum meaning.

- **Avoid adding a site‑wide environment dependency** (`PYTHONUTF8=1`, `PYTHONIOENCODING`):  
  - *Critique:* Env toggles are brittle across shells/launchers. Fixing the generated script itself is more robust and self‑contained.

- **No encoding cookie needed**: Python 3 sources default to UTF‑8; our script template contains only ASCII after this change.  
  - *Critique:* If future edits add non‑ASCII literals, the UTF‑8 default still handles it; plus our reconfigure fallback guards prints.

- **Tests**: Include a Windows job that **forces a legacy code page** and validates the script **does not crash**.  
  - *Critique:* Simulating exact VSPreview runtime is hard in CI. We unit‑test the sanitizer and a tiny surrogate script to exercise `print()` behavior under `cp1252` and `utf‑8` code pages.

---

## Implementation Plan

### A. Patch the generated script template (inside `_write_vspreview_script()`)

1) **Add safe I/O reconfigure** after imports in the generated script:

```python
try:
    import sys
    # Prefer UTF-8 on Windows; never crash on stray glyphs.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
```

2) **Replace Unicode arrows in printed strings with ASCII** (only for `print()` lines; do NOT touch overlay text drawn into frames):

- Change:
  - `"Adjusted FPS for target '%s' to match reference (%s/%s → %s/%s)"`
  - `"VSPreview outputs: reference on even slots, target on odd slots (0↔1, 2↔3, ...)."`

- To:
  - `"Adjusted FPS for target '%s' to match reference (%s/%s -> %s/%s)"`
  - `"VSPreview outputs: reference on even slots, target on odd slots (0<->1, 2<->3, ...)."`

3) **Optional:** Define a tiny helper in the generated script to future‑proof prints (kept simple, local, and ASCII‑first):

```python
def safe_print(msg: str) -> None:
    try:
        print(msg)
    except Exception:
        # Last‑chance: ensure we never raise due to encoding.
        try:
            print(msg.encode("utf-8", "replace").decode("utf-8", "replace"))
        except Exception:
            print("[log message unavailable due to encoding]")
```

Then use `safe_print(...)` for the two user‑facing lines.

> **Note:** Keep this helper **inside the generated script only**, not library code.

---

## Exact Edits (search/replace cues)

> File: `frame_compare.py`  
> Sections: `_write_vspreview_script` (≈ lines 3040–3317), `_launch_vspreview` (≈ lines 3620–3651)

- **Insert** the `reconfigure(...)` block into the generated script body right after its imports.  
- **Replace** glyphs in the two `print(...)` messages as shown above.  
- **(Optional)** Wrap those prints with `safe_print(...)` from the snippet.

---

## Type Checking & Linting

### Pyright (and Pylance) configuration

- Create **`pyrightconfig.json`** at repo root (if absent):

```json
{
  "$schema": "https://raw.githubusercontent.com/microsoft/pyright/main/packages/pyright/schema/pyrightconfig.schema.json",
  "typeCheckingMode": "strict",
  "include": ["."],
  "exclude": ["**/.venv", "**/.mypy_cache", "**/__pycache__", "build", "dist"],
  "reportMissingImports": "error",
  "reportUnknownMemberType": "warning",
  "reportUnknownArgumentType": "warning",
  "pythonVersion": "3.11",
  "venvPath": ".",
  "venv": ".venv"
}
```

- Ensure `pyproject.toml` (if used for tools) sets the same Python version as CI.

- Add/update a minimal stub for VSPreview types if needed (to quiet false positives for dynamic imports). Example: `typings/vspreview.pyi` with minimal signatures used by the generator.

### Run locally

```bash
# If node is available
npx pyright

# Or installed globally
pyright
```

---

## Tests

### Unit Tests

- **New**: `tests/test_console_safety.py`
  - **`test_ascii_arrows_in_prints()`**: import the generator, build a script string with template substitutions, assert no `→`/`↔` remain in `print` lines (regex on lines beginning with `print(` or using `safe_print`).
  - **`test_reconfigure_present()`**: the generated script contains the `reconfigure(..., errors="replace")` guard.
  - **`test_safe_print_fallback()`** *(if helper kept)*: simulate an object with `encoding="cp1252"` and ensure no exception is raised.

- **Smoke on Windows** (CI only):
  - Run a tiny surrogate Python script that sets `sys.stdout.reconfigure(encoding="cp1252")`, then `subprocess.run` a snippet mirroring our two prints. Assert exit code 0.

### Type Checks

- Run `pyright` in CI and locally; ensure no new diagnostics are introduced by template edits.

---

## GitHub Actions (CI) Updates

Create or update `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [Develop, feature/**]
  pull_request:
    branches: [Develop, main]

jobs:
  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - name: Install pyright
        run: npm i -g pyright
      - name: Type check
        run: pyright
```

> *Note:* We keep type checking on Linux for speed; functionality tests run on both Linux and Windows.

---

## Documentation Updates

- **README.md / CLI Guide**:  
  - Add a short “VSPreview Console Notes (Windows)” section explaining that logs use ASCII arrows and why.  
  - Mention the `chcp 65001`/Windows Terminal tip.

- **config_reference.md / README_REFERENCE.md** (if `VSPreview` section exists):  
  - Clarify that the helper script sanitizes console prints for portability; overlay text remains unchanged.

- **CHANGELOG.md**:  
  - Add under “Fixed”: “Prevent VSPreview helper crash on Windows `cp1252` consoles by sanitizing printed Unicode glyphs and preferring UTF‑8 for stdout/stderr in helper script.”

---

## Acceptance Criteria

- Running a newly generated `vspreview_*.py` **does not throw** `UnicodeEncodeError` on a default Windows console.  
- Console lines show `->` and `<->` instead of Unicode arrows.  
- Overlay rendering and all VSPreview behavior remain unchanged.  
- `pytest` green on Linux & Windows in CI.  
- `pyright` green (no new errors).  
- Docs updated; CHANGELOG entry added.

---

## Definition of Done

- [ ] Code patched in `frame_compare.py` template.  
- [ ] Optional `safe_print` helper used for the two lines.  
- [ ] Unit tests written and passing.  
- [ ] `pyright` config present; type check passes locally and in CI.  
- [ ] CI updated to include Windows smoke.  
- [ ] Docs + changelog updated.  
- [ ] PR description links to this task and includes before/after screenshot of the console output.

---

## Appendix: Minimal Patch Snippets

```diff
 # inside the generated script (template in _write_vspreview_script)
+try:
+    import sys
+    if hasattr(sys.stdout, "reconfigure"):
+        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
+    if hasattr(sys.stderr, "reconfigure"):
+        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
+except Exception:
+    pass

- print("VSPreview outputs: reference on even slots, target on odd slots (0↔1, 2↔3, ...).")
+ print("VSPreview outputs: reference on even slots, target on odd slots (0<->1, 2<->3, ...).")

- msg = "Adjusted FPS for target '%s' to match reference (%s/%s → %s/%s)" % (...)
+ msg = "Adjusted FPS for target '%s' to match reference (%s/%s -> %s/%s)" % (...)
```

> **Decision log:** We deliberately keep the fix small, local, and ASCII‑first; we add a guarded UTF‑8 preference to reduce future fragility without imposing global env requirements.
