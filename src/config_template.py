"""Helpers for copying the configuration template in both packaged and source layouts."""

from __future__ import annotations

import os
import tempfile
from importlib import resources
from pathlib import Path
from typing import Final

_TEMPLATE_PACKAGE: Final[str] = "data"
_TEMPLATE_FILENAME: Final[str] = "config.toml.template"
TEMPLATE_ENV_VAR: Final[str] = "FRAME_COMPARE_TEMPLATE_PATH"
FILESYSTEM_TEMPLATE_PATH: Final[Path] = (
    Path(__file__).resolve().parent / "data" / _TEMPLATE_FILENAME
)


def _read_template_bytes() -> bytes:
    """Return the template bytes from the packaged module or filesystem fallback."""

    override = os.environ.get(TEMPLATE_ENV_VAR)
    if override:
        candidate = Path(override).expanduser()
        if candidate.is_dir():
            candidate = candidate / _TEMPLATE_FILENAME
        try:
            return candidate.read_bytes()
        except OSError as exc:
            raise FileNotFoundError(
                f"Unable to read config template override at {candidate}: {exc}"
            ) from exc

    try:
        template = resources.files(_TEMPLATE_PACKAGE).joinpath(_TEMPLATE_FILENAME)
        return template.read_bytes()
    except (FileNotFoundError, ModuleNotFoundError):
        try:
            return FILESYSTEM_TEMPLATE_PATH.read_bytes()
        except OSError as exc:
            raise FileNotFoundError(
                "Unable to locate config template; expected packaged module 'data' "
                f"or filesystem fallback {FILESYSTEM_TEMPLATE_PATH}: {exc}"
            ) from exc


def copy_default_config(
    destination: str | Path | None = None,
    *,
    overwrite: bool = False,
) -> Path:
    """Copy the packaged default configuration to ``destination``.

    Parameters
    ----------
    destination:
        File path to write. When omitted, the file is written as ``config.toml``
        in the current working directory.
    overwrite:
        Whether to overwrite an existing file. When ``False`` (the default), a
        :class:`FileExistsError` is raised if the destination already exists.

    Returns
    -------
    Path
        The path where the configuration template was written.
    """

    target = Path(destination) if destination is not None else Path.cwd() / "config.toml"
    template_bytes = _read_template_bytes()

    if target.exists() and not overwrite:
        raise FileExistsError(f"{target} already exists; pass overwrite=True to replace it.")

    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb",
            delete=False,
            dir=str(target.parent),
        ) as handle:
            handle.write(template_bytes)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(temp_path, target)
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
    return target


__all__ = [
    "FILESYSTEM_TEMPLATE_PATH",
    "TEMPLATE_ENV_VAR",
    "copy_default_config",
]
