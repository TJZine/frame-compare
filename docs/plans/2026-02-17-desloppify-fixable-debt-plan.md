# Desloppify High-Value Debt Fixes Implementation Plan

> **For implementer:** Follow this plan task-by-task. Do not skip steps or reorder tasks.

**Goal:** Eliminate the highest-value, low-risk, real (non-false-positive) quality issues identified in the re-audit: non-atomic writes and silent exception handling paths.

**Architecture:** Use a small shared atomic-write utility to centralize safe file persistence, then migrate the flagged `write_text(...)` sites to that utility. Also harden the alignment cache persistence path (no silent suppression + atomic bytes write). In parallel, remove silent exception suppression in report-opening flows by making fallback behavior explicit and testable. Keep behavior-compatible changes only; no broad refactors.

**Tech Stack:** Python 3.13, pytest, structlog, pathlib, tomli-w

---

## Global Stop Gates (no decision points)

0. Ensure the dev environment exists:
   - Run: `uv sync --group dev --frozen`
   - Expected: completes successfully and creates `.venv/`
1. Start from a clean working tree:
   - Run: `git status --porcelain`
   - Expected: no output
2. If any test/gate fails: STOP, fix the failure, rerun the same command, then continue.
3. Every commit must be GREEN for the task’s targeted tests (no broken intermediate commits).

### Task 1: Add Shared Atomic Write Utility

**Files:**
- Create: `src/frame_compare/utils/atomic_write.py`
- Modify: `src/frame_compare/utils/__init__.py`
- Test: `tests/utils/test_atomic_write.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

from frame_compare.utils.atomic_write import write_text_atomic


def test_write_text_atomic_replaces_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "out.toml"
    target.write_text("old", encoding="utf-8")

    write_text_atomic(target, "new", encoding="utf-8")

    assert target.read_text(encoding="utf-8") == "new"
```

Add a second failing test for bytes writes:

```python
from pathlib import Path

from frame_compare.utils.atomic_write import write_bytes_atomic


def test_write_bytes_atomic_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "data.bin"

    write_bytes_atomic(target, b"abc")

    assert target.read_bytes() == b"abc"
```

Add a third failing test to ensure failures do not corrupt existing files:

```python
import os
from pathlib import Path

import pytest

from frame_compare.utils.atomic_write import write_text_atomic


def test_write_text_atomic_does_not_replace_target_on_os_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "out.toml"
    target.write_text("old", encoding="utf-8")

    def _boom(_src: str, _dst: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("frame_compare.utils.atomic_write.os.replace", _boom)

    with pytest.raises(OSError, match="replace failed"):
        write_text_atomic(target, "new", encoding="utf-8")

    assert target.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.glob(".out.toml.*")) == []
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest -q tests/utils/test_atomic_write.py`
Expected: FAIL with import error for `frame_compare.utils.atomic_write`.

**Step 3: Write minimal implementation**

```python
# src/frame_compare/utils/atomic_write.py
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write_text_atomic(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def write_bytes_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise
```

Export from `src/frame_compare/utils/__init__.py` (append; do not replace existing exports):

1) Add imports near the top:

```python
from frame_compare.utils.atomic_write import write_bytes_atomic, write_text_atomic
```

2) Append to the existing `__all__` list:

```python
__all__ = [
    # ...existing entries...
    "write_bytes_atomic",
    "write_text_atomic",
]
```

**Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest -q tests/utils/test_atomic_write.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/frame_compare/utils/atomic_write.py src/frame_compare/utils/__init__.py tests/utils/test_atomic_write.py
git commit -m "refactor: add shared atomic write helpers"
```

### Task 2: Migrate Flagged Write Sites To Atomic Writes

**Files:**
- Modify: `src/frame_compare/cli_entry.py`
- Modify: `src/frame_compare/config/presets.py`
- Modify: `src/frame_compare/vspreview/adapter.py`
- Test: `tests/cli/test_cli_commands.py`
- Test: `tests/config/test_presets.py`
- Test: `tests/vspreview/test_adapter.py`

**Step 1: Write the failing test**

Add focused tests that assert these paths call atomic write helpers (no “analogous tests” left for the implementer).

`tests/cli/test_cli_commands.py`:

```python
def test_wizard_writer_uses_atomic_write(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    from frame_compare.cli_entry import _write_wizard_config_payload

    calls: list[Path] = []

    def _fake_write(path: Path, content: str, *, encoding: str = "utf-8") -> None:
        calls.append(path)
        path.write_text(content, encoding=encoding)

    monkeypatch.setattr("frame_compare.cli_entry.write_text_atomic", _fake_write)

    destination = tmp_path / "config" / "config.toml"
    _write_wizard_config_payload(destination, {"paths": {}, "slowpics": {}})

    assert calls == [destination]
```

`tests/config/test_presets.py`:

```python
def test_save_preset_uses_atomic_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from frame_compare.config.loader import get_default_config
    from frame_compare.config.presets import save_preset

    calls: list[Path] = []

    def _fake_write(path: Path, content: str, *, encoding: str = "utf-8") -> None:
        calls.append(path)
        path.write_text(content, encoding=encoding)

    monkeypatch.setattr("frame_compare.config.presets.write_text_atomic", _fake_write)

    config = get_default_config()
    saved = save_preset("atomic", config, presets_dir=tmp_path)

    assert calls == [saved]
```

`tests/vspreview/test_adapter.py`:

```python
def test_generate_vspreview_script_uses_atomic_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from frame_compare.vspreview.adapter import _generate_vspreview_script

    calls: list[Path] = []

    def _fake_write(path: Path, content: str, *, encoding: str = "utf-8") -> None:
        calls.append(path)
        path.write_text(content, encoding=encoding)

    monkeypatch.setattr("frame_compare.vspreview.adapter.write_text_atomic", _fake_write)

    script_path = _generate_vspreview_script(
        reference=Path("ref.mkv"),
        comparisons=[Path("a.mkv")],
        suggested_offsets_by_key={},
        cache_dir=tmp_path,
    )

    assert calls == [script_path]
    assert script_path.exists()
```

**Step 2: Run test to verify it fails**

Run:
`.venv/bin/pytest -q tests/cli/test_cli_commands.py tests/config/test_presets.py tests/vspreview/test_adapter.py`
Expected: FAIL because `write_text_atomic` is not yet used at call sites.

**Step 3: Write minimal implementation**

Replace direct `.write_text(...)` calls in:
- `src/frame_compare/cli_entry.py:439`
- `src/frame_compare/cli_entry.py:486`
- `src/frame_compare/config/presets.py:83`
- `src/frame_compare/vspreview/adapter.py:228`

Example replacement:

```python
from frame_compare.utils.atomic_write import write_text_atomic

write_text_atomic(config_path, toml_text, encoding="utf-8")
```

**Step 4: Run test to verify it passes**

Run:
`.venv/bin/pytest -q tests/cli/test_cli_commands.py tests/config/test_presets.py tests/vspreview/test_adapter.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/frame_compare/cli_entry.py src/frame_compare/config/presets.py src/frame_compare/vspreview/adapter.py tests/cli/test_cli_commands.py tests/config/test_presets.py tests/vspreview/test_adapter.py
git commit -m "refactor: use atomic file writes in cli, presets, and vspreview"
```

### Task 3: Harden Alignment Cache Write Path (no silent suppression + atomic write)

**Files:**
- Modify: `src/frame_compare/services/alignment.py`
- Test: `tests/services/test_alignment.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

import pytest

from frame_compare.services.alignment import save_offsets_cache
from frame_compare.services.types import AlignmentResult


def test_save_offsets_cache_logs_corrupt_existing_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_file = tmp_path / "audio_offsets.toml"
    cache_file.write_text("not valid toml", encoding="utf-8")

    warnings: list[tuple[str, dict[str, object]]] = []

    def _warning(event: str, **kwargs: object) -> None:
        warnings.append((event, dict(kwargs)))

    monkeypatch.setattr("frame_compare.services.alignment.log.warning", _warning)

    save_offsets_cache(
        tmp_path,
        [
            AlignmentResult(
                reference_clip="ref.mkv",
                comparison_clip="comp.mkv",
                frame_offset=1,
                time_offset_seconds=0.04,
                correlation_score=0.9,
                method="cross_correlation",
            )
        ],
    )

    assert any(event == "audio_offsets_cache_corrupt_on_write" for event, _ in warnings)
```

Add a second failing test to ensure the write itself is atomic:

```python
def test_save_offsets_cache_uses_atomic_bytes_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    res = [
        AlignmentResult(
            reference_clip="ref.mkv",
            comparison_clip="comp.mkv",
            frame_offset=10,
            time_offset_seconds=0.4,
            correlation_score=0.9,
            method="cross_correlation",
        )
    ]

    calls: list[Path] = []

    def _fake_write(path: Path, content: bytes) -> None:
        calls.append(path)
        path.write_bytes(content)

    monkeypatch.setattr("frame_compare.services.alignment.write_bytes_atomic", _fake_write)

    save_offsets_cache(tmp_path, res)
    assert calls == [tmp_path / "audio_offsets.toml"]
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest -q tests/services/test_alignment.py -k corrupt_existing_cache`
Expected: FAIL (no warning logged).

**Step 3: Write minimal implementation**

Change `src/frame_compare/services/alignment.py:328-330` to log with context instead of `pass`:

```python
except tomllib.TOMLDecodeError as exc:
    log.warning(
        "audio_offsets_cache_corrupt_on_write",
        path=str(cache_path),
        error=str(exc),
        exc_info=True,
    )
```

Keep overwrite behavior unchanged.

Then replace the non-atomic write at `src/frame_compare/services/alignment.py:344-345` with `write_bytes_atomic`:

```python
from frame_compare.utils.atomic_write import write_bytes_atomic

write_bytes_atomic(cache_path, tomli_w.dumps(data).encode("utf-8"))
```

**Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest -q tests/services/test_alignment.py -k "save_offsets_cache or corrupt_existing_cache"`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/frame_compare/services/alignment.py tests/services/test_alignment.py
git commit -m "fix: harden alignment cache writes (log corruption + atomic write)"
```

### Task 4: Make Browser Open Fallback Explicit (No Silent `except pass`)

**Files:**
- Modify: `src/frame_compare/cli_entry.py`
- Test: `tests/cli/test_cli_commands.py`

**Step 1: Write the failing test**

```python
def test_maybe_open_report_falls_back_to_webbrowser_when_startfile_fails(monkeypatch: MonkeyPatch) -> None:
    called: dict[str, str] = {}

    def _raise_startfile(_value: str) -> None:
        raise OSError("boom")

    fake_os = SimpleNamespace(name="nt", startfile=_raise_startfile)
    monkeypatch.setattr("frame_compare.cli_entry.os", fake_os)
    monkeypatch.setattr("frame_compare.cli_entry.webbrowser.open", lambda uri: called.setdefault("uri", uri))

    _maybe_open_report(Path("report.html"))

    assert called["uri"].startswith("file:")
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest -q tests/cli/test_cli_commands.py -k maybe_open_report_falls_back`
Expected: FAIL if fallback is not explicit in exception block.

**Step 3: Write minimal implementation**

Refactor `src/frame_compare/cli_entry.py:80-91`:

```python
if os.name == "nt" and hasattr(os, "startfile"):
    try:
        os.startfile(str(report_path))  # type: ignore[attr-defined]
        return
    except OSError:
        try:
            webbrowser.open(report_path.resolve().as_uri())
        except (OSError, webbrowser.Error):
            return
        return

try:
    webbrowser.open(report_path.resolve().as_uri())
except (OSError, webbrowser.Error):
    return
```

Replace the `except OSError: pass` with explicit fallback invocation inside that block so suppression is no longer silent.

**Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest -q tests/cli/test_cli_commands.py -k maybe_open_report`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/frame_compare/cli_entry.py tests/cli/test_cli_commands.py
git commit -m "refactor: make report-open fallback explicit on Windows startfile errors"
```

### Task 5: Verification Sweep

**Files:**
- Test: `tests/cli/test_cli_commands.py`
- Test: `tests/config/test_presets.py`
- Test: `tests/services/test_alignment.py`
- Test: `tests/vspreview/test_adapter.py`
- Test: `tests/utils/test_atomic_write.py`

**Step 1: Run targeted suite**

Run:
`.venv/bin/pytest -q tests/utils/test_atomic_write.py tests/cli/test_cli_commands.py tests/config/test_presets.py tests/services/test_alignment.py tests/vspreview/test_adapter.py`
Expected: PASS.

**Step 2: Mechanical grep checks (ensures debt is actually removed)**

- Verify the original non-atomic `write_text` call sites are gone:
  - Run:
    - `rg -n \"\\.write_text\\(\" src/frame_compare/cli_entry.py src/frame_compare/config/presets.py src/frame_compare/vspreview/adapter.py`
  - Expected: no matches
- Verify the silent cache suppression is gone:
  - Run: `rg -n \"except tomllib\\.TOMLDecodeError:\\s*\\n\\s*pass\" src/frame_compare/services/alignment.py`
  - Expected: no matches
- Verify the Windows report open path no longer has `except ...: pass`:
  - Run: `rg -n \"except OSError:\\s*\\n\\s*pass\" src/frame_compare/cli_entry.py`
  - Expected: no matches

**Step 3: Run project quality gates**

Run:
`.venv/bin/pyright --warnings`

Run:
`.venv/bin/ruff check .`

Run:
`.venv/bin/pytest -q`

Expected: All pass.

**Step 4: Re-run desloppify (STOP if tool not available)**

Preflight:
- Run: `command -v desloppify`
- Expected: prints a path; if empty, STOP and obtain install instructions (do not guess).

Run:
`desloppify scan --path .`

Run:
`desloppify status`

Run:
`desloppify show smells --status open`

Expected:
- `unsafe_file_write` and targeted `silent_except` findings reduced.
- no regressions in security/duplication.

**Step 5: Review strict delta and reclassify leftovers**

Run:
`desloppify show --status wontfix --top 200`

Expected:
- confirm remaining items are intentional debt only.

**Step 6: Commit verification artifacts (deterministic file list; no secrets)**

Before committing:
- Remove backup artifacts created by desloppify:
  - Run: `.venv/bin/python -c "import glob, os; [os.remove(p) for p in glob.glob('.desloppify/*.bak')]"`
  - Expected: no output
- Ensure only expected artifacts are staged:
  - Run: `git status --porcelain`
  - Expected: changes limited to `.desloppify/*.json` and `scorecard.png`

```bash
git add .desloppify/config.json .desloppify/state-python.json .desloppify/query.json scorecard.png
git commit -m "chore: re-scan desloppify after high-value debt fixes"
```
