"""Generate deterministic API documentation for Frame Compare.

This script generates `docs/api.md` by parsing a locked set of modules using the Python AST.
It intentionally avoids importing project code (so optional dependencies do not affect generation).

See: `.agent-workflow/runs/2026-02-04__p7-1__readme-md-with-usage-examples/plan-v5.md`
"""

from __future__ import annotations

import argparse
import ast
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ExitCode = Literal[0, 1, 2, 3, 4]


@dataclass(frozen=True)
class _ResolvedSymbol:
    """A symbol resolved to its defining AST node and origin file."""

    kind: Literal["function", "class", "constant"]
    name: str
    file_path: Path
    node: ast.AST


@dataclass(frozen=True)
class _ModuleInfo:
    """Parsed module metadata cached for deterministic generation."""

    module_name: str
    file_path: Path
    module_doc: str
    exports: tuple[str, ...]
    # local symbol table for resolution
    symbols: dict[str, ast.AST]


_LOCKED_MODULES: tuple[tuple[str, str], ...] = (
    ("frame_compare", "src/frame_compare/__init__.py"),
    ("frame_compare.analysis", "src/frame_compare/analysis/__init__.py"),
    ("frame_compare.config", "src/frame_compare/config/__init__.py"),
    ("frame_compare.orchestration", "src/frame_compare/orchestration/__init__.py"),
    ("frame_compare.render", "src/frame_compare/render/__init__.py"),
    ("frame_compare.services", "src/frame_compare/services/__init__.py"),
    ("frame_compare.utils", "src/frame_compare/utils/__init__.py"),
    ("frame_compare.vs", "src/frame_compare/vs/__init__.py"),
    ("frame_compare.vspreview", "src/frame_compare/vspreview/__init__.py"),
    ("frame_compare.runner", "src/frame_compare/runner.py"),
)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="generate_api_docs.py")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root directory (defaults to current working directory).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file path (defaults to <project-root>/docs/api.md).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write; compare would-be output against --output.",
    )
    return parser.parse_args(argv)


def _first_paragraph(doc: str) -> str:
    doc = doc.strip()
    if not doc:
        return ""
    # Split on first blank line; keep only the first paragraph.
    parts = doc.split("\n\n", 1)
    return parts[0].strip()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _module_ast(path: Path) -> ast.Module:
    return ast.parse(_read_text(path), filename=str(path))


def _parse_dunder_all(tree: ast.Module) -> tuple[str, ...] | None:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__all__":
                value = node.value
                if not isinstance(value, (ast.List, ast.Tuple)):
                    return None
                exports: list[str] = []
                for elt in value.elts:
                    if not isinstance(elt, ast.Constant) or not isinstance(elt.value, str):
                        return None
                    exports.append(elt.value)
                return tuple(exports)
    return None


def _is_type_checking_guard(node: ast.If) -> bool:
    test = node.test
    # Accept common patterns:
    # - if typing.TYPE_CHECKING:
    # - if TYPE_CHECKING:
    if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
        return True
    if isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING":
        return isinstance(test.value, ast.Name) and test.value.id == "typing"
    return False


def _build_symbol_table(tree: ast.Module) -> dict[str, ast.AST]:
    symbols: dict[str, ast.AST] = {}
    nodes: list[ast.stmt] = list(tree.body)

    # For docs generation, treat `if typing.TYPE_CHECKING:` imports as valid re-export sources.
    # This keeps the generator deterministic without importing the project.
    for node in tree.body:
        if isinstance(node, ast.If) and _is_type_checking_guard(node):
            nodes.extend(node.body)

    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols[node.name] = node
            continue

        if isinstance(node, ast.ImportFrom) and node.module is not None:
            for alias in node.names:
                local_name = alias.asname or alias.name
                # Store the ImportFrom node; resolution needs alias.name + node.module.
                symbols[local_name] = ast.ImportFrom(
                    module=node.module,
                    names=[ast.alias(name=alias.name, asname=alias.asname)],
                    level=node.level,
                )
            continue

        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            # Keep all single-target assignments addressable so type aliases and constants can be documented
            # deterministically without importing code.
            symbols[node.targets[0].id] = node
            continue

        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            symbols[node.target.id] = node
            continue

    return symbols


