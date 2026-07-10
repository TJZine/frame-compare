"""Contract tests for strict slow.pics title configuration."""

import pytest
from pydantic import ValidationError

from frame_compare.config.schema_models import SlowpicsConfig, SourceOverrideConfig
from frame_compare.config.slowpics import (
    SLOWPICS_TITLE_TEMPLATE_FIELDS,
    render_slowpics_title_template,
)


def test_renderer_supports_every_allowed_placeholder_and_missing_values() -> None:
    context = {name: name.lower() for name in SLOWPICS_TITLE_TEMPLATE_FIELDS}
    template = "|".join(f"${{{name}}}" for name in sorted(SLOWPICS_TITLE_TEMPLATE_FIELDS))

    assert render_slowpics_title_template(template, context) == "|".join(
        name.lower() for name in sorted(SLOWPICS_TITLE_TEMPLATE_FIELDS)
    )
    assert render_slowpics_title_template("${Title}/${Year}", {}) == "/"


def test_renderer_supports_literal_text_and_escaped_dollar() -> None:
    assert render_slowpics_title_template("Cost $$5: ${Title}", {"Title": "Example"}) == (
        "Cost $5: Example"
    )


@pytest.mark.parametrize(
    "template",
    ["$", "$Title", "${Title", "${}", "${Unknown}", "${Title.value}", "${Title[0]}"],
)
def test_slowpics_config_rejects_unknown_or_malformed_templates(template: str) -> None:
    with pytest.raises(ValidationError):
        SlowpicsConfig(title_template=template)


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


@pytest.mark.parametrize(
    "payload",
    [
        {"tmdb_id": 1},
        {"tmdb_media_type": "movie"},
        {"tmdb_id": True, "tmdb_media_type": "movie"},
        {"tmdb_id": "1", "tmdb_media_type": "movie"},
        {"tmdb_id": 0, "tmdb_media_type": "movie"},
        {"tmdb_id": -1, "tmdb_media_type": "tv"},
    ],
)
def test_slowpics_config_requires_strict_positive_paired_tmdb_values(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        SlowpicsConfig.model_validate(payload)


@pytest.mark.parametrize("value", [True, "1", -1, 1_000_000])
def test_slowpics_config_rejects_invalid_remote_retention(value: object) -> None:
    with pytest.raises(ValidationError):
        SlowpicsConfig.model_validate({"remove_after_days": value})


def test_slowpics_config_accepts_remote_retention_bounds_and_timeout_floor() -> None:
    assert SlowpicsConfig(remove_after_days=0).remove_after_days == 0
    assert SlowpicsConfig(remove_after_days=999999).remove_after_days == 999999
    with pytest.raises(ValidationError):
        SlowpicsConfig(image_upload_timeout_seconds=9.99)


@pytest.mark.parametrize("value", ["true", "false", "yes", "off", 0, 1])
def test_slowpics_config_requires_strict_hentai_boolean(value: object) -> None:
    with pytest.raises(ValidationError):
        SlowpicsConfig.model_validate({"is_hentai": value})


def test_source_override_label_is_trimmed_and_strict() -> None:
    assert SourceOverrideConfig(label="  Reference Source  ").label == "Reference Source"
    for value in ("", "   ", "bad\tlabel", "\nwrapped\n", "\twrapped\r"):
        with pytest.raises(ValidationError):
            SourceOverrideConfig(label=value)


def test_slowpics_nested_unknown_key_remains_rejected() -> None:
    with pytest.raises(ValidationError):
        SlowpicsConfig.model_validate({"collection_name": "legacy"})
