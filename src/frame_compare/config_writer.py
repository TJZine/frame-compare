"""Config template/preset helpers extracted from src.frame_compare.core."""

from __future__ import annotations

import copy
import difflib
import math
import os
import tempfile
import tomllib
from collections.abc import Mapping as MappingABC
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple

from rich import print

from src.frame_compare.preflight import PACKAGED_TEMPLATE_PATH

__all__ = [
    "read_template_text",
    "load_template_config",
    "render_config_text",
    "write_config_file",
]


def read_template_text() -> str:
    """Return the config template text, preserving existing comments."""

    return PACKAGED_TEMPLATE_PATH.read_text(encoding="utf-8")


def load_template_config() -> Dict[str, Any]:
    """Load the template configuration into a nested dictionary."""

    text = read_template_text()
    return tomllib.loads(text.lstrip("\ufeff"))


def _deep_merge(dest: Dict[str, Any], src: Mapping[str, Any]) -> None:
    """Recursively merge ``src`` into ``dest`` in-place."""

    for key, value in src.items():
        if isinstance(value, Mapping) and isinstance(dest.get(key), MappingABC):
            existing = dest[key]
            if not isinstance(existing, dict):
                dest[key] = copy.deepcopy(value)
            else:
                _deep_merge(existing, value)  # type: ignore[arg-type]
        elif isinstance(value, Mapping) and key not in dest:
            dest[key] = copy.deepcopy(value)
        else:
            dest[key] = copy.deepcopy(value)


def _diff_config(base: Mapping[str, Any], modified: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a nested mapping of values that differ between ``base`` and ``modified``."""

    diff: Dict[str, Any] = {}
    for key, value in modified.items():
        base_value = base.get(key)
        if isinstance(value, Mapping) and isinstance(base_value, Mapping):
            nested = _diff_config(base_value, value)
            if nested:
                diff[key] = nested
        else:
            if key not in base or base_value != value:
                diff[key] = value
    return diff


def _format_toml_value(value: Any) -> str:
    """Format a Python value as TOML literal."""

    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError("Non-finite float cannot be serialized to TOML")
            return format(value, "g")
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        return "[" + ", ".join(_format_toml_value(item) for item in value) + "]"
    if value is None:
        return '""'  # Represent None as empty string literal.
    raise ValueError(f"Unsupported TOML value type: {type(value)!r}")


def _flatten_overrides(overrides: Mapping[str, Any]) -> Dict[Tuple[str, ...], Dict[str, Any]]:
    """Flatten nested override mapping to section tuples -> key/value pairs."""

    flattened: Dict[Tuple[str, ...], Dict[str, Any]] = {}

    def _walk(mapping: Mapping[str, Any], prefix: Tuple[str, ...]) -> None:
        for key, value in mapping.items():
            if isinstance(value, Mapping):
                _walk(value, prefix + (key,))
            else:
                flattened.setdefault(prefix, {})[key] = value

    _walk(overrides, ())
    return flattened


def _apply_overrides_to_template(template_text: str, overrides: Mapping[str, Any]) -> str:
    """Return template text with overrides applied without discarding comments."""

    if not overrides:
        return template_text

    lines = template_text.splitlines()
    section_ranges: Dict[Tuple[str, ...], Tuple[int, int]] = {}
    current_section: Tuple[str, ...] = ()
    section_start = 0
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]") and not stripped.startswith("[["):
            if current_section not in section_ranges:
                section_ranges[current_section] = (section_start, index)
            section_name = stripped[1:-1]
            current_section = tuple(part.strip() for part in section_name.split(".")) if section_name else ()
            section_start = index + 1
    if current_section not in section_ranges:
        section_ranges[current_section] = (section_start, len(lines))

    flattened = _flatten_overrides(overrides)
    applied: set[Tuple[Tuple[str, ...], str]] = set()
    current_section = ()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]") and not stripped.startswith("[["):
            section_name = stripped[1:-1]
            current_section = tuple(part.strip() for part in section_name.split(".")) if section_name else ()
            continue
        if "=" not in line or stripped.startswith("#"):
            continue
        key, _, _ = stripped.partition("=")
        key = key.strip()
        overrides_for_section = flattened.get(current_section)
        if overrides_for_section and key in overrides_for_section:
            formatted = _format_toml_value(overrides_for_section[key])
            prefix = line[: line.index(key)]
            lines[idx] = f"{prefix}{key} = {formatted}"
            applied.add((current_section, key))

    for section, key_values in flattened.items():
        for key, value in key_values.items():
            identifier = (section, key)
            if identifier in applied:
                continue
            start, end = section_ranges.get(section, (len(lines), len(lines)))
            formatted = _format_toml_value(value)
            insert_line = f"{key} = {formatted}"
            lines.insert(end, insert_line)
            # Update stored ranges for following insertions.
            section_ranges = {
                sect: (s, e + 1 if e >= end else e) for sect, (s, e) in section_ranges.items()
            }
            applied.add(identifier)

    return "\n".join(lines) + ("\n" if template_text.endswith("\n") else "")


def render_config_text(
    template_text: str,
    template_config: Mapping[str, Any],
    final_config: Mapping[str, Any],
) -> str:
    """Generate TOML text for ``final_config`` using the original template layout."""

    overrides = _diff_config(template_config, final_config)
    return _apply_overrides_to_template(template_text, overrides)


def write_config_file(path: Path, content: str) -> None:
    """Atomically write ``content`` to ``path`` with UTF-8 encoding."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=str(path.parent),
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def _present_diff(original: str, updated: str) -> None:
    """Print a unified diff between ``original`` and ``updated`` strings."""

    diff = list(
        difflib.unified_diff(
            original.splitlines(),
            updated.splitlines(),
            fromfile="template",
            tofile="generated",
            lineterm="",
        )
    )
    if diff:
        for line in diff:
            print(line)
    else:
        print("No differences from the template.")

