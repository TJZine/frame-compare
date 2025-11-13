import logging
from pathlib import Path

import pytest

from src.config_loader import load_config


def test_center_pad_deprecated(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    cfg_path = tmp_path / "config.toml.template"
    cfg_path.write_text(
        """
[screenshots]
pad_to_canvas = "on"
center_pad = false
        """.strip(),
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING):
        app = load_config(str(cfg_path))

    assert app.screenshots.center_pad is True
    assert any("center_pad is deprecated and ignored" in message for message in caplog.messages)
