"""Behavior tests for ``scripts.api_docs.model``."""
# pyright: reportMissingImports=false

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import scripts.api_docs.model as api_docs_model  # noqa: E402


def _write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_model_resolves_locked_module_reexport(tmp_path: Path) -> None:
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

    module = api_docs_model.load_module_info(
        "frame_compare.utils",
        package_init,
        require_dunder_all=True,
    )

    assert (
        "frame_compare.utils",
        "src/frame_compare/utils/__init__.py",
    ) in api_docs_model.LOCKED_MODULES
    assert module.module_doc == "Utility facade."
    assert module.exports == ("public_fn", "SETTINGS")
    assert (
        api_docs_model.alias_target_for_export("public_fn", module.symbols["public_fn"])
        == "internal_fn"
    )

    module_cache = {package_init: module}
    resolved_alias = api_docs_model.resolve_symbol(
        project_root=tmp_path,
        module=module,
        name="public_fn",
        module_cache=module_cache,
        visited=set(),
    )
    resolved_constant = api_docs_model.resolve_symbol(
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
