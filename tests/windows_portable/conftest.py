"""Native Windows portable verification environment."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def native_powershell_module_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    if os.name == "nt":
        # PS5.1 launched through Python otherwise inherits incompatible PS7 modules.
        # Each child interpreter initializes its own defaults; restore the parent
        # environment after the test instead of changing machine/user settings.
        monkeypatch.delenv("PSModulePath", raising=False)
