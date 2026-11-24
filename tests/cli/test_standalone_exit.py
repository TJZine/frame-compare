"""Standalone exit policy must not escape into reusable application invocations."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("target", "code", "custom_handler"),
    [
        ("console_main", 130, False),
        ("console_main", 0, False),
        ("console_main", 2, False),
        ("app", 130, False),
        ("console_main", 130, True),
    ],
)
def test_shutdown_signal_preserves_exit_and_caller_ownership(
    target: str,
    code: int,
    custom_handler: bool,
) -> None:
    script = """
import atexit, json, signal, sys
from frame_compare.cli import entry
target, code, custom = sys.argv[1], int(sys.argv[2]), sys.argv[3] == 'True'
delivered = []
def owner(signum, frame):
    delivered.append('custom')
if custom:
    signal.signal(signal.SIGINT, owner)
def interrupted_app():
    raise SystemExit(code)
entry.app = interrupted_app
def shutdown():
    try:
        signal.raise_signal(signal.SIGINT)
    except KeyboardInterrupt:
        delivered.append('keyboard_interrupt')
    print(json.dumps({'delivered': delivered}), flush=True)
atexit.register(shutdown)
getattr(entry, target)()
"""
    result = subprocess.run(
        [sys.executable, "-c", script, target, str(code), str(custom_handler)],
        cwd=Path(__file__).parents[2],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == code, result.stdout + result.stderr
    assert result.stderr == ""
    expected = (
        ["custom"]
        if custom_handler
        else (
            []
            if sys.platform == "win32" and target == "console_main" and code == 130
            else ["keyboard_interrupt"]
        )
    )
    assert json.loads(result.stdout) == {"delivered": expected}
