"""Command-line behavior for API docs generation."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from api_docs.model import ModuleInfo, read_text
from api_docs.render import generate_markdown

ExitCode = Literal[0, 1, 2, 3, 4]


@dataclass(frozen=True)
class CliArgs:
    project_root: Path
    output: Path | None
    check: bool


def main(argv: Sequence[str] | None = None) -> ExitCode:
    """CLI entrypoint."""

    args = _parse_args(argv)
    project_root = args.project_root.resolve()
    output = args.output.resolve() if args.output is not None else project_root / "docs" / "api.md"
    module_cache: dict[Path, ModuleInfo] = {}

    try:
        markdown, missing = generate_markdown(project_root=project_root, module_cache=module_cache)
    except ValueError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 4
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"ERROR: unexpected failure: {exc}\n")
        return 1

    if args.check:
        return _check_output(output=output, markdown=markdown, missing=missing)

    _write_text_atomic(output, markdown)
    return 0


def _parse_args(argv: Sequence[str] | None) -> CliArgs:
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
    namespace = parser.parse_args(argv)
    return CliArgs(
        project_root=namespace.project_root,
        output=namespace.output,
        check=bool(namespace.check),
    )


def _check_output(*, output: Path, markdown: str, missing: list[str]) -> ExitCode:
    if missing:
        for name in sorted(set(missing), key=lambda s: (s.lower(), s)):
            sys.stderr.write(f"MISSING_DOCSTRING: {name}\n")
        return 3
    if not output.exists():
        sys.stderr.write(f"MISSING: {output}\n")
        return 2
    if read_text(output) != markdown:
        sys.stderr.write(f"STALE: {output} differs from generated\n")
        return 2
    return 0


def _write_text_atomic(output: Path, markdown: str) -> None:
    from frame_compare.utils.atomic_write import write_text_atomic

    write_text_atomic(output, markdown, encoding="utf-8")
