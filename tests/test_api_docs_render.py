"""Behavior tests for ``scripts.api_docs.render``."""
# pyright: reportMissingImports=false

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import scripts.api_docs.model as api_docs_model  # noqa: E402
import scripts.api_docs.render as api_docs_render  # noqa: E402


def test_render_markdown_for_small_module_doc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    module_doc = api_docs_model.ModuleInfo(
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
        api_docs_render,
        "LOCKED_MODULES",
        (("frame_compare.utils", "src/frame_compare/utils/__init__.py"),),
    )

    markdown, missing = api_docs_render.generate_markdown(
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
