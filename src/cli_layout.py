# pyright: reportUnsupportedDunderAll=false

"""Compatibility shim for `src.cli_layout` until Sub-phase 11.10 removes it."""

import sys as _sys

from src.frame_compare import cli_layout as _cli_layout
from src.frame_compare.cli_layout import *  # type: ignore[F401,F403]  # noqa: F403

_sys.modules[__name__] = _cli_layout
