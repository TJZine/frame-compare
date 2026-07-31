"""Deterministic slow.pics upload membership planning."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from frame_compare.services.errors import SlowpicsError


@dataclass(frozen=True, slots=True)
class SlowpicsUploadClip:
    """Service-owned primitive clip identity for slow.pics upload planning."""

    label: str
    image_name: str


@dataclass(frozen=True, slots=True)
class SlowpicsPlannedImage:
    """A single image slot in a planned slow.pics upload."""

    row_index: int
    selected_frame: int
    image_index: int
    clip_label: str
    image_name: str
    screenshot_path: Path
    sort_order: int


@dataclass(frozen=True, slots=True)
class SlowpicsUploadRow:
    """A slow.pics comparison row for one selected frame."""

    row_index: int
    selected_frame: int
    row_name: str
    sort_order: int
    images: tuple[SlowpicsPlannedImage, ...]


@dataclass(frozen=True, slots=True)
class SlowpicsUploadPlan:
    """Complete row-major slow.pics upload plan for rendered screenshots."""

    rows: tuple[SlowpicsUploadRow, ...]

    @property
    def file_paths(self) -> list[Path]:
        """Return planned screenshot files in row-major upload order."""
        return [image.screenshot_path for row in self.rows for image in row.images]

    @property
    def screenshot_count(self) -> int:
        return sum(len(row.images) for row in self.rows)


def build_slowpics_upload_plan(
    *,
    selected_frames: list[int],
    clips: list[SlowpicsUploadClip],
    screenshots_by_label: dict[str, list[Path]],
) -> SlowpicsUploadPlan:
    """Build a deterministic upload plan from current render artifacts."""
    if not selected_frames:
        raise SlowpicsError("No selected frames available for slow.pics upload")
    if not clips:
        raise SlowpicsError("No clips available for slow.pics upload")

    _validate_unique_clip_labels(clips)
    _validate_image_names(clips)

    rows: list[SlowpicsUploadRow] = []
    for row_index, selected_frame in enumerate(selected_frames):
        images: list[SlowpicsPlannedImage] = []
        for image_index, clip in enumerate(clips):
            screenshot_paths = _screenshots_for_clip(
                clip=clip,
                selected_frames=selected_frames,
                screenshots_by_label=screenshots_by_label,
            )
            screenshot_path = screenshot_paths[row_index]
            _validate_screenshot_file(
                clip=clip, selected_frame=selected_frame, path=screenshot_path
            )
            images.append(
                SlowpicsPlannedImage(
                    row_index=row_index,
                    selected_frame=selected_frame,
                    image_index=image_index,
                    clip_label=clip.label,
                    image_name=clip.image_name,
                    screenshot_path=screenshot_path,
                    sort_order=image_index,
                )
            )
        rows.append(
            SlowpicsUploadRow(
                row_index=row_index,
                selected_frame=selected_frame,
                row_name=str(selected_frame),
                sort_order=row_index,
                images=tuple(images),
            )
        )

    return SlowpicsUploadPlan(rows=tuple(rows))


def _validate_unique_clip_labels(clips: list[SlowpicsUploadClip]) -> None:
    seen: set[str] = set()
    for clip in clips:
        if clip.label in seen:
            raise SlowpicsError(f"Duplicate clip label in slow.pics upload plan: {clip.label!r}")
        seen.add(clip.label)


def _validate_image_names(clips: list[SlowpicsUploadClip]) -> None:
    for clip in clips:
        if not clip.image_name.strip():
            raise SlowpicsError(
                f"Empty slow.pics image display name for clip label {clip.label!r}"
            )


def _screenshots_for_clip(
    *,
    clip: SlowpicsUploadClip,
    selected_frames: list[int],
    screenshots_by_label: dict[str, list[Path]],
) -> list[Path]:
    screenshot_paths = screenshots_by_label.get(clip.label)
    if screenshot_paths is None:
        raise SlowpicsError(f"Missing screenshots for clip label {clip.label!r}")

    expected_count = len(selected_frames)
    actual_count = len(screenshot_paths)
    if actual_count != expected_count:
        raise SlowpicsError(
            "Mismatched slow.pics screenshot count for "
            f"{clip.label!r}: expected {expected_count}, found {actual_count}"
        )
    return screenshot_paths


def _validate_screenshot_file(
    *,
    clip: SlowpicsUploadClip,
    selected_frame: int,
    path: Path,
) -> None:
    if not path.is_file():
        raise SlowpicsError(
            "Planned slow.pics screenshot is missing for "
            f"{clip.label!r} frame {selected_frame}: {path}"
        )
