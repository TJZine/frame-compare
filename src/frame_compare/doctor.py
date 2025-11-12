"""Standalone doctor workflow helpers reused by the CLI and shims."""

from __future__ import annotations

import importlib.util
import json
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal, TypedDict, cast

import click

from src.frame_compare.preflight import is_writable_path

DoctorStatus = Literal["pass", "fail", "warn"]


class DoctorCheck(TypedDict):
    """Structured result for dependency doctor checks."""

    id: str
    label: str
    status: DoctorStatus
    message: str


_DOCTOR_STATUS_ICONS: Final[dict[DoctorStatus, str]] = {
    "pass": "✅",
    "fail": "❌",
    "warn": "⚠️",
}


def _get_config_value(mapping: Mapping[str, Any], path: Sequence[str], default: Any = None) -> Any:
    """Return a nested configuration value from *mapping* using ``path`` segments."""

    sentinel = object()
    current_value: Any = mapping
    for segment in path:
        if not isinstance(current_value, Mapping):
            return default
        current_mapping = cast(Mapping[str, Any], current_value)
        next_value = current_mapping.get(segment, sentinel)
        if next_value is sentinel:
            return default
        current_value = next_value
    return current_value


def collect_checks(
    root: Path,
    config_path: Path,
    config_mapping: Mapping[str, Any],
    *,
    root_issue: str | None = None,
    config_issue: str | None = None,
) -> tuple[list[DoctorCheck], list[str]]:
    """Generate doctor check results and auxiliary notes."""

    notes: list[str] = []
    if root_issue:
        notes.append(root_issue)
    if config_issue:
        notes.append(config_issue)

    use_ffmpeg = bool(_get_config_value(config_mapping, ("screenshots", "use_ffmpeg"), False))
    audio_enabled = bool(_get_config_value(config_mapping, ("audio_alignment", "enable"), False))
    vspreview_enabled = bool(_get_config_value(config_mapping, ("audio_alignment", "use_vspreview"), False))
    auto_upload = bool(_get_config_value(config_mapping, ("slowpics", "auto_upload"), False))

    vapoursynth_spec = importlib.util.find_spec("vapoursynth")
    vapoursynth_available = vapoursynth_spec is not None

    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")

    checks: list[DoctorCheck] = []

    config_writable = is_writable_path(config_path, for_file=True)
    config_label = "Config path writable"
    if root_issue:
        config_status: DoctorStatus = "fail"
        config_message = root_issue
    elif config_issue:
        config_status = "warn"
        config_message = config_issue
    elif config_writable:
        config_status = "pass"
        config_message = f"{config_path} is writable."
    else:
        config_status = "fail"
        config_message = (
            f"{config_path} is not writable. Choose another --root/--config or adjust permissions."
        )
    checks.append({
        "id": "config",
        "label": config_label,
        "status": config_status,
        "message": config_message,
    })

    if vapoursynth_available:
        vap_message = "VapourSynth module available."
        vap_status: DoctorStatus = "pass"
    else:
        if use_ffmpeg:
            vap_status = "warn"
            vap_message = "VapourSynth not found; screenshots are configured for FFmpeg fallback."
        else:
            vap_status = "fail"
            vap_message = "VapourSynth not found. Install VapourSynth or set [screenshots].use_ffmpeg=true."
    checks.append({
        "id": "vapoursynth",
        "label": "VapourSynth import",
        "status": vap_status,
        "message": vap_message,
    })

    ffmpeg_missing = [name for name, present in (("ffmpeg", ffmpeg_path), ("ffprobe", ffprobe_path)) if not present]
    if not ffmpeg_missing:
        ffmpeg_status: DoctorStatus = "pass"
        ffmpeg_message = "ffmpeg/ffprobe available."
    else:
        if use_ffmpeg:
            ffmpeg_status = "fail"
        elif vapoursynth_available:
            ffmpeg_status = "warn"
        else:
            ffmpeg_status = "fail"
        missing_str = ", ".join(ffmpeg_missing)
        ffmpeg_message = (
            f"Missing {missing_str}. Install FFmpeg or adjust renderer settings."
        )
    checks.append({
        "id": "ffmpeg",
        "label": "FFmpeg binaries",
        "status": ffmpeg_status,
        "message": ffmpeg_message,
    })

    audio_modules = {"librosa": importlib.util.find_spec("librosa"), "soundfile": importlib.util.find_spec("soundfile")}
    missing_audio = [name for name, spec in audio_modules.items() if spec is None]
    if not missing_audio:
        audio_status: DoctorStatus = "pass"
        audio_message = "Optional audio dependencies available."
    else:
        install_hint = "Install with 'uv pip install frame-compare[audio]'."
        if audio_enabled:
            audio_status = "fail"
            audio_message = f"Missing {', '.join(missing_audio)}. {install_hint}"
        else:
            audio_status = "warn"
            audio_message = f"Missing {', '.join(missing_audio)} (audio alignment disabled). {install_hint}"
    checks.append({
        "id": "audio",
        "label": "Audio alignment deps",
        "status": audio_status,
        "message": audio_message,
    })

    vspreview_detected = bool(shutil.which("vspreview") or importlib.util.find_spec("vspreview"))
    pyside_available = importlib.util.find_spec("PySide6") is not None
    if vspreview_detected and pyside_available:
        vs_status: DoctorStatus = "pass"
        vs_message = "VSPreview tooling available."
    else:
        if vspreview_enabled:
            vs_status = "fail"
            vs_message = "VSPreview extras missing. Install the 'preview' extras group."
        else:
            vs_status = "warn"
            vs_message = "VSPreview extras not detected (feature disabled)."
    checks.append({
        "id": "vspreview",
        "label": "VSPreview extras",
        "status": vs_status,
        "message": vs_message,
    })

    if auto_upload:
        slowpics_status: DoctorStatus = "warn"
        slowpics_message = (
            "[slowpics].auto_upload is enabled. Allow network access to https://slow.pics/ or disable auto_upload."
        )
    else:
        slowpics_status = "pass"
        slowpics_message = "Slow.pics auto-upload disabled."
    checks.append({
        "id": "slowpics",
        "label": "slow.pics network",
        "status": slowpics_status,
        "message": slowpics_message,
    })

    pyperclip_spec = importlib.util.find_spec("pyperclip")
    if auto_upload and pyperclip_spec is None:
        clip_status: DoctorStatus = "warn"
        clip_message = "Clipboard helper missing. Install 'pyperclip' or ignore to skip clipboard copying."
    else:
        clip_status = "pass"
        if auto_upload:
            clip_message = "pyperclip available for clipboard copy."
        else:
            clip_message = "Clipboard helper optional when slow.pics auto-upload is disabled."
    checks.append({
        "id": "pyperclip",
        "label": "Clipboard helper",
        "status": clip_status,
        "message": clip_message,
    })

    return checks, notes


def emit_results(
    checks: Sequence[DoctorCheck],
    notes: Sequence[str],
    *,
    json_mode: bool,
    workspace_root: Path,
    config_path: Path,
) -> None:
    """Render doctor results either as text table or JSON payload."""

    if json_mode:
        payload = {
            "workspace_root": str(workspace_root),
            "config_path": str(config_path),
            "checks": list(checks),
            "notes": list(notes),
        }
        click.echo(json.dumps(payload, indent=2))
        return

    if checks:
        width = max(len(check["label"]) for check in checks)
    else:
        width = 0
    for check in checks:
        icon = _DOCTOR_STATUS_ICONS.get(check["status"], "•")
        label = check["label"].ljust(width)
        click.echo(f"{icon} {label} — {check['message']}")
    if notes:
        click.echo("Notes:")
        for note in notes:
            click.echo(f"  - {note}")


__all__ = ["DoctorCheck", "DoctorStatus", "collect_checks", "emit_results"]
