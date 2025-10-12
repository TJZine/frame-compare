from __future__ import annotations

from importlib import resources
from pathlib import Path

import pytest

from src import config_paths
from src.config_template import copy_default_config


@pytest.fixture(name="template_bytes")
def fixture_template_bytes() -> bytes:
    return resources.files("data").joinpath("config.toml.template").read_bytes()


def test_copy_default_config_writes_template(tmp_path: Path, template_bytes: bytes) -> None:
    destination = tmp_path / "config.toml"

    written_path = copy_default_config(destination)

    assert written_path == destination
    assert destination.read_bytes() == template_bytes


def test_copy_default_config_uses_cli_default_path(
    tmp_path: Path, template_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    default_path = tmp_path / "data" / "config.toml"
    monkeypatch.setattr(config_paths, "DEFAULT_CONFIG_PATH", default_path)

    written_path = copy_default_config()

    assert written_path == default_path
    assert default_path.read_bytes() == template_bytes


def test_copy_default_config_refuses_to_overwrite(tmp_path: Path, template_bytes: bytes) -> None:
    destination = tmp_path / "config.toml"
    destination.write_bytes(template_bytes)

    with pytest.raises(FileExistsError):
        copy_default_config(destination)


def test_copy_default_config_overwrites_when_requested(tmp_path: Path) -> None:
    destination = tmp_path / "config.toml"
    destination.write_text("initial", encoding="utf-8")

    copy_default_config(destination, overwrite=True)

    contents = destination.read_text(encoding="utf-8")
    assert "[analysis]" in contents
