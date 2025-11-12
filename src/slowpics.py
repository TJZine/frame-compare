# pyright: reportUnsupportedDunderAll=false

"""Compatibility shim for `src.slowpics` until Sub-phase 11.10 removes it."""

import sys as _sys

from src.frame_compare import slowpics as _slowpics
from src.frame_compare.slowpics import *  # type: ignore[F401,F403]  # noqa: F403

_sys.modules[__name__] = _slowpics
