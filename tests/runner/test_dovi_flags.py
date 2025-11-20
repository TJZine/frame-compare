"""Regression tests covering Dolby Vision CLI overrides."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, cast

import pytest
from click.testing import CliRunner

import frame_compare
from src.frame_compare import runner as runner_module
from tests.helpers.runner_env import (
    _CliRunnerEnv,
    _make_config,
    _make_json_tail_stub,
)

_CLI_JSON_ENV = {"COLUMNS": "200"}

def _install_stubbed_runner(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner_env: _CliRunnerEnv,
) -> List[runner_module.RunRequest]:
    """Replace the runner with a deterministic stub that records overrides."""

    captured: List[runner_module.RunRequest] = []

    def _fake_run(
        request: runner_module.RunRequest,
        *,
        dependencies: runner_module.RunDependencies | None = None,
    ) -> runner_module.RunResult:
        captured.append(request)
        cfg = cli_runner_env.cfg
        overrides = request.tonemap_overrides or {}
        color_cfg = cfg.color
        override_value = overrides.get("use_dovi")
        if override_value is None:
            override_value = getattr(color_cfg, "use_dovi", None)
        visualize_lut_value = overrides.get("visualize_lut")
        if visualize_lut_value is None:
            visualize_lut_value = bool(getattr(color_cfg, "visualize_lut", False))
        show_clipping_value = overrides.get("show_clipping")
        if show_clipping_value is None:
            show_clipping_value = bool(getattr(color_cfg, "show_clipping", False))
        target_nits_value = overrides.get("target_nits", getattr(color_cfg, "target_nits", 100.0))
        preset_value = overrides.get("preset", getattr(color_cfg, "preset", "reference"))
        tone_curve_value = overrides.get("tone_curve", getattr(color_cfg, "tone_curve", "bt.2390"))
        metadata_value = overrides.get("metadata", getattr(color_cfg, "metadata", "auto"))
        json_tail = _make_json_tail_stub()
        tonemap_block = json_tail.setdefault("tonemap", {})
        tonemap_block["preset"] = preset_value
        tonemap_block["tone_curve"] = tone_curve_value
        tonemap_block["target_nits"] = float(target_nits_value)
        tonemap_block["use_dovi"] = override_value
        tonemap_block["metadata"] = metadata_value
        tonemap_block["visualize_lut"] = visualize_lut_value
        tonemap_block["show_clipping"] = show_clipping_value
        tonemap_block["overlay_enabled"] = bool(getattr(color_cfg, "overlay_enabled", True))
        tonemap_block["overlay_mode"] = getattr(color_cfg, "overlay_mode", "minimal")
        tonemap_block["verify_luma_threshold"] = float(getattr(color_cfg, "verify_luma_threshold", 0.1))
        if override_value is None:
            tonemap_block["use_dovi_label"] = "auto"
        else:
            tonemap_block["use_dovi_label"] = "on" if override_value else "off"
        overlay_block = json_tail.setdefault("overlay", {})
        overlay_block["enabled"] = bool(getattr(color_cfg, "overlay_enabled", True))
        overlay_block["template"] = getattr(
            color_cfg,
            "overlay_text_template",
            "Tonemapping Algorithm: bt.2390",
        )
        overlay_block["mode"] = getattr(color_cfg, "overlay_mode", "minimal")
        overlay_block["diagnostics"] = {
            "dv": {
                "enabled": override_value,
                "label": tonemap_block.get("use_dovi_label", "auto"),
                "metadata_present": False,
                "has_l1_stats": False,
            },
            "frame_metrics": {
                "enabled": False,
                "per_frame": {},
                "gating": {
                    "config": False,
                    "cli_override": None,
                    "overlay_mode": overlay_block["mode"],
                },
            },
        }
        verify_block = json_tail.setdefault("verify", {})
        verify_block["threshold"] = float(getattr(color_cfg, "verify_luma_threshold", 0.1))
        cache_block = json_tail.setdefault("cache", {})
        cache_block.setdefault("reason", "stub")

        out_dir = Path(cli_runner_env.media_root / cfg.screenshots.directory_name)
        out_dir.mkdir(parents=True, exist_ok=True)
        return runner_module.RunResult(
            files=[],
            frames=[],
            out_dir=out_dir,
            out_dir_created=True,
            out_dir_created_path=out_dir,
            root=cli_runner_env.media_root,
            config=cfg,
            image_paths=[],
            json_tail=json_tail,
        )

    monkeypatch.setattr(runner_module, "run", _fake_run)
    return captured


def _extract_json_tail(output: str) -> Dict[str, Any]:
    """Parse the JSON tail emitted by the CLI run helper."""

    stripped = output.strip()
    if not stripped:
        raise AssertionError("JSON tail was not emitted")
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise AssertionError("JSON tail payload was not valid JSON") from exc


def test_cli_without_tm_flags_inherits_config(
    cli_runner_env: _CliRunnerEnv,
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
) -> None:
    """Ensure the Click entrypoint does not inject implicit DoVi overrides."""

    cfg = _make_config(cli_runner_env.media_root)
    cfg.color.use_dovi = True
    cli_runner_env.reinstall(cfg)
    captured = _install_stubbed_runner(monkeypatch, cli_runner_env)

    direct_result = frame_compare.run_cli(None, None)
    assert direct_result.json_tail is not None
    tonemap_direct = direct_result.json_tail["tonemap"]
    assert tonemap_direct["use_dovi"] is True
    assert tonemap_direct["use_dovi_label"] == "on"
    assert len(captured) == 1
    assert (captured[0].tonemap_overrides or {}).get("use_dovi") is None

    cli_result = runner.invoke(
        frame_compare.main,
        ["--no-color", "--json-pretty"],
        env=dict(_CLI_JSON_ENV),
    )
    assert cli_result.exit_code == 0, cli_result.output
    cli_tail = _extract_json_tail(cli_result.output)
    tonemap_cli = cli_tail["tonemap"]
    assert tonemap_cli["use_dovi"] is True
    assert tonemap_cli["use_dovi_label"] == "on"

    assert len(captured) == 2
    assert (captured[1].tonemap_overrides or {}).get("use_dovi") is None


def test_cli_tm_no_dovi_overrides_config(
    cli_runner_env: _CliRunnerEnv,
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
) -> None:
    """Verify --tm-no-dovi forces tonemap overrides."""

    cfg = _make_config(cli_runner_env.media_root)
    cfg.color.use_dovi = True
    cli_runner_env.reinstall(cfg)
    captured = _install_stubbed_runner(monkeypatch, cli_runner_env)

    result = runner.invoke(
        frame_compare.main,
        ["--no-color", "--json-pretty", "--tm-no-dovi"],
        env=dict(_CLI_JSON_ENV),
    )
    assert result.exit_code == 0, result.output
    tonemap_cli = _extract_json_tail(result.output)["tonemap"]
    assert tonemap_cli["use_dovi"] is False
    assert tonemap_cli["use_dovi_label"] == "off"

    assert len(captured) == 1
    overrides = captured[0].tonemap_overrides
    assert overrides is not None and overrides["use_dovi"] is False


def test_cli_tm_use_dovi_can_force_override(
    cli_runner_env: _CliRunnerEnv,
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
) -> None:
    """Verify --tm-use-dovi overrides config defaults when explicitly set."""

    cfg = _make_config(cli_runner_env.media_root)
    cfg.color.use_dovi = False
    cli_runner_env.reinstall(cfg)
    captured = _install_stubbed_runner(monkeypatch, cli_runner_env)

    result = runner.invoke(
        frame_compare.main,
        ["--no-color", "--json-pretty", "--tm-use-dovi"],
        env=dict(_CLI_JSON_ENV),
    )
    assert result.exit_code == 0, result.output
    tonemap_cli = _extract_json_tail(result.output)["tonemap"]
    assert tonemap_cli["use_dovi"] is True
    assert tonemap_cli["use_dovi_label"] == "on"

    assert len(captured) == 1
    overrides = captured[0].tonemap_overrides
    assert overrides is not None and overrides["use_dovi"] is True


def test_cli_visualize_lut_flags_respect_cli_source(
    cli_runner_env: _CliRunnerEnv,
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
) -> None:
    """Verify --tm-visualize-lut/--tm-no-visualize-lut only override when passed."""

    cfg = _make_config(cli_runner_env.media_root)
    cfg.color.visualize_lut = True
    cli_runner_env.reinstall(cfg)
    captured = _install_stubbed_runner(monkeypatch, cli_runner_env)

    default_result = runner.invoke(
        frame_compare.main,
        ["--no-color", "--json-pretty"],
        env=dict(_CLI_JSON_ENV),
    )
    assert default_result.exit_code == 0, default_result.output
    tonemap_default = _extract_json_tail(default_result.output)["tonemap"]
    assert tonemap_default["visualize_lut"] is True
    assert (captured[0].tonemap_overrides or {}).get("visualize_lut") is None

    disable_result = runner.invoke(
        frame_compare.main,
        ["--no-color", "--json-pretty", "--tm-no-visualize-lut"],
        env=dict(_CLI_JSON_ENV),
    )
    assert disable_result.exit_code == 0, disable_result.output
    tonemap_disable = _extract_json_tail(disable_result.output)["tonemap"]
    assert tonemap_disable["visualize_lut"] is False
    overrides = captured[1].tonemap_overrides
    assert overrides is not None and overrides["visualize_lut"] is False

    enable_result = runner.invoke(
        frame_compare.main,
        ["--no-color", "--json-pretty", "--tm-visualize-lut"],
        env=dict(_CLI_JSON_ENV),
    )
    assert enable_result.exit_code == 0, enable_result.output
    tonemap_enable = _extract_json_tail(enable_result.output)["tonemap"]
    assert tonemap_enable["visualize_lut"] is True
    overrides = captured[2].tonemap_overrides
    assert overrides is not None and overrides["visualize_lut"] is True


def test_cli_show_clipping_flags_respect_cli_source(
    cli_runner_env: _CliRunnerEnv,
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
) -> None:
    """Verify --tm-show-clipping/--tm-no-show-clipping follow explicit CLI input."""

    cfg = _make_config(cli_runner_env.media_root)
    cfg.color.show_clipping = False
    cli_runner_env.reinstall(cfg)
    captured = _install_stubbed_runner(monkeypatch, cli_runner_env)

    default_result = runner.invoke(
        frame_compare.main,
        ["--no-color", "--json-pretty"],
        env=dict(_CLI_JSON_ENV),
    )
    assert default_result.exit_code == 0, default_result.output
    tonemap_default = _extract_json_tail(default_result.output)["tonemap"]
    assert tonemap_default["show_clipping"] is False
    assert (captured[0].tonemap_overrides or {}).get("show_clipping") is None

    enable_result = runner.invoke(
        frame_compare.main,
        ["--no-color", "--json-pretty", "--tm-show-clipping"],
        env=dict(_CLI_JSON_ENV),
    )
    assert enable_result.exit_code == 0, enable_result.output
    tonemap_enable = _extract_json_tail(enable_result.output)["tonemap"]
    assert tonemap_enable["show_clipping"] is True
    overrides = captured[1].tonemap_overrides
    assert overrides is not None and overrides["show_clipping"] is True

    disable_result = runner.invoke(
        frame_compare.main,
        ["--no-color", "--json-pretty", "--tm-no-show-clipping"],
        env=dict(_CLI_JSON_ENV),
    )
    assert disable_result.exit_code == 0, disable_result.output
    tonemap_disable = _extract_json_tail(disable_result.output)["tonemap"]
    assert tonemap_disable["show_clipping"] is False
    overrides = captured[2].tonemap_overrides
    assert overrides is not None and overrides["show_clipping"] is False


def test_cli_tm_target_default_map_defer_to_config(
    cli_runner_env: _CliRunnerEnv,
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
) -> None:
    """Values from Click default maps should not override the loaded config."""

    cfg = _make_config(cli_runner_env.media_root)
    cfg.color.target_nits = 203.0
    cli_runner_env.reinstall(cfg)
    captured = _install_stubbed_runner(monkeypatch, cli_runner_env)

    result = runner.invoke(
        frame_compare.main,
        ["--no-color", "--json-pretty"],
        default_map={"tm_target": 321.0},
        env=dict(_CLI_JSON_ENV),
    )
    assert result.exit_code == 0, result.output
    tonemap_cli = _extract_json_tail(result.output)["tonemap"]
    assert tonemap_cli["target_nits"] == pytest.approx(203.0)
    overrides = captured[0].tonemap_overrides or {}
    assert "target_nits" not in overrides


def test_cli_tm_target_flag_overrides_config(
    cli_runner_env: _CliRunnerEnv,
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
) -> None:
    """Explicit --tm-target flags must override config defaults."""

    cfg = _make_config(cli_runner_env.media_root)
    cfg.color.target_nits = 150.0
    cli_runner_env.reinstall(cfg)
    captured = _install_stubbed_runner(monkeypatch, cli_runner_env)

    result = runner.invoke(
        frame_compare.main,
        ["--no-color", "--json-pretty", "--tm-target", "275.0"],
        env=dict(_CLI_JSON_ENV),
    )
    assert result.exit_code == 0, result.output
    tonemap_cli = _extract_json_tail(result.output)["tonemap"]
    assert tonemap_cli["target_nits"] == pytest.approx(275.0)
    overrides = captured[0].tonemap_overrides
    assert overrides is not None and overrides["target_nits"] == pytest.approx(275.0)


def test_cli_overlay_and_verify_blocks_follow_config(
    cli_runner_env: _CliRunnerEnv,
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
) -> None:
    """Overlay + verify telemetry should reflect config-driven defaults in both entry points."""

    cfg = _make_config(cli_runner_env.media_root)
    cfg.color.overlay_enabled = False
    cfg.color.overlay_mode = "diagnostic"
    cfg.color.overlay_text_template = "Overlay {tone_curve}"
    cfg.color.verify_luma_threshold = 0.42
    cli_runner_env.reinstall(cfg)
    _install_stubbed_runner(monkeypatch, cli_runner_env)

    direct_result = frame_compare.run_cli(None, None)
    assert direct_result.json_tail is not None
    overlay_direct = cast(Dict[str, Any], direct_result.json_tail["overlay"])
    verify_direct = direct_result.json_tail["verify"]
    assert overlay_direct["enabled"] is False
    assert overlay_direct["template"] == "Overlay {tone_curve}"
    assert overlay_direct["mode"] == "diagnostic"
    diagnostics_block = cast(Dict[str, Any], overlay_direct["diagnostics"])
    assert diagnostics_block["frame_metrics"]["enabled"] is False
    assert verify_direct["threshold"] == pytest.approx(0.42)

    cli_result = runner.invoke(
        frame_compare.main,
        ["--no-color", "--json-pretty"],
        env=dict(_CLI_JSON_ENV),
    )
    assert cli_result.exit_code == 0, cli_result.output
    cli_tail = _extract_json_tail(cli_result.output)
    cli_overlay = cast(Dict[str, Any], cli_tail["overlay"])
    assert cli_overlay["enabled"] is False
    assert cli_overlay["template"] == "Overlay {tone_curve}"
    assert cli_overlay["mode"] == "diagnostic"
    cli_diag = cast(Dict[str, Any], cli_overlay["diagnostics"])
    assert cli_diag["frame_metrics"]["enabled"] is False
    assert cli_tail["verify"]["threshold"] == pytest.approx(0.42)