def _load_module_info(
    module_name: str, module_path: Path, *, require_dunder_all: bool
) -> _ModuleInfo:
    tree = _module_ast(module_path)
    exports: tuple[str, ...] = ()
    if require_dunder_all:
        parsed = _parse_dunder_all(tree)
        if parsed is None:
            raise ValueError(f"invalid __all__ in {module_path}")
        exports = parsed
    module_doc = _first_paragraph(ast.get_docstring(tree) or "")
    return _ModuleInfo(
        module_name=module_name,
        file_path=module_path,
        module_doc=module_doc,
        exports=exports,
        symbols=_build_symbol_table(tree),
    )


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


def _resolve_symbol(
    *,
    project_root: Path,
    module: _ModuleInfo,
    name: str,
    module_cache: dict[Path, _ModuleInfo],
    visited: set[tuple[Path, str]],
) -> _ResolvedSymbol:
    key = (module.file_path, name)
    if key in visited:
        raise ValueError(f"cyclic re-export: {module.module_name}.{name}")
    visited.add(key)

    node = module.symbols.get(name)
    if node is None:
        raise ValueError(f"unresolved export: {module.module_name}.{name}")

    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return _ResolvedSymbol(kind="function", name=name, file_path=module.file_path, node=node)
    if isinstance(node, ast.ClassDef):
        return _ResolvedSymbol(kind="class", name=name, file_path=module.file_path, node=node)
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        # Constant or alias.
        value = node.value  # type: ignore[attr-defined]
        if value is None:
            return _ResolvedSymbol(
                kind="constant", name=name, file_path=module.file_path, node=node
            )
        if isinstance(value, ast.Constant):
            return _ResolvedSymbol(
                kind="constant", name=name, file_path=module.file_path, node=node
            )
        if isinstance(value, (ast.Dict, ast.List, ast.Tuple, ast.Set)):
            return _ResolvedSymbol(
                kind="constant", name=name, file_path=module.file_path, node=node
            )
        if isinstance(value, ast.Name):
            return _resolve_symbol(
                project_root=project_root,
                module=module,
                name=value.id,
                module_cache=module_cache,
                visited=visited,
            )
        # Treat complex assignments (e.g., type aliases) as constants for documentation purposes.
        return _ResolvedSymbol(kind="constant", name=name, file_path=module.file_path, node=node)

    if isinstance(node, ast.ImportFrom) and node.module is not None:
        if len(node.names) != 1:
            raise ValueError(f"unexpected import shape for {module.module_name}.{name}")
        alias = node.names[0]
        target_module_name = node.module
        target_name = alias.name
        target_path = _module_path_from_import(project_root, target_module_name, node.level)
        target_module = module_cache.get(target_path)
        if target_module is None:
            target_module = _load_module_info(
                target_module_name,
                target_path,
                require_dunder_all=False,
            )
            module_cache[target_path] = target_module
        return _resolve_symbol(
            project_root=project_root,
            module=target_module,
            name=target_name,
            module_cache=module_cache,
            visited=visited,
        )

    raise ValueError(
        f"unsupported symbol node for {module.module_name}.{name}: {type(node).__name__}"
    )


def _render_arg(arg: ast.arg, default: ast.expr | None) -> str:
    rendered = arg.arg
    if arg.annotation is not None:
        rendered += f": {ast.unparse(arg.annotation)}"
    if default is not None:
        rendered += f" = {ast.unparse(default)}"
    return rendered


