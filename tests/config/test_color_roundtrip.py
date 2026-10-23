"""Resolved color behavior survives persistence and partial preset application."""

from pathlib import Path

import pytest
import tomli_w

from frame_compare.config.loader import get_default_config, load_config
from frame_compare.config.overrides import CLIConfigOverrides, apply_cli_overrides
from frame_compare.config.persistence import dump_config_for_persistence
from frame_compare.config.presets import apply_preset, save_preset
from frame_compare.config.schema import ColorConfig, ToneCurve, TonemapPreset
from frame_compare.config.schema_enums import TonemapSpeed
from frame_compare.render.prepare import resolve_tonemap_settings
from frame_compare.vs.tonemap_presets import get_preset_settings


@pytest.mark.parametrize("curve", list(ToneCurve))
def test_highlight_preserve_opt_in_and_curve_override(curve: ToneCurve) -> None:
    from dataclasses import asdict

    config = get_default_config()
    baseline = resolve_tonemap_settings(config)
    assert baseline.knee_offset == 0.5
    selected = apply_cli_overrides(
        config, CLIConfigOverrides(tm_preset=TonemapPreset.HIGHLIGHT_PRESERVE)
    )
    preserved = resolve_tonemap_settings(selected)
    assert preserved.knee_offset == 1.0
    expected = asdict(baseline)
    expected.update(preset=TonemapPreset.HIGHLIGHT_PRESERVE, knee_offset=1.0)
    assert asdict(preserved) == expected
    changed = apply_cli_overrides(selected, CLIConfigOverrides(tm_curve=curve))
    resolved = resolve_tonemap_settings(changed)
    assert resolved.tone_curve is curve
    assert resolved.knee_offset == (1.0 if curve is ToneCurve.BT2390 else 0.5)
    assert resolve_tonemap_settings(config) == baseline


@pytest.mark.parametrize("preset", list(TonemapPreset))
@pytest.mark.parametrize("explicit_defaults", [False, True])
def test_color_semantics_survive_merges_and_persisted_reload(
    tmp_path: Path,
    preset: TonemapPreset,
    explicit_defaults: bool,
) -> None:
    config = get_default_config()
    color = ColorConfig(preset=preset)
    if explicit_defaults:
        color.target_nits = 100
        color.tone_curve = ColorConfig().tone_curve
        color.gamma_lift = False
        color.contrast_recovery = 0.3
    config.color = color
    expected = resolve_tonemap_settings(config)
    if not explicit_defaults:
        assert expected == get_preset_settings(preset)
    else:
        assert expected.target_nits == 100
        assert expected.tone_curve == ColorConfig().tone_curve
        assert expected.gamma_lift is False
        assert expected.contrast_recovery == 0.3

    config_path = tmp_path / "config.toml"
    config_path.write_text(tomli_w.dumps(dump_config_for_persistence(config)), encoding="utf-8")
    reloaded = load_config(config_path)
    assert resolve_tonemap_settings(reloaded) == expected
    assert reloaded.analysis.model_dump() == config.analysis.model_dump()

    unrelated = apply_cli_overrides(reloaded, CLIConfigOverrides(random_frame_count=42))
    assert resolve_tonemap_settings(unrelated) == expected

    (tmp_path / "partial.toml").write_text("[analysis]\nrandom_frame_count = 23\n")
    merged = apply_preset(unrelated, "partial", presets_dir=tmp_path)
    assert resolve_tonemap_settings(merged) == expected
    assert merged.analysis.random_frame_count == 23
    saved = save_preset("saved", merged, presets_dir=tmp_path)
    assert resolve_tonemap_settings(load_config(saved)) == expected


def test_partial_color_preset_preserves_only_authored_overrides(tmp_path: Path) -> None:
    config = get_default_config()
    config.color = ColorConfig(preset=TonemapPreset.FILMIC, target_nits=100)
    (tmp_path / "partial.toml").write_text("[color]\ngamma_lift = true\n")
    updated = apply_preset(config, "partial", presets_dir=tmp_path)
    resolved = resolve_tonemap_settings(updated)
    assert resolved.target_nits == 100
    assert resolved.tone_curve == get_preset_settings(TonemapPreset.FILMIC).tone_curve
    assert resolved.gamma_lift is True
    assert updated.color.model_fields_set & {
        "target_nits",
        "tone_curve",
        "gamma_lift",
        "contrast_recovery",
    } == {"target_nits", "gamma_lift"}


