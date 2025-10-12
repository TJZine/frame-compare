"""Helpers for working with the packaged configuration template."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Final

_TEMPLATE_PACKAGE: Final[str] = "data"
_TEMPLATE_FILENAME: Final[str] = "config.toml.template"


def copy_default_config(
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Copy the packaged default configuration to ``destination``.

    Parameters
    ----------
    destination:
        File path to write. This must point to a user-writable location such as a
        project workspace or configuration directory.
    overwrite:
        Whether to overwrite an existing file. When ``False`` (the default), a
        :class:`FileExistsError` is raised if the destination already exists.

    Returns
    -------
    Path
        The path where the configuration template was written.

    Raises
    ------
    ValueError
        If ``destination`` is ``None``.
    """

    if destination is None:
        raise ValueError("destination must be provided")

    target = Path(destination)
    template = resources.files(_TEMPLATE_PACKAGE).joinpath(_TEMPLATE_FILENAME)

    if target.exists() and not overwrite:
        raise FileExistsError(f"{target} already exists; pass overwrite=True to replace it.")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(template.read_bytes())
    return target


__all__ = ["copy_default_config"]
