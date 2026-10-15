from __future__ import annotations

import json
import math
import uuid
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from frame_compare.utils.atomic_write import write_text_atomic
from frame_compare.vs.source import source_index_path

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
) -> Path:
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
    )

    base_timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    script_path = None
    for _attempt in range(100):
        session_id = uuid.uuid4().hex
        script_name = f"vsview_{reference.stem}_{base_timestamp}_{session_id}.py"
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
) -> str:
    presentation_names = presentation_names_by_stem or {}
    targets: dict[str, ComparisonSource] = {}
    for comparison in comparisons:
        key = f"{reference.stem}:{comparison.stem}"
        targets[comparison.stem] = {
            "path": str(comparison),
            "index_path": str(source_index_path(comparison)),
            "display_name": presentation_names.get(comparison.stem, comparison.stem),
            "comparison_key": key,
            "suggested_offset": suggested_offsets_by_key.get(key),
            "audio_review": audio_review_by_key[key],
        }
    frame_props = _preview_frame_props_for_script(frame_props_by_stem)
    data: SessionData = {
        "reference": {
            "label": reference.stem,
            "path": str(reference),
            "index_path": str(source_index_path(reference)),
            "display_name": presentation_names.get(reference.stem, reference.stem),
        },
        "targets": targets,
        "frame_props_by_label": {
            label: dict(sorted(props.items())) for label, props in sorted(frame_props.items())
        },
        "short_names": dict(sorted((short_names_by_stem or {}).items())),
        "memory_limit_mb": memory_limit_mb,
    }
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
