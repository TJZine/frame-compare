"""Unit tests for `scripts/generate_api_docs.py`.

These tests load the generator module directly from its file path (scripts/ is not a package),
and run it against a temporary fixture project tree under `tmp_path`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_generator_module(repo_root: Path) -> ModuleType:
    script_path = repo_root / "scripts" / "generate_api_docs.py"
    spec = importlib.util.spec_from_file_location("generate_api_docs", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Ensure the module is registered so dataclasses can resolve forward references when
    # `from __future__ import annotations` is used in the script.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_fixture_project(*, root: Path, missing_docstring: bool) -> None:
    """Create the minimal fixture project tree locked in the plan."""

    # Non-focus modules: module docstring + empty __all__.
    minimal_module = '"""Fixture module."""\n\n__all__ = []\n'

    for rel in (
        "src/frame_compare/__init__.py",
        "src/frame_compare/analysis/__init__.py",
        "src/frame_compare/config/__init__.py",
        "src/frame_compare/orchestration/__init__.py",
        "src/frame_compare/render/__init__.py",
        "src/frame_compare/vs/__init__.py",
        "src/frame_compare/vspreview/__init__.py",
        "src/frame_compare/runner.py",
    ):
        _write_file(root / rel, minimal_module)

    _write_file(
        root / "src/frame_compare/utils/__init__.py",
        '''"""Utilities module for fixture tests."""

__all__ = ["a_func", "BClass", "CONST_STR"]


def a_func(x: int) -> int:
    """Return x unchanged."""
    return x


class BClass:
    """A minimal class for generator tests."""

    def __init__(self) -> None:
        self.value = 1


CONST_STR = "hello"
''',
    )

    if missing_docstring:
        services_text = '''"""Services module for fixture tests."""

__all__ = ["missing_func"]


def missing_func() -> None:
    return None
'''
    else:
        services_text = '''"""Services module for fixture tests."""

__all__ = ["ok_func"]


def ok_func() -> None:
    """A documented function used to avoid docstring failures in drift tests."""
    return None
'''

    _write_file(root / "src/frame_compare/services/__init__.py", services_text)


def test_symbols_order_case_insensitive(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    gen = _load_generator_module(repo_root)

    _write_fixture_project(root=tmp_path, missing_docstring=False)
    output = tmp_path / "docs" / "api.md"

    exit_code = gen.main(["--project-root", str(tmp_path), "--output", str(output)])
    assert exit_code == 0

    text = output.read_text(encoding="utf-8")
    utils_section = text.split("## frame_compare.utils", 1)[1]

    idx_a = utils_section.find("### a_func")
    idx_b = utils_section.find("### BClass")
    idx_c = utils_section.find("### CONST_STR")

    assert idx_a != -1
    assert idx_b != -1
    assert idx_c != -1
    assert idx_a < idx_b < idx_c


def test_constant_str_rendered_as_constant_str(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    gen = _load_generator_module(repo_root)

    _write_fixture_project(root=tmp_path, missing_docstring=False)
    output = tmp_path / "docs" / "api.md"

    exit_code = gen.main(["--project-root", str(tmp_path), "--output", str(output)])
    assert exit_code == 0

    text = output.read_text(encoding="utf-8")
    assert "`CONST_STR` — constant (str)" in text


def test_check_exits_3_and_reports_missing_docstrings(tmp_path: Path, capsys) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    gen = _load_generator_module(repo_root)

    _write_fixture_project(root=tmp_path, missing_docstring=True)
    output = tmp_path / "docs" / "api.md"

    exit_code = gen.main(["--project-root", str(tmp_path), "--output", str(output), "--check"])
    assert exit_code == 3

    captured = capsys.readouterr()
    assert "missing_func" in captured.err


def test_check_exits_2_on_drift(tmp_path: Path, capsys) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    gen = _load_generator_module(repo_root)

    _write_fixture_project(root=tmp_path, missing_docstring=False)
    output = tmp_path / "docs" / "api.md"

    _write_file(output, "# not the generated output\n")
    exit_code = gen.main(["--project-root", str(tmp_path), "--output", str(output), "--check"])
    assert exit_code == 2

    captured = capsys.readouterr()
    assert "STALE:" in captured.err


def test_check_exits_2_when_output_missing(tmp_path: Path, capsys) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    gen = _load_generator_module(repo_root)

    _write_fixture_project(root=tmp_path, missing_docstring=False)
    output = tmp_path / "docs" / "api.md"
    assert not output.exists()

    exit_code = gen.main(["--project-root", str(tmp_path), "--output", str(output), "--check"])
    assert exit_code == 2

    captured = capsys.readouterr()
    assert f"MISSING: {output}" in captured.err


def test_repo_api_docs_drift() -> None:
    """Verify that checked-in docs/api.md does not drift from current codebase."""
    repo_root = Path(__file__).resolve().parents[1]
    gen = _load_generator_module(repo_root)

    exit_code = gen.main(["--project-root", str(repo_root), "--check"])
    assert exit_code == 0, (
        "docs/api.md is stale or has missing docstrings. "
        "Run 'python scripts/generate_api_docs.py' to regenerate it."
    )
