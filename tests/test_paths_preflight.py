from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

import frame_compare
from src.config_template import copy_default_config


def test_prepare_preflight_cli_root_seeds_config(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    ctx = frame_compare._prepare_preflight(
        cli_root=str(workspace),
        config_override=None,
        input_override=None,
        ensure_config=True,
        create_dirs=True,
        create_media_dir=True,
    )

    assert ctx.workspace_root == workspace.resolve()
    assert ctx.media_root == workspace / "comparison_videos"
    assert ctx.config_path == workspace / "config" / "config.toml"
    assert ctx.config_path.exists()
    assert (ctx.media_root).is_dir()


def test_prepare_preflight_env_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_root = tmp_path / "env-root"
    monkeypatch.setenv("FRAME_COMPARE_ROOT", str(env_root))
    try:
        ctx = frame_compare._prepare_preflight(
            cli_root=None,
            config_override=None,
            input_override=None,
            ensure_config=True,
            create_dirs=True,
            create_media_dir=True,
        )
    finally:
        monkeypatch.delenv("FRAME_COMPARE_ROOT", raising=False)

    assert ctx.workspace_root == env_root.resolve()
    assert ctx.media_root == env_root / "comparison_videos"


def test_prepare_preflight_sentinel_discovery(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "comparison_videos").mkdir(parents=True)
    (project / "subdir").mkdir(parents=True)
    monkeypatch.chdir(project / "subdir")

    ctx = frame_compare._prepare_preflight(
        cli_root=None,
        config_override=None,
        input_override=None,
        ensure_config=False,
        create_dirs=False,
        create_media_dir=False,
    )

    assert ctx.workspace_root == project.resolve()
    assert ctx.media_root == project / "comparison_videos"
    assert not ctx.config_path.exists()
    assert "defaults" in " ".join(ctx.warnings)


def test_prepare_preflight_rejects_site_packages(tmp_path: Path) -> None:
    root = tmp_path / "lib" / "python" / "site-packages" / "frame_compare"
    with pytest.raises(frame_compare.CLIAppError):
        frame_compare._prepare_preflight(
            cli_root=str(root),
            config_override=None,
            input_override=None,
            ensure_config=True,
            create_dirs=True,
            create_media_dir=True,
        )


def test_collect_path_diagnostics_reports_expected_structure(tmp_path: Path) -> None:
    root = tmp_path / "diagnostics"
    report = frame_compare._collect_path_diagnostics(
        cli_root=str(root),
        config_override=None,
        input_override=None,
    )

    assert report["workspace_root"] == str(root.resolve())
    assert report["media_root"].endswith("comparison_videos")
    assert report["config_path"].endswith("config/config.toml")
    assert report["config_exists"] is False
    assert set(report["writable"].keys()) == {
        "workspace_root",
        "media_root",
        "config_dir",
        "screens_dir",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("analysis.frame_data_filename", "../escape.compframes"),
        ("analysis.frame_data_filename", "/tmp/outside.compframes"),
        ("audio_alignment.offsets_filename", "../escape_offsets.toml"),
        ("audio_alignment.offsets_filename", "/tmp/outside_offsets.toml"),
    ),
)
def test_collect_path_diagnostics_rejects_escaped_subpaths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
) -> None:
    """
    Ensure user-configured cache or offsets paths cannot escape the media root.
    """

    cfg = frame_compare._fresh_app_config()
    target_section, target_attr = field.split(".")
    setattr(getattr(cfg, target_section), target_attr, value)

    monkeypatch.setattr(frame_compare, "load_config", lambda _: cfg)

    with pytest.raises(frame_compare.CLIAppError) as excinfo:
        frame_compare._collect_path_diagnostics(
            cli_root=str(tmp_path),
            config_override="ignored",
            input_override=None,
        )

    assert target_attr in str(excinfo.value)


def test_copy_default_config_matches_template(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    copy_default_config(target)
    template = (Path(__file__).resolve().parent.parent / "src" / "data" / "config.toml.template").read_text()
    assert target.read_text() == template


def test_cli_write_config_creates_under_root(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(frame_compare.main, ["--root", str(tmp_path), "--write-config"])
    assert result.exit_code == 0
    config_file = tmp_path / "config" / "config.toml"
    assert config_file.exists()
    assert "Config ensured at" in result.output


def test_cli_diagnose_rejects_site_packages_root(tmp_path: Path) -> None:
    runner = CliRunner()
    site_root = tmp_path / "lib" / "python" / "site-packages" / "frame_compare"
    result = runner.invoke(frame_compare.main, ["--root", str(site_root), "--diagnose-paths"])
    assert result.exit_code != 0
    assert "site-packages" in result.output
