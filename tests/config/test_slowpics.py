"""Contract tests for strict slow.pics title configuration."""

import pytest
from pydantic import ValidationError

from frame_compare.config.schema_models import SlowpicsConfig, SourceOverrideConfig
from frame_compare.config.slowpics import (
    render_slowpics_title_template,
    validate_slowpics_title_template,
)


@pytest.mark.parametrize(
    ("template", "context", "expected"),
    [
        ("${Title}/${Year}", {}, "/"),
        ("Cost $$5: ${Title}", {"Title": "Example"}, "Cost $5: Example"),
        ("${Title}", {"Title": "Good", "Unused": "bad\n"}, "Good"),
    ],
    ids=["missing-values", "escaped-dollar", "unused-control"],
)
def test_renderer_substitutes_only_used_template_values(
    template: str, context: dict[str, str], expected: str
) -> None:
    assert render_slowpics_title_template(template, context) == expected


@pytest.mark.parametrize("control", ["\x00", "\n", "\u0085"])
def test_template_helpers_reject_unicode_control_characters(control: str) -> None:
    with pytest.raises(ValueError, match="title_template must not contain control characters"):
        validate_slowpics_title_template(f"bad{control}template")

    with pytest.raises(
        ValueError,
        match="title_template context value Title must not contain control characters",
    ):
        render_slowpics_title_template("${Title}", {"Title": f"bad{control}context"})


@pytest.mark.parametrize(
    "payload",
    [
        {"title_template": "$"},
        {"title_template": "$Title"},
        {"title_template": "${Title"},
        {"title_template": "${}"},
        {"title_template": "${Unknown}"},
        {"title_template": "${Title.value}"},
        {"title_template": "${Title[0]}"},
        {"remove_after_days": True},
        {"remove_after_days": "1"},
        {"remove_after_days": -1},
        {"remove_after_days": 1_000_000},
        {"is_hentai": "true"},
        {"is_hentai": "false"},
        {"is_hentai": "yes"},
        {"is_hentai": "off"},
        {"is_hentai": 0},
        {"is_hentai": 1},
        {"tmdb_id": 1},
        {"tmdb_media_type": "movie"},
        {"tmdb_id": True, "tmdb_media_type": "movie"},
        {"tmdb_id": "1", "tmdb_media_type": "movie"},
        {"tmdb_id": 0, "tmdb_media_type": "movie"},
        {"tmdb_id": -1, "tmdb_media_type": "tv"},
        {"collection_name": "legacy"},
    ],
)
def test_slowpics_config_rejects_invalid_payloads(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SlowpicsConfig.model_validate(payload)


def test_slowpics_config_trims_title_fields_and_rejects_conflicts_and_controls() -> None:
    config = SlowpicsConfig(title="  Example  ", title_suffix="  [Compare]  ")
    assert config.title == "Example"
    assert config.title_suffix == "[Compare]"

    with pytest.raises(ValidationError):
        SlowpicsConfig(title="Example", title_template="${Title}")
    for field_name in ("title", "title_template", "title_suffix"):
        for value in ("bad\nvalue", "\nwrapped\n", "\twrapped\r"):
            with pytest.raises(ValidationError):
                SlowpicsConfig.model_validate({field_name: value})


def test_slowpics_config_accepts_remote_retention_bounds_and_timeout_floor() -> None:
    assert SlowpicsConfig(remove_after_days=0).remove_after_days == 0
    assert SlowpicsConfig(remove_after_days=999999).remove_after_days == 999999
    with pytest.raises(ValidationError):
        SlowpicsConfig(image_upload_timeout_seconds=9.99)


def test_source_override_label_is_trimmed_and_strict() -> None:
    assert SourceOverrideConfig(label="  Reference Source  ").label == "Reference Source"
    for value in ("", "   ", "bad\tlabel", "\nwrapped\n", "\twrapped\r"):
        with pytest.raises(ValidationError):
            SourceOverrideConfig(label=value)
