from __future__ import annotations

import click

from frame_compare import CLIAppError, ScreenshotError, vs_core


def test_runtime_exception_hierarchy() -> None:
    assert issubclass(CLIAppError, (RuntimeError, click.ClickException))
    assert issubclass(ScreenshotError, RuntimeError)
    assert issubclass(vs_core.ClipInitError, RuntimeError)
    assert issubclass(vs_core.ClipProcessError, RuntimeError)
