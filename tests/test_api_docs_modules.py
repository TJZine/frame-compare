"""Focused tests for extracted API docs helper modules."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def api_docs_import_path(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Expose scripts/api_docs as the top-level api_docs package used by the script."""
    monkeypatch.syspath_prepend(str(repo_root / "scripts"))


def _write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _import_api_docs_module(module_name: str) -> ModuleType:
    return importlib.import_module(f"api_docs.{module_name}")


def test_model_resolves_locked_module_reexport(tmp_path: Path, api_docs_import_path: None) -> None:
    model = _import_api_docs_module("model")

    package_init = tmp_path / "src" / "frame_compare" / "utils" / "__init__.py"
    _write_file(
        package_init,
        '''"""Utility facade.

Extra detail that should be excluded from the rendered summary.
"""

from frame_compare.utils._impl import internal_fn as public_fn

SETTINGS: dict[str, bool] = {"enabled": True}

__all__ = ["public_fn", "SETTINGS"]
''',
    )
    _write_file(
        tmp_path / "src" / "frame_compare" / "utils" / "_impl.py",
        '''"""Implementation module."""

def internal_fn(value: int) -> int:
    """Return the input value."""
    return value
''',
    )

    module = model.load_module_info(
        "frame_compare.utils",
        package_init,
        require_dunder_all=True,
    )

    assert ("frame_compare.utils", "src/frame_compare/utils/__init__.py") in model.LOCKED_MODULES
    assert module.module_doc == "Utility facade."
    assert module.exports == ("public_fn", "SETTINGS")
    assert model.alias_target_for_export("public_fn", module.symbols["public_fn"]) == "internal_fn"

    module_cache = {package_init: module}
    resolved_alias = model.resolve_symbol(
        project_root=tmp_path,
        module=module,
        name="public_fn",
        module_cache=module_cache,
        visited=set(),
    )
    resolved_constant = model.resolve_symbol(
        project_root=tmp_path,
        module=module,
        name="SETTINGS",
        module_cache=module_cache,
        visited=set(),
    )

    assert resolved_alias.kind == "function"
    assert resolved_alias.name == "internal_fn"
    assert resolved_alias.file_path == tmp_path / "src" / "frame_compare" / "utils" / "_impl.py"
    assert resolved_constant.kind == "constant"
    assert resolved_constant.name == "SETTINGS"


def test_render_markdown_for_small_module_doc(
    tmp_path: Path, api_docs_import_path: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ast

    model = _import_api_docs_module("model")
    render = _import_api_docs_module("render")

    module_path = tmp_path / "src" / "frame_compare" / "utils" / "__init__.py"
    tree = ast.parse(
        '''"""Utility facade."""

def beta(value: int, *, enabled: bool = True) -> str:
    """Render beta output.

    Additional details stay out of the first paragraph.
    """
    return str(value)

class Alpha:
    """Alpha class."""

CONFIG = {"enabled": True}
''',
        filename=str(module_path),
    )
    module_doc = model.ModuleInfo(
        module_name="frame_compare.utils",
        file_path=module_path,
        module_doc="Utility facade.",
        exports=("CONFIG", "beta", "Alpha"),
        symbols={
            node.name: node
            for node in tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef))
        }
        | {"CONFIG": tree.body[-1]},
    )
    monkeypatch.setattr(
        render, "LOCKED_MODULES", (("frame_compare.utils", "src/frame_compare/utils/__init__.py"),)
    )

    markdown, missing = render.generate_markdown(
        project_root=tmp_path,
        module_cache={module_path.resolve(): module_doc},
    )

    assert missing == []
    assert markdown.startswith("# API Reference\n")
    assert "## frame_compare.utils\n\nUtility facade.\n" in markdown
    assert markdown.index("### Alpha") < markdown.index("### beta") < markdown.index("### CONFIG")
    assert "`beta(value: int, *, enabled: bool = True) -> str`" in markdown
    assert "Render beta output." in markdown
    assert "`CONFIG` — constant (dict)" in markdown


def test_cli_check_reports_success_and_mismatch(
    tmp_path: Path,
    api_docs_import_path: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _import_api_docs_module("cli")

    generated = "# API Reference\n\nstable\n"
    output = tmp_path / "api.md"
    output.write_text(generated, encoding="utf-8")

    def _generate_markdown(
        *, project_root: Path, module_cache: dict[Path, object]
    ) -> tuple[str, list[str]]:
        assert project_root == tmp_path.resolve()
        assert module_cache == {}
        return generated, []

    monkeypatch.setattr(cli, "generate_markdown", _generate_markdown)

    success_code = cli.main(["--project-root", str(tmp_path), "--output", str(output), "--check"])
    success_streams = capsys.readouterr()

    output.write_text("# stale\n", encoding="utf-8")
    mismatch_code = cli.main(["--project-root", str(tmp_path), "--output", str(output), "--check"])
    mismatch_streams = capsys.readouterr()

    assert success_code == 0
    assert success_streams.err == ""
    assert mismatch_code == 2
    assert f"STALE: {output.resolve()} differs from generated\n" == mismatch_streams.err
