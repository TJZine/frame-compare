"""Unit tests for `scripts/generate_api_docs.py`.

These tests load the generator module directly from its file path (scripts/ is not a package),
and run it against a temporary fixture project tree under `tmp_path`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


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
        "src/frame_compare/vsview/__init__.py",
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


@pytest.mark.parametrize("ordering", [True, False], ids=["symbol-order", "string-constant"])
def test_api_docs_symbol_order_and_constant_rendering(tmp_path: Path, ordering: bool) -> None:
    gen = _load_generator_module(Path(__file__).resolve().parents[1])
    _write_fixture_project(root=tmp_path, missing_docstring=False)
    output = tmp_path / "docs" / "api.md"
    assert gen.main(["--project-root", str(tmp_path), "--output", str(output)]) == 0
    text = output.read_text(encoding="utf-8")
    if ordering:
        section = text.split("## frame_compare.utils", 1)[1]
        indices = [section.find(f"### {name}") for name in ("a_func", "BClass", "CONST_STR")]
        for index in indices:
            assert index != -1
        assert indices[0] < indices[1] < indices[2]
    else:
        assert "`CONST_STR` — constant (str)" in text


@pytest.mark.parametrize(
    ("missing_docstring", "existing_output", "expected_code", "message"),
    [(True, False, 3, "missing_func"), (False, True, 2, "STALE:"), (False, False, 2, "MISSING:")],
)
def test_api_docs_check_refuses_missing_docs_or_stale_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    missing_docstring: bool,
    existing_output: bool,
    expected_code: int,
    message: str,
) -> None:
    gen = _load_generator_module(Path(__file__).resolve().parents[1])
    _write_fixture_project(root=tmp_path, missing_docstring=missing_docstring)
    output = tmp_path / "docs" / "api.md"
    if existing_output:
        _write_file(output, "# not the generated output\n")
    else:
        assert not output.exists()
    assert (
        gen.main(["--project-root", str(tmp_path), "--output", str(output), "--check"])
        == expected_code
    )
    expected = f"MISSING: {output}" if message == "MISSING:" else message
    assert expected in capsys.readouterr().err


def test_generation_preserves_existing_output_mode(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    gen = _load_generator_module(repo_root)
    _write_fixture_project(root=tmp_path, missing_docstring=False)
    output = tmp_path / "docs" / "api.md"
    _write_file(output, "old")
    output.chmod(0o640)
    original_mode = output.stat().st_mode & 0o777

    exit_code = gen.main(["--project-root", str(tmp_path), "--output", str(output)])

    assert exit_code == 0
    assert (output.stat().st_mode & 0o777) == original_mode


def test_file_path_import_uses_repo_local_api_docs_when_foreign_package_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    foreign_root = tmp_path / "foreign"
    fixture_root = tmp_path / "fixture"

    _write_file(foreign_root / "api_docs" / "__init__.py", "")
    _write_file(
        foreign_root / "api_docs" / "cli.py",
        "def main(argv=None):\n    return 99\n",
    )
    monkeypatch.syspath_prepend(str(foreign_root))
    for module_name in list(sys.modules):
        if module_name == "api_docs" or module_name.startswith("api_docs."):
            monkeypatch.delitem(sys.modules, module_name, raising=False)

    gen = _load_generator_module(repo_root)
    _write_fixture_project(root=fixture_root, missing_docstring=False)
    output = fixture_root / "docs" / "api.md"

    exit_code = gen.main(["--project-root", str(fixture_root), "--output", str(output), "--check"])

    assert exit_code == 2
    api_docs_cli = sys.modules["api_docs.cli"]
    assert (
        Path(str(api_docs_cli.__file__))
        .resolve()
        .is_relative_to(repo_root / "scripts" / "api_docs")
    )


def test_generation_does_not_replace_target_on_shared_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    gen = _load_generator_module(repo_root)
    _write_fixture_project(root=tmp_path, missing_docstring=False)
    target = tmp_path / "docs" / "api.md"
    _write_file(target, "old")

    def _boom(_src: str, _dst: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("frame_compare.utils.atomic_write.os.replace", _boom)

    with pytest.raises(OSError, match="replace failed"):
        gen.main(["--project-root", str(tmp_path), "--output", str(target)])

    assert target.read_text(encoding="utf-8") == "old"
    assert list(target.parent.glob(".api.md.*")) == []


def test_repo_api_docs_drift() -> None:
    """Verify that checked-in docs/api.md does not drift from current codebase."""
    repo_root = Path(__file__).resolve().parents[1]
    gen = _load_generator_module(repo_root)

    exit_code = gen.main(["--project-root", str(repo_root), "--check"])
    assert exit_code == 0, (
        "docs/api.md is stale or has missing docstrings. "
        "Run 'python scripts/generate_api_docs.py' to regenerate it."
    )
