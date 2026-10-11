"""AST-backed module discovery and symbol resolution for API docs."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class ResolvedSymbol:
    """A symbol resolved to its defining AST node and origin file."""

    kind: Literal["function", "class", "constant"]
    name: str
    file_path: Path
    node: ast.AST


@dataclass(frozen=True)
class ModuleInfo:
    """Parsed module metadata cached for deterministic generation."""

    module_name: str
    file_path: Path
    module_doc: str
    exports: tuple[str, ...]
    symbols: dict[str, ast.AST]


LOCKED_MODULES: tuple[tuple[str, str], ...] = (
    ("frame_compare", "src/frame_compare/__init__.py"),
    ("frame_compare.analysis", "src/frame_compare/analysis/__init__.py"),
    ("frame_compare.config", "src/frame_compare/config/__init__.py"),
    ("frame_compare.orchestration", "src/frame_compare/orchestration/__init__.py"),
    ("frame_compare.render", "src/frame_compare/render/__init__.py"),
    ("frame_compare.services", "src/frame_compare/services/__init__.py"),
    ("frame_compare.utils", "src/frame_compare/utils/__init__.py"),
    ("frame_compare.vs", "src/frame_compare/vs/__init__.py"),
    ("frame_compare.vsview", "src/frame_compare/vsview/__init__.py"),
    ("frame_compare.runner", "src/frame_compare/runner.py"),
)


def first_paragraph(doc: str) -> str:
    doc = doc.strip()
    if not doc:
        return ""
    parts = doc.split("\n\n", 1)
    return parts[0].strip()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_module_info(
    module_name: str, module_path: Path, *, require_dunder_all: bool
) -> ModuleInfo:
    tree = ast.parse(read_text(module_path), filename=str(module_path))
    exports: tuple[str, ...] = ()
    if require_dunder_all:
        parsed = _parse_dunder_all(tree)
        if parsed is None:
            raise ValueError(f"invalid __all__ in {module_path}")
        exports = parsed
    return ModuleInfo(
        module_name=module_name,
        file_path=module_path,
        module_doc=first_paragraph(ast.get_docstring(tree) or ""),
        exports=exports,
        symbols=_build_symbol_table(tree),
    )


def resolve_symbol(
    *,
    project_root: Path,
    module: ModuleInfo,
    name: str,
    module_cache: dict[Path, ModuleInfo],
    visited: set[tuple[Path, str]],
) -> ResolvedSymbol:
    key = (module.file_path, name)
    if key in visited:
        raise ValueError(f"cyclic re-export: {module.module_name}.{name}")
    visited.add(key)

    node = module.symbols.get(name)
    if node is None:
        raise ValueError(f"unresolved export: {module.module_name}.{name}")

    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return ResolvedSymbol(kind="function", name=name, file_path=module.file_path, node=node)
    if isinstance(node, ast.ClassDef):
        return ResolvedSymbol(kind="class", name=name, file_path=module.file_path, node=node)
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        return _resolve_assign_symbol(
            project_root=project_root,
            module=module,
            name=name,
            node=node,
            module_cache=module_cache,
            visited=visited,
        )
    if isinstance(node, ast.ImportFrom):
        return _resolve_import_symbol(
            project_root=project_root,
            module=module,
            name=name,
            node=node,
            module_cache=module_cache,
            visited=visited,
        )

    raise ValueError(
        f"unsupported symbol node for {module.module_name}.{name}: {type(node).__name__}"
    )


def alias_target_for_export(export: str, export_node: ast.AST | None) -> str | None:
    if (
        isinstance(export_node, ast.ImportFrom)
        and export_node.module is not None
        and len(export_node.names) == 1
    ):
        imported = export_node.names[0]
        if imported.asname == export and imported.name != export:
            return imported.name
    return None


def _parse_dunder_all(tree: ast.Module) -> tuple[str, ...] | None:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__all__":
                return _literal_string_sequence(node.value)
    return None


def _literal_string_sequence(value: ast.expr) -> tuple[str, ...] | None:
    if not isinstance(value, (ast.List, ast.Tuple)):
        return None
    exports: list[str] = []
    for elt in value.elts:
        if not isinstance(elt, ast.Constant) or not isinstance(elt.value, str):
            return None
        exports.append(elt.value)
    return tuple(exports)


def _is_type_checking_guard(node: ast.If) -> bool:
    test = node.test
    if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
        return True
    if isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING":
        return isinstance(test.value, ast.Name) and test.value.id == "typing"
    return False


def _build_symbol_table(tree: ast.Module) -> dict[str, ast.AST]:
    symbols: dict[str, ast.AST] = {}
    nodes: list[ast.stmt] = list(tree.body)

    for node in tree.body:
        if isinstance(node, ast.If) and _is_type_checking_guard(node):
            nodes.extend(node.body)

    for node in nodes:
        _process_symbol_node(node, symbols)

    return symbols


def _process_symbol_node(node: ast.AST, symbols: dict[str, ast.AST]) -> None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        symbols[node.name] = node
    elif isinstance(node, ast.ImportFrom) and node.module is not None:
        for alias in node.names:
            local_name = alias.asname or alias.name
            symbols[local_name] = ast.ImportFrom(
                module=node.module,
                names=[ast.alias(name=alias.name, asname=alias.asname)],
                level=node.level,
            )
    elif (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    ):
        symbols[node.targets[0].id] = node
    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        symbols[node.target.id] = node


def _module_path_from_import(project_root: Path, module: str, level: int) -> Path:
    if level != 0:
        raise ValueError(f"relative import not supported: from {'.' * level}{module} import ...")
    base = project_root / "src"
    py_path = base / Path(*module.split("."))
    if (py_path.with_suffix(".py")).exists():
        return py_path.with_suffix(".py")
    if (py_path / "__init__.py").exists():
        return py_path / "__init__.py"
    raise ValueError(f"import target not found: {module}")


def _resolve_assign_symbol(
    *,
    project_root: Path,
    module: ModuleInfo,
    name: str,
    node: ast.Assign | ast.AnnAssign,
    module_cache: dict[Path, ModuleInfo],
    visited: set[tuple[Path, str]],
) -> ResolvedSymbol:
    value = node.value
    if value is None or isinstance(value, (ast.Constant, ast.Dict, ast.List, ast.Tuple, ast.Set)):
        return ResolvedSymbol(kind="constant", name=name, file_path=module.file_path, node=node)
    if isinstance(value, ast.Name):
        return resolve_symbol(
            project_root=project_root,
            module=module,
            name=value.id,
            module_cache=module_cache,
            visited=visited,
        )
    return ResolvedSymbol(kind="constant", name=name, file_path=module.file_path, node=node)


def _resolve_import_symbol(
    *,
    project_root: Path,
    module: ModuleInfo,
    name: str,
    node: ast.ImportFrom,
    module_cache: dict[Path, ModuleInfo],
    visited: set[tuple[Path, str]],
) -> ResolvedSymbol:
    if len(node.names) != 1:
        raise ValueError(f"unexpected import shape for {module.module_name}.{name}")
    alias = node.names[0]
    target_module_name = node.module
    if target_module_name is None:
        raise ValueError(f"missing module in import for {module.module_name}.{name}")
    target_path = _module_path_from_import(project_root, target_module_name, node.level)
    target_module = module_cache.get(target_path)
    if target_module is None:
        target_module = load_module_info(target_module_name, target_path, require_dunder_all=False)
        module_cache[target_path] = target_module
    return resolve_symbol(
        project_root=project_root,
        module=target_module,
        name=alias.name,
        module_cache=module_cache,
        visited=visited,
    )
