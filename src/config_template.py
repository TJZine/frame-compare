# pyright: reportUnsupportedDunderAll=false

"""Compatibility shim for `src.config_template` until Sub-phase 11.10 removes it."""

import sys as _sys

from src.frame_compare import config_template as _config_template
from src.frame_compare.config_template import *  # type: ignore[F401,F403]  # noqa: F403

_sys.modules[__name__] = _config_template
