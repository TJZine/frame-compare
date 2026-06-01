"""Tests for deterministic slow.pics upload planning."""

from pathlib import Path

import pytest

from frame_compare.services.errors import SlowpicsError
from frame_compare.services.slowpics_upload_plan import (
    SlowpicsUploadClip,
    build_slowpics_upload_plan,
)


def _png(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n")
    return path


def test_upload_plan_preserves_selected_frame_row_order(tmp_path: Path) -> None:
    reference_files = [_png(tmp_path / f"ref-{frame}.png") for frame in (42, 7, 99)]

    plan = build_slowpics_upload_plan(
        selected_frames=[42, 7, 99],
        clips=[SlowpicsUploadClip(label="Reference", image_name="Reference")],
        screenshots_by_label={"Reference": reference_files},
    )

    assert [row.selected_frame for row in plan.rows] == [42, 7, 99]
    assert [row.row_name for row in plan.rows] == ["42", "7", "99"]
    assert [row.sort_order for row in plan.rows] == [0, 1, 2]
    assert plan.file_paths == reference_files


def test_upload_plan_preserves_reference_then_comparison_image_order(tmp_path: Path) -> None:
    ref = _png(tmp_path / "10 - ref.png")
    encode_a = _png(tmp_path / "10 - encode-a.png")
    encode_b = _png(tmp_path / "10 - encode-b.png")

    plan = build_slowpics_upload_plan(
        selected_frames=[10],
        clips=[
            SlowpicsUploadClip(label="Reference", image_name="Reference"),
            SlowpicsUploadClip(label="Encode A", image_name="Encode A"),
            SlowpicsUploadClip(label="Encode B", image_name="Encode B"),
        ],
        screenshots_by_label={
            "Reference": [ref],
            "Encode A": [encode_a],
            "Encode B": [encode_b],
        },
    )

    row = plan.rows[0]
    assert [image.clip_label for image in row.images] == ["Reference", "Encode A", "Encode B"]
    assert [image.image_index for image in row.images] == [0, 1, 2]
    assert [image.sort_order for image in row.images] == [0, 1, 2]
    assert plan.file_paths == [ref, encode_a, encode_b]


def test_upload_plan_uses_source_filename_stems_for_image_names(tmp_path: Path) -> None:
    ref = _png(tmp_path / "screenshots" / "ui-reference-frame-10.png")
    encode = _png(tmp_path / "screenshots" / "ui-encode-frame-10.png")

    plan = build_slowpics_upload_plan(
        selected_frames=[10],
        clips=[
            SlowpicsUploadClip(label="Reference", image_name="source.reference.cut"),
            SlowpicsUploadClip(label="Encode UI Label", image_name="encode-final-v2"),
        ],
        screenshots_by_label={
            "Reference": [ref],
            "Encode UI Label": [encode],
        },
    )

    row = plan.rows[0]
    assert [image.image_name for image in row.images] == [
        "source.reference.cut",
        "encode-final-v2",
    ]
    assert [image.screenshot_path for image in row.images] == [ref, encode]


def test_upload_plan_ignores_stale_directory_png(tmp_path: Path) -> None:
    screenshot_dir = tmp_path / "screenshots"
    current_ref = _png(screenshot_dir / "10 - ref.png")
    current_encode = _png(screenshot_dir / "10 - encode.png")
    _png(screenshot_dir / "stale.png")

    plan = build_slowpics_upload_plan(
        selected_frames=[10],
        clips=[
            SlowpicsUploadClip(label="Reference", image_name="Reference"),
            SlowpicsUploadClip(label="Encode", image_name="Encode"),
        ],
        screenshots_by_label={
            "Reference": [current_ref],
            "Encode": [current_encode],
        },
    )

    assert plan.file_paths == [current_ref, current_encode]


def test_upload_plan_rejects_missing_screenshot_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.png"

    with pytest.raises(SlowpicsError, match="Planned slow.pics screenshot is missing"):
        build_slowpics_upload_plan(
            selected_frames=[10],
            clips=[SlowpicsUploadClip(label="Reference", image_name="Reference")],
            screenshots_by_label={"Reference": [missing]},
        )


def test_upload_plan_rejects_mismatched_screenshot_counts(tmp_path: Path) -> None:
    only_file = _png(tmp_path / "10 - ref.png")

    with pytest.raises(SlowpicsError, match="Mismatched slow.pics screenshot count"):
        build_slowpics_upload_plan(
            selected_frames=[10, 20],
            clips=[SlowpicsUploadClip(label="Reference", image_name="Reference")],
            screenshots_by_label={"Reference": [only_file]},
        )


def test_upload_plan_rejects_missing_clip_labels(tmp_path: Path) -> None:
    _png(tmp_path / "10 - ref.png")

    with pytest.raises(SlowpicsError, match="Missing screenshots for clip label 'Encode'"):
        build_slowpics_upload_plan(
            selected_frames=[10],
            clips=[
                SlowpicsUploadClip(label="Reference", image_name="Reference"),
                SlowpicsUploadClip(label="Encode", image_name="Encode"),
            ],
            screenshots_by_label={
                "Reference": [tmp_path / "10 - ref.png"],
            },
        )


def test_upload_plan_rejects_empty_image_display_names(tmp_path: Path) -> None:
    screenshot = _png(tmp_path / "10 - ref.png")

    with pytest.raises(SlowpicsError, match="Empty slow.pics image display name"):
        build_slowpics_upload_plan(
            selected_frames=[10],
            clips=[SlowpicsUploadClip(label="Reference", image_name="  ")],
            screenshots_by_label={"Reference": [screenshot]},
        )
