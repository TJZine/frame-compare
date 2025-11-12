# pyright: reportUnsupportedDunderAll=false

"""Compatibility shim for `src.report` until Sub-phase 11.10 removes it."""

import sys as _sys

from src.frame_compare import report as _report
from src.frame_compare.report import *  # type: ignore[F401,F403]  # noqa: F403

_sys.modules[__name__] = _report
