from __future__ import annotations

import json
import math
import uuid
from contextlib import suppress
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from frame_compare.utils.atomic_write import write_text_atomic
from frame_compare.vs.types import TonemapSettings

if TYPE_CHECKING:
    from frame_compare.vsview.session_runtime import ComparisonSource, SessionData


def write_vsview_session_script(
    reference: Path,
    comparisons: list[Path],
    suggested_offsets_by_key: dict[str, int | None],
    audio_review_by_key: dict[str, str],
    cache_dir: Path,
    frame_props_by_stem: dict[str, dict[str, str | int | float]] | None = None,
    presentation_names_by_stem: dict[str, str] | None = None,
    short_names_by_stem: dict[str, str] | None = None,
    memory_limit_mb: int | None = None,
    preview_tonemap: TonemapSettings | None = None,
    source_indexes: dict[Path, Path] | None = None,
    source_index_generated_root: Path | None = None,
) -> Path:
    if source_indexes and source_index_generated_root is None:
        raise ValueError("source_index_generated_root is required when source_indexes are provided")

    sessions_dir = cache_dir / "vsview_sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    script_content = _build_script_content(
        reference=reference,
        comparisons=comparisons,
        suggested_offsets_by_key=suggested_offsets_by_key,
        audio_review_by_key=audio_review_by_key,
        frame_props_by_stem=frame_props_by_stem,
        presentation_names_by_stem=presentation_names_by_stem,
        short_names_by_stem=short_names_by_stem,
        memory_limit_mb=memory_limit_mb,
        preview_tonemap=preview_tonemap,
        source_indexes=source_indexes,
        source_index_generated_root=source_index_generated_root,
    )

    # Leave room for the result sidecar and its atomic-write sibling.
    reference_stem = reference.stem[:64]
    while len(reference_stem.encode("utf-8", errors="surrogateescape")) > 150:
        reference_stem = reference_stem[:-1]
    base_timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    script_path = None
    for _attempt in range(100):
        session_id = uuid.uuid4().hex
        script_name = f"vsview_{reference_stem}_{base_timestamp}_{session_id}.py"
        candidate_path = sessions_dir / script_name
        if _reserve_empty_file(candidate_path):
            script_path = candidate_path
            break

    if script_path is None:
        raise FileExistsError("could not reserve a unique VSView session script path")

    try:
        write_text_atomic(script_path, script_content, encoding="utf-8")
    except OSError:
        with suppress(OSError):
            script_path.unlink(missing_ok=True)
        raise
    return script_path


def _reserve_empty_file(path: Path) -> bool:
    try:
        path.touch(exist_ok=False)
    except FileExistsError:
        reserved = False
    else:
        reserved = True
    return reserved


def _preview_frame_props_for_script(
    frame_props_by_stem: dict[str, dict[str, str | int | float]] | None,
) -> dict[str, dict[str, str | int]]:
    if frame_props_by_stem is None:
        return {}

    props_for_script: dict[str, dict[str, str | int]] = {}
    for stem, props in frame_props_by_stem.items():
        clean_props: dict[str, str | int] = {}
        for key, value in props.items():
            if isinstance(value, int | str):
                clean_props[key] = value
            elif math.isfinite(value) and value.is_integer():
                clean_props[key] = int(value)
            else:
                clean_props[key] = str(value)
        props_for_script[stem] = clean_props
    return props_for_script


def _build_script_content(
    reference: Path,
    comparisons: list[Path],
    suggested_offsets_by_key: dict[str, int | None],
    audio_review_by_key: dict[str, str],
    frame_props_by_stem: dict[str, dict[str, str | int | float]] | None = None,
    presentation_names_by_stem: dict[str, str] | None = None,
    short_names_by_stem: dict[str, str] | None = None,
    memory_limit_mb: int | None = None,
    preview_tonemap: TonemapSettings | None = None,
    source_indexes: dict[Path, Path] | None = None,
    source_index_generated_root: Path | None = None,
) -> str:
    presentation_names = presentation_names_by_stem or {}
    indexes = source_indexes or {}
    targets: dict[str, ComparisonSource] = {}
    for comparison in comparisons:
        key = f"{reference.stem}:{comparison.stem}"
        targets[comparison.stem] = {
            "path": str(comparison),
            "display_name": presentation_names.get(comparison.stem, comparison.stem),
            "comparison_key": key,
            "suggested_offset": suggested_offsets_by_key.get(key),
            "audio_review": audio_review_by_key[key],
        }
        if comparison in indexes:
            targets[comparison.stem]["managed_index_path"] = str(indexes[comparison])
    frame_props = _preview_frame_props_for_script(frame_props_by_stem)
    data: SessionData = {
        "reference": {
            "label": reference.stem,
            "path": str(reference),
            "display_name": presentation_names.get(reference.stem, reference.stem),
        },
        "targets": targets,
        "frame_props_by_label": {
            label: dict(sorted(props.items())) for label, props in sorted(frame_props.items())
        },
        "short_names": dict(sorted((short_names_by_stem or {}).items())),
        "memory_limit_mb": memory_limit_mb,
        "preview_tonemap": asdict(preview_tonemap) if preview_tonemap is not None else None,
    }
    if reference in indexes:
        data["reference"]["managed_index_path"] = str(indexes[reference])
    if indexes and source_index_generated_root is not None:
        data["source_index_generated_root"] = str(source_index_generated_root)
    # Encode JSON as a Python string literal so filenames and JSON null/booleans
    # remain data rather than source.
    payload = json.dumps(data, ensure_ascii=True, allow_nan=False, indent=4)
    return f'''#!/usr/bin/env python3
"""VSView alignment verification session.

Sign convention:
    + trims reference (comparison starts AFTER reference)
    - trims comparison (comparison starts BEFORE reference)

Audio-derived offsets shown here are hints only. This session displays
untrimmed source clips so the operator can inspect source-frame positions.
"""
import json
from pathlib import Path
from typing import cast

from frame_compare.vsview.session_runtime import SessionData, run_session

SESSION_DATA = cast(SessionData, json.loads({payload!r}))

run_session(SESSION_DATA, Path(__file__))
'''