def test_fast_tonemap_speed_survives_persistence_and_is_not_preset_controlled(
    tmp_path: Path,
) -> None:
    config = get_default_config()
    config.color = ColorConfig(preset=TonemapPreset.FILMIC, tonemap_speed=TonemapSpeed.FAST)
    expected = resolve_tonemap_settings(config)
    assert expected.tonemap_speed is TonemapSpeed.FAST
    assert expected.dynamic_peak_detection is False

    config_path = tmp_path / "config.toml"
    config_path.write_text(tomli_w.dumps(dump_config_for_persistence(config)), encoding="utf-8")
    reloaded = load_config(config_path)
    assert reloaded.color.tonemap_speed is TonemapSpeed.FAST
    assert resolve_tonemap_settings(reloaded) == expected

    (tmp_path / "partial.toml").write_text('[color]\npreset = "reference"\n')
    updated = apply_preset(config, "partial", presets_dir=tmp_path)
    assert updated.color.tonemap_speed is TonemapSpeed.FAST
    assert resolve_tonemap_settings(updated).tonemap_speed is TonemapSpeed.FAST


@pytest.mark.parametrize("merge_kind", ["preset", "cli"])
@pytest.mark.parametrize(
    "ambient_change",
    ["valid_default", "invalid_default", "changed_environment", "malformed_environment"],
)
def test_resolved_config_merges_do_not_reacquire_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    merge_kind: str,
    ambient_change: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    default_path = tmp_path / "config" / "config.toml"
    default_path.parent.mkdir()
    if ambient_change.endswith("default"):
        default_path.write_text(
            "[color]\ntarget_nits = "
            + ("500" if ambient_change == "valid_default" else '"invalid-irrelevant-default"')
            + "\n"
        )
    selected = tmp_path / "selected.toml"
    selected.write_text(
        '[color]\npreset = "filmic"\n'
        '[tmdb]\napi_key = "retained-runtime-key"\n'
        '[slowpics]\nwebhook_url = "https://discord.com/api/webhooks/id/retained-runtime-token"\n'
        '[sources.overrides."reference.mkv"]\neffective_fps = "24000/1001"\n'
    )
    config = load_config(selected)
    expected = get_preset_settings(TonemapPreset.FILMIC)
    assert resolve_tonemap_settings(config) == expected

    if ambient_change == "changed_environment":
        monkeypatch.setenv("FRAME_COMPARE_COLOR__TARGET_NITS", "500")
    elif ambient_change == "malformed_environment":
        monkeypatch.setenv("FRAME_COMPARE_COLOR", '{"target_nits":')
        monkeypatch.setenv("FRAME_COMPARE_ANALYSIS__USER_FRAMES", "[")

    if merge_kind == "preset":
        (tmp_path / "partial.toml").write_text("[analysis]\nrandom_frame_count = 23\n")
        merged = apply_preset(config, "partial", presets_dir=tmp_path)
    else:
        merged = apply_cli_overrides(config, CLIConfigOverrides(random_frame_count=23))
    assert merged.analysis.random_frame_count == 23
    assert resolve_tonemap_settings(merged) == expected
    assert merged.color.model_fields_set.isdisjoint(
        {"target_nits", "tone_curve", "gamma_lift", "contrast_recovery"}
    )
    assert merged.tmdb.api_key == config.tmdb.api_key
    assert merged.slowpics.webhook_url == config.slowpics.webhook_url
    assert merged.sources.overrides == config.sources.overrides

    # Clear post-acquisition environment changes before intentionally reacquiring
    # the persisted config.
    monkeypatch.delenv("FRAME_COMPARE_COLOR__TARGET_NITS", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_COLOR", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_ANALYSIS__USER_FRAMES", raising=False)
    saved = save_preset("saved", merged, presets_dir=tmp_path)
    assert resolve_tonemap_settings(load_config(saved)) == expected


@pytest.mark.parametrize("merge_kind", ["preset", "cli", "secret_preset"])
def test_source_free_merges_preserve_validation_input_policy(
    tmp_path: Path, merge_kind: str
) -> None:
    from frame_compare.config.errors import ConfigValidationError

    config = get_default_config()
    with pytest.raises(ConfigValidationError) as exc_info:
        if merge_kind == "cli":
            apply_cli_overrides(config, CLIConfigOverrides(random_frame_count=-1))
        else:
            (tmp_path / "invalid.toml").write_text(
                '[tmdb]\napi_key = ["sentinel-secret"]\n'
                if merge_kind == "secret_preset"
                else "[analysis]\nrandom_frame_count = -1\n"
            )
            apply_preset(config, "invalid", presets_dir=tmp_path)
    errors = exc_info.value.validation_errors
    if merge_kind == "secret_preset":
        assert errors[0]["loc"] == ["tmdb", "api_key"]
        assert errors[0]["input"] == "<redacted>"
        assert "sentinel-secret" not in str(exc_info.value.context.to_dict())
    else:
        assert errors[0]["loc"] == ["analysis", "random_frame_count"]
        assert errors[0]["input"] == -1
