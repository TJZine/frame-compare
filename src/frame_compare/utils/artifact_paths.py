"""Shared human artifact paths and terminal hyperlinks."""

from pathlib import Path

from rich.markup import escape


def absolute_display_path(path: Path, root: Path | None) -> Path:
    if path.is_absolute():
        return path.resolve()
    if root is None:
        return path
    return (root.resolve() / path).resolve()


def format_display_path(path: Path, *, root: Path | None) -> str:
    absolute = absolute_display_path(path, root)
    if root is None:
        return str(path)

    try:
        relative = absolute.relative_to(root.resolve())
    except ValueError:
        return str(absolute)
    return str(relative) if relative != Path(".") else "."


def artifact_link(path: Path, *, root: Path | None, verbose: bool = False) -> str:
    display = format_display_path(path, root=root)
    absolute = absolute_display_path(path, root)
    if not absolute.is_absolute():
        absolute = path.resolve()
    rendered = f"[link={absolute.as_uri()}]{escape(display)}[/link]"
    if verbose and root is not None and display != str(absolute):
        rendered += f" [dim]{escape(f'(absolute: {absolute})')}[/]"
    return rendered