def _render_signature(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = fn.args

    # Defaults apply to the last N positional args.
    pos_args = list(args.posonlyargs) + list(args.args)
    pos_defaults = [None] * (len(pos_args) - len(args.defaults)) + list(args.defaults)
    rendered_parts: list[str] = []

    for i, (a, d) in enumerate(zip(pos_args, pos_defaults, strict=True)):
        rendered_parts.append(_render_arg(a, d))
        if args.posonlyargs and i == len(args.posonlyargs) - 1:
            rendered_parts.append("/")

    if args.vararg is not None:
        rendered_parts.append(f"*{args.vararg.arg}")
    elif args.kwonlyargs:
        rendered_parts.append("*")

    for a, d in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        rendered_parts.append(_render_arg(a, d))

    if args.kwarg is not None:
        rendered_parts.append(f"**{args.kwarg.arg}")

    ret = ast.unparse(fn.returns) if fn.returns is not None else "None"
    return f"{fn.name}({', '.join(rendered_parts)}) -> {ret}"


def _constant_type(assign: ast.Assign | ast.AnnAssign) -> str:
    value = assign.value
    if value is None:
        return "unknown"
    if isinstance(value, ast.Dict):
        return "dict"
    if isinstance(value, ast.List):
        return "list"
    if isinstance(value, ast.Tuple):
        return "tuple"
    if isinstance(value, ast.Set):
        return "set"
    if not isinstance(value, ast.Constant):
        return "unknown"
    value = value.value
    if value is None:
        return "None"
    return type(value).__name__


def _generate_markdown(
    *,
    project_root: Path,
    module_cache: dict[Path, _ModuleInfo],
) -> tuple[str, list[str]]:
    missing_docstrings: list[str] = []

    out_lines: list[str] = []
    out_lines.append("# API Reference")
    out_lines.append("")
    out_lines.append("> Generated by `scripts/generate_api_docs.py`. Do not edit manually.")
    out_lines.append("")

    for module_name, rel_path in _LOCKED_MODULES:
        module_path = (project_root / rel_path).resolve()
        module = module_cache.get(module_path)
        if module is None:
            module = _load_module_info(module_name, module_path, require_dunder_all=True)
            module_cache[module_path] = module

        out_lines.append(f"## {module_name}")
        out_lines.append("")
        if module.module_doc:
            out_lines.append(module.module_doc)
            out_lines.append("")

        for export in sorted(module.exports, key=lambda s: (s.lower(), s)):
            export_node = module.symbols.get(export)
            alias_target: str | None = None
            if (
                isinstance(export_node, ast.ImportFrom)
                and export_node.module is not None
                and len(export_node.names) == 1
            ):
                imported = export_node.names[0]
                if imported.asname == export and imported.name != export:
                    # Example: from x import foo as bar  (export == "bar", target == "foo")
                    alias_target = imported.name

            resolved = _resolve_symbol(
                project_root=project_root,
                module=module,
                name=export,
                module_cache=module_cache,
                visited=set(),
            )

            out_lines.append(f"### {export}")
            out_lines.append("")

            if resolved.kind == "function":
                assert isinstance(resolved.node, (ast.FunctionDef, ast.AsyncFunctionDef))
                signature = _render_signature(resolved.node)
                if signature.startswith(f"{resolved.node.name}(") and export != resolved.node.name:
                    signature = signature.replace(f"{resolved.node.name}(", f"{export}(", 1)
                out_lines.append(f"`{signature}`")
                out_lines.append("")
                if alias_target is not None:
                    out_lines.append(f"Alias of `{alias_target}`.")
                    out_lines.append("")
                else:
                    doc = _first_paragraph(ast.get_docstring(resolved.node) or "")
                    if not doc:
                        missing_docstrings.append(export)
                    else:
                        out_lines.append(doc)
                        out_lines.append("")
            elif resolved.kind == "class":
                out_lines.append(f"`{export}`")
                out_lines.append("")
                assert isinstance(resolved.node, ast.ClassDef)
                doc = _first_paragraph(ast.get_docstring(resolved.node) or "")
                if not doc:
                    missing_docstrings.append(export)
                else:
                    out_lines.append(doc)
                    out_lines.append("")
            else:
                assert resolved.kind == "constant"
                assert isinstance(resolved.node, (ast.Assign, ast.AnnAssign))
                out_lines.append(f"`{export}` — constant ({_constant_type(resolved.node)})")
                out_lines.append("")

    return "\n".join(out_lines).rstrip() + "\n", missing_docstrings


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint.

    Args:
        argv: Optional argv override for testability.

    Returns:
        Process exit code.
    """

    args = _parse_args(argv)
    project_root: Path = args.project_root.resolve()
    output: Path = (
        args.output.resolve() if args.output is not None else (project_root / "docs" / "api.md")
    )
    check: bool = bool(args.check)

    module_cache: dict[Path, _ModuleInfo] = {}

    try:
        markdown, missing = _generate_markdown(project_root=project_root, module_cache=module_cache)
    except ValueError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 4
    except Exception as exc:  # noqa: BLE001
        # Unexpected failures should remain deterministic and non-traceback for this repo workflow.
        sys.stderr.write(f"ERROR: unexpected failure: {exc}\n")
        return 1

    # Missing-docstring failures are reported in check mode only.
    if check and missing:
        for name in sorted(set(missing), key=lambda s: (s.lower(), s)):
            sys.stderr.write(f"MISSING_DOCSTRING: {name}\n")
        return 3

    if check:
        if not output.exists():
            sys.stderr.write(f"MISSING: {output}\n")
            return 2
        current = _read_text(output)
        if current != markdown:
            sys.stderr.write(f"STALE: {output} differs from generated\n")
            return 2
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
