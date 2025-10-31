"""HTML report generation utilities for offline comparison viewing."""

from __future__ import annotations

import html
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, TypedDict

from .analysis import SelectionDetail
from .datatypes import ReportConfig

_ASSET_DIR = Path(__file__).resolve().parent / "data" / "report"
_INDEX_TEMPLATE_PATH = _ASSET_DIR / "index.html"
_ASSETS = ("app.js", "app.css")
_INVALID_LABEL_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitise_label(label: str) -> str:
    cleaned = _INVALID_LABEL_PATTERN.sub("_", label)
    if os.name == "nt":
        cleaned = cleaned.rstrip(" .")
    cleaned = cleaned.strip()
    return cleaned or "comparison"


class EncodeEntryBase(TypedDict):
    label: str
    safe_label: str
    source: str


class EncodeEntryOptional(TypedDict, total=False):
    metadata: Dict[str, str]


class EncodeEntry(EncodeEntryBase, EncodeEntryOptional):
    """Typed representation of encodes in the report payload."""


class FileRecord(TypedDict):
    encode: str
    path: str
    safe_label: str


class FrameEntryBase(TypedDict):
    index: int
    files: List[FileRecord]
    label: Optional[str]


class FrameEntryOptional(TypedDict, total=False):
    detail: Dict[str, object]
    thumbnail: str


class FrameEntry(FrameEntryBase, FrameEntryOptional):
    """Typed representation of per-frame payload entries."""


def _normalise_default(label: Optional[str], encodes: Sequence[EncodeEntry]) -> Optional[str]:
    if not label:
        return None
    stripped = label.strip()
    if not stripped:
        return None
    for encode in encodes:
        if encode["label"] == stripped:
            return encode["label"]
    sanitised = _sanitise_label(stripped)
    for encode in encodes:
        if encode["safe_label"] == sanitised:
            return encode["label"]
    return None


def _detail_to_payload(detail: SelectionDetail) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "label": detail.label,
        "score": detail.score,
        "source": detail.source,
        "timecode": detail.timecode,
        "clip_role": detail.clip_role,
        "notes": detail.notes,
    }
    return {key: value for key, value in payload.items() if value is not None}


def _relative_path(path: Path, base: Path) -> str:
    try:
        rel = os.path.relpath(path, base)
    except ValueError:
        return path.resolve().as_posix()
    return rel.replace(os.sep, "/")


def generate_html_report(
    *,
    report_dir: Path,
    report_cfg: ReportConfig,
    frames: Sequence[int],
    selection_details: Mapping[int, SelectionDetail],
    image_paths: Sequence[str],
    plans: Sequence[Mapping[str, object]],
    metadata_title: Optional[str],
    include_metadata: str,
    slowpics_url: Optional[str],
) -> Path:
    """
    Generate the HTML report alongside existing screenshots.

    Parameters:
        report_dir: Resolved output directory for the report assets.
        report_cfg: Effective report configuration for the current run.
        frames: Ordered collection of selected frame indices.
        selection_details: Mapping of frame index to SelectionDetail metadata.
        image_paths: Sequence of absolute screenshot paths produced by the run.
        plans: Sequence of dictionaries describing each encode (keys: label, metadata, path).
        metadata_title: Optional title inferred from media metadata.
        include_metadata: Either \"minimal\" or \"full\" to control payload verbosity.
        slowpics_url: Optional slow.pics URL associated with the run.

    Returns:
        Path to the generated ``index.html`` file.
    """

    report_dir.mkdir(parents=True, exist_ok=True)
    for asset in _ASSETS:
        shutil.copy2(_ASSET_DIR / asset, report_dir / asset)

    raw_title = report_cfg.title or metadata_title or "Frame Compare Report"
    document_title = raw_title.strip() or "Frame Compare Report"

    encode_entries: List[EncodeEntry] = []
    seen_safe: set[str] = set()
    for plan in plans:
        label = str(plan.get("label") or "").strip() or str(plan.get("path") or "")
        safe_label = _sanitise_label(label)
        source_path = plan.get("path")
        metadata = plan.get("metadata")
        entry: EncodeEntry = {
            "label": label,
            "safe_label": safe_label,
            "source": (
                str(source_path)
                if isinstance(source_path, Path)
                else (source_path if isinstance(source_path, str) else "")
            ),
        }
        if include_metadata == "full" and isinstance(metadata, Mapping):
            metadata_dict: Dict[str, str] = {
                str(k): str(v) for k, v in metadata.items() if v not in (None, "")
            }
            if metadata_dict:
                entry["metadata"] = metadata_dict
        if safe_label in seen_safe:
            continue
        seen_safe.add(safe_label)
        encode_entries.append(entry)

    files_by_frame: Dict[int, Dict[str, str]] = {}
    for path_str in image_paths:
        image_path = Path(path_str)
        base_name = image_path.stem
        if " - " not in base_name:
            continue
        frame_part, safe_label = base_name.split(" - ", 1)
        try:
            frame_idx = int(frame_part)
        except ValueError:
            continue
        rel_path = _relative_path(image_path, report_dir)
        files_by_frame.setdefault(frame_idx, {})[safe_label] = rel_path

    frames_sorted = [int(frame) for frame in frames]
    frame_payload: List[FrameEntry] = []
    for frame_idx in frames_sorted:
        files_for_frame = files_by_frame.get(frame_idx, {})
        records: List[FileRecord] = []
        for encode in encode_entries:
            safe_label = encode["safe_label"]
            rel_path = files_for_frame.get(safe_label)
            if not rel_path:
                continue
            records.append(
                {
                    "encode": encode["label"],
                    "path": rel_path,
                    "safe_label": safe_label,
                }
            )
        detail = selection_details.get(frame_idx)
        thumbnail_path: Optional[str] = None
        if records:
            # Prefer the first listed encode for consistent filmstrip thumbnails.
            thumbnail_path = records[0]["path"]
        frame_entry: FrameEntry = {
            "index": frame_idx,
            "files": records,
            "label": detail.label if detail else None,
        }
        if include_metadata == "full" and detail is not None:
            frame_entry["detail"] = _detail_to_payload(detail)
        if thumbnail_path:
            frame_entry["thumbnail"] = thumbnail_path
        frame_payload.append(frame_entry)

    defaults = {
        "left": _normalise_default(report_cfg.default_left_label, encode_entries),
        "right": _normalise_default(report_cfg.default_right_label, encode_entries),
    }

    data = {
        "title": document_title,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "encodes": encode_entries,
        "frames": frame_payload,
        "defaults": defaults,
        "include_metadata": include_metadata,
        "viewer_mode": report_cfg.default_mode,
        "slowpics_url": slowpics_url,
        "stats": {
            "frames": len(frame_payload),
            "encodes": len(encode_entries),
        },
    }

    data_path = report_dir / "data.json"
    json_text = json.dumps(data, indent=2, ensure_ascii=False)
    data_path.write_text(json_text, encoding="utf-8")

    template_text = _INDEX_TEMPLATE_PATH.read_text(encoding="utf-8")
    escaped_title = html.escape(document_title, quote=True)
    embedded_json = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    embedded_json = embedded_json.replace("</", "<\\/")
    html_output = template_text.replace("{{TITLE}}", escaped_title).replace("{{DATA_JSON}}", embedded_json)
    (report_dir / "index.html").write_text(html_output, encoding="utf-8")

    return report_dir / "index.html"
