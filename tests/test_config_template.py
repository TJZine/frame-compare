from __future__ import annotations

from importlib import resources
from pathlib import Path

from importlib import resources
from pathlib import Path

import pytest

from src.config_template import (
    FILESYSTEM_TEMPLATE_PATH,
    TEMPLATE_ENV_VAR,
    copy_default_config,
)


@pytest.fixture(name="template_bytes")
def fixture_template_bytes() -> bytes:
    return FILESYSTEM_TEMPLATE_PATH.read_bytes()


def test_copy_default_config_writes_template(tmp_path: Path, template_bytes: bytes) -> None:
    destination = tmp_path / "config.toml"

    written_path = copy_default_config(destination)

    assert written_path == destination
    assert destination.read_bytes() == template_bytes


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


def test_copy_default_config_falls_back_without_packaged_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    template_bytes: bytes,
) -> None:
    destination = tmp_path / "config.toml"

    def _raise(*args: object, **kwargs: object) -> resources.Traversable:
        raise ModuleNotFoundError("data")

    monkeypatch.setattr(
        "src.config_template.resources.files",
        _raise,
    )

    written = copy_default_config(destination, overwrite=True)

    assert written == destination
    assert destination.read_bytes() == template_bytes


def test_copy_default_config_respects_env_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "config.toml"
    override_template = tmp_path / "custom-template.toml"
    override_template.write_text("[custom]\nvalue=1\n", encoding="utf-8")

    monkeypatch.setenv(TEMPLATE_ENV_VAR, str(override_template))

    try:
        written = copy_default_config(destination, overwrite=True)
    finally:
        monkeypatch.delenv(TEMPLATE_ENV_VAR, raising=False)

    assert written == destination
    assert destination.read_text(encoding="utf-8") == "[custom]\nvalue=1\n"
