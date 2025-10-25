from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import src.config_template as config_template
from src.config_template import (
    TEMPLATE_ENV_VAR,
    _read_template_bytes,
    copy_default_config,
)


@pytest.fixture(name="template_bytes")
def fixture_template_bytes() -> bytes:
    return _read_template_bytes()


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

    def _raise(*_args: object, **_kwargs: object) -> object:
        raise ModuleNotFoundError("data")

    monkeypatch.setattr(
        config_template.resources,
        "files",
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


def test_copy_default_config_available_from_wheel(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    project_root = Path(__file__).resolve().parents[1]

    try:
        import pip  # type: ignore  # noqa: F401
    except ModuleNotFoundError:
        subprocess.run(
            [sys.executable, "-m", "ensurepip", "--upgrade"],
            check=True,
        )

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--wheel-dir",
            str(dist_dir),
            str(project_root),
        ],
        check=True,
    )

    wheel_path = next(dist_dir.glob("frame_compare-*.whl"))
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PYTHONPATH"] = str(wheel_path)

    script = (
        "from pathlib import Path\n"
        "import tempfile\n"
        "from src.config_template import copy_default_config\n"
        "dest = Path(tempfile.mkdtemp()) / 'config.toml'\n"
        "copy_default_config(dest)\n"
        "print(dest.exists())\n"
    )

    proc = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),
    )

    assert "True" in proc.stdout
