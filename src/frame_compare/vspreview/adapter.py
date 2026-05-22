"""VSPreview availability detection and session script generation/launch wrapper.

This module provides the adapter between Frame Compare and the optional
VSPreview application for interactive alignment verification.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from frame_compare.errors import VSPreviewError, VSPreviewNotFoundError
from frame_compare.utils.atomic_write import write_text_atomic

if TYPE_CHECKING:
    pass

log = structlog.get_logger()


@dataclass(frozen=True)
class VSPreviewConfig:
    """Configuration for VSPreview integration.

    Attributes:
        enabled: Whether to launch VSPreview for verification
        timeout_seconds: Max time to wait for user input
        auto_close: Close VSPreview after user confirms
    """

    enabled: bool = False
    timeout_seconds: float = 300.0  # 5 minutes
    auto_close: bool = True


def is_vspreview_available() -> bool:
    """Check if VSPreview is installed and can be launched.

    Returns:
        True if vspreview is importable and functional

    Availability rules per vspreview spec §3.1 / §6.3:
        - Return True if `shutil.which("vspreview")` is non-None, OR
        - `importlib.util.find_spec("vspreview")` is non-None AND
          (`find_spec("PySide6")` OR `find_spec("PyQt5")`) is non-None.

    Note:
        Does not require a running X server/display.
        Full launch capability is checked separately.
    """
    # Priority 1: Check if vspreview executable exists in PATH
    if shutil.which("vspreview") is not None:
        return True

    # Priority 2: Check if vspreview module is importable + Qt backend
    vspreview_spec = importlib.util.find_spec("vspreview")
    if vspreview_spec is None:
        return False

    # Need at least one Qt backend
    pyside6_spec = importlib.util.find_spec("PySide6")
    pyqt5_spec = importlib.util.find_spec("PyQt5")

    return pyside6_spec is not None or pyqt5_spec is not None


def launch_alignment_verification_session(
    reference: Path,
    comparisons: list[Path],
    suggested_offsets_by_key: dict[str, int],
    cache_dir: Path,
    config: VSPreviewConfig,
) -> Path:
    """Launch a single VSPreview session for the full comparison set.

    Behavior:
    1. Generate a self-contained Python script that loads the reference clip
       and all comparisons.
    2. Apply FPS harmonization so that all clips scrub at the reference FPS.
    3. Overlay labels + suggested offsets per clip.
    4. Launch VSPreview via `vspreview {script}` or
       `{sys.executable} -m vspreview {script}`.
    5. Return the on-disk script path for debugging/replay.
    6. If `config.enabled` is False, generate and persist the script but do NOT
       launch VSPreview and do NOT raise any errors.

    Args:
        reference: Path to reference video
        comparisons: Paths to comparison videos
        suggested_offsets_by_key: Signed relative offsets keyed by
            "{ref_stem}:{comp_stem}"
        cache_dir: Directory used for generated artifacts
        config: VSPreview configuration

    Returns:
        Path to the generated script on disk

    Raises:
        VSPreviewNotFoundError: If vspreview is not available when config.enabled
            is True and launch is attempted
        VSPreviewError: If launch fails after vspreview is available
    """
    # Generate the script
    script_path = _generate_vspreview_script(
        reference=reference,
        comparisons=comparisons,
        suggested_offsets_by_key=suggested_offsets_by_key,
        cache_dir=cache_dir,
    )

    # If not enabled, just return the script path without launching
    if not config.enabled:
        log.info(
            "vspreview_script_generated",
            script_path=str(script_path),
            enabled=False,
        )
        return script_path

    # TTY gating: VSPreview is interactive; avoid launching in non-interactive contexts.
    stdin_tty = sys.stdin.isatty()
    stdout_tty = sys.stdout.isatty()
    stderr_tty = sys.stderr.isatty()
    if not (stdin_tty or stdout_tty or stderr_tty):
        log.warning(
            "vspreview_no_tty",
            hint="Cannot launch VSPreview without an interactive terminal (TTY)",
            script_path=str(script_path),
            stdin_tty=stdin_tty,
            stdout_tty=stdout_tty,
            stderr_tty=stderr_tty,
        )
        return script_path

    # Check availability
    if not is_vspreview_available():
        raise VSPreviewNotFoundError()

    # Resolve the launch command
    command = _resolve_launch_command(script_path)

    # Print telemetry per vspreview spec §3.2.3
    print(f"VSPreview script: {script_path}")
    print(f"Launch command: {' '.join(command)}")

    # Launch VSPreview
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=config.timeout_seconds,
        )

        if result.returncode != 0:
            # Emit warning telemetry before surfacing a launch failure.
            log.warning(
                "vspreview_non_zero_exit",
                returncode=result.returncode,
                stderr=result.stderr[:500] if result.stderr else None,
                stdout=result.stdout[:500] if result.stdout else None,
                hint="Re-run with verbose mode to capture full output",
            )
            raise VSPreviewError(
                f"VSPreview exited with code {result.returncode}: "
                f"{result.stderr[:200] if result.stderr else 'no stderr'}"
            )

    except subprocess.TimeoutExpired as e:
        raise VSPreviewError(f"VSPreview timed out after {config.timeout_seconds}s") from e
    except FileNotFoundError as e:
        raise VSPreviewError(f"Failed to launch VSPreview: {e}") from e
    except Exception as e:
        if isinstance(e, (VSPreviewError, VSPreviewNotFoundError)):
            raise
        raise VSPreviewError(f"Unexpected error launching VSPreview: {e}") from e

    return script_path


def _resolve_launch_command(script_path: Path) -> list[str]:
    """Resolve the launch command for VSPreview.

    Priority per vspreview spec §6.3:
    1. If `vspreview` executable exists in PATH: `vspreview {script_path}`
    2. Else: `{sys.executable} -m vspreview {script_path}`
    """
    vspreview_path = shutil.which("vspreview")
    if vspreview_path is not None:
        return [vspreview_path, str(script_path)]
    return [sys.executable, "-m", "vspreview", str(script_path)]


def _generate_vspreview_script(
    reference: Path,
    comparisons: list[Path],
    suggested_offsets_by_key: dict[str, int],
    cache_dir: Path,
) -> Path:
    """Generate a self-contained VSPreview script.

    Output location:
        - Directory: `{cache_dir}/vspreview_sessions/` (created if missing)
        - Filename: `vspreview_{reference_stem}_{timestamp}.py` (UTC timestamp)
        - Timestamp format: YYYYMMDDTHHMMSSZ (UTC, seconds precision)

    The timestamp MUST appear in the filename only; it MUST NOT appear in the
    script body so that script content remains byte-identical for the same inputs.
    """
    sessions_dir = cache_dir / "vspreview_sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    bootstrap_paths = _resolve_bootstrap_paths(cache_dir)

    # Build script content
    script_content = _build_script_content(
        reference=reference,
        comparisons=comparisons,
        suggested_offsets_by_key=suggested_offsets_by_key,
        bootstrap_paths=bootstrap_paths,
    )

    # Generate UTC timestamp for filename only
    base_timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    script_path = None
    for attempt in range(100):
        suffix = f"_{attempt}" if attempt > 0 else ""
        script_name = f"vspreview_{reference.stem}_{base_timestamp}{suffix}.py"
        candidate_path = sessions_dir / script_name
        try:
            # Atomically reserve path by exclusively creating it
            with open(candidate_path, "x", encoding="utf-8"):
                pass
            script_path = candidate_path
            break
        except FileExistsError:
            continue

    if script_path is None:
        import uuid

        random_suffix = uuid.uuid4().hex[:8]
        script_name = f"vspreview_{reference.stem}_{base_timestamp}_{random_suffix}.py"
        script_path = sessions_dir / script_name
        with open(script_path, "x", encoding="utf-8"):
            pass

    write_text_atomic(script_path, script_content, encoding="utf-8")
    return script_path


def _resolve_bootstrap_paths(cache_dir: Path) -> list[Path]:
    """Resolve stable bootstrap import roots for generated VSPreview scripts."""
    resolved_cache_dir = cache_dir.resolve()
    workspace_root = _find_workspace_root(resolved_cache_dir)
    project_root = _find_project_root(resolved_cache_dir, workspace_root)

    bootstrap_paths: list[Path] = []
    for candidate in (project_root, project_root / "src", workspace_root):
        if candidate not in bootstrap_paths:
            bootstrap_paths.append(candidate)
    return bootstrap_paths


def _find_workspace_root(cache_dir: Path) -> Path:
    """Find the nearest ancestor that looks like a Frame Compare workspace root."""
    for candidate in (cache_dir, *cache_dir.parents):
        if (candidate / "config").is_dir():
            return candidate

    if cache_dir.name == "cache" and cache_dir.parent.name == "generated":
        return cache_dir.parent.parent
    return cache_dir.parent


def _find_project_root(cache_dir: Path, workspace_root: Path) -> Path:
    """Find the nearest ancestor that can import the local frame_compare package."""
    for candidate in (cache_dir, *cache_dir.parents):
        if (candidate / "src" / "frame_compare").is_dir():
            return candidate
    return workspace_root


def _build_script_header() -> str:
    """Build the script header with docstring and imports."""
    return '''\
#!/usr/bin/env python3
"""VSPreview alignment verification session.

Sign convention:
    + trims comparison (comparison starts AFTER reference)
    - trims reference (comparison starts BEFORE reference)

Operator-confirmed offsets are SIGNED RELATIVE OFFSETS.
The pipeline will apply trim-first normalization (no padding).
"""
from __future__ import annotations

import sys
from pathlib import Path
'''


def _build_bootstrap_section(bootstrap_paths: list[Path]) -> str:
    """Build the sys.path bootstrap section of the script."""
    bootstrap_path_lines = ",\n".join(f"    {json.dumps(str(path))}" for path in bootstrap_paths)
    return f"""\
# ─── sys.path Bootstrap ───────────────────────────────────────────────────────
# Make imports work in "run from repo" mode without deriving roots from __file__
_BOOTSTRAP_PATHS = [
{bootstrap_path_lines}
]

for _raw_path in _BOOTSTRAP_PATHS:
    _p = Path(_raw_path)
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
"""


def _build_helpers_section() -> str:
    """Build the static printing and loader helper functions."""
    return '''\
# ─── Safe Print Helper ────────────────────────────────────────────────────────
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass  # Best-effort on Windows


def safe_print(*args, **kwargs):
    """Print with unicode safety."""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # Fallback for problematic consoles
        text = " ".join(str(a) for a in args)
        print(text.encode("ascii", errors="replace").decode("ascii"), **kwargs)


def resolve_lwlibavsource(core):
    """Resolve LWLibavSource using Frame Compare's lsmas-then-lw contract."""
    if hasattr(core, "lsmas") and hasattr(core.lsmas, "LWLibavSource"):
        return core.lsmas.LWLibavSource
    if hasattr(core, "lw") and hasattr(core.lw, "LWLibavSource"):
        return core.lw.LWLibavSource
    raise RuntimeError("LWLibavSource not found on core.lsmas or core.lw")
'''


def _build_clip_data_section(
    reference: Path,
    comparisons: list[Path],
    suggested_offsets_by_key: dict[str, int],
) -> str:
    """Build the dynamic clip data payload variables."""
    # Build targets dict with stable ordering (sorted by comparison path stem)
    targets_lines: list[str] = []
    for comp in sorted(comparisons, key=lambda p: p.stem):
        targets_lines.append(f"    {json.dumps(comp.stem)}: {json.dumps(str(comp))},")

    # Build suggested offsets with stable ordering
    offset_lines: list[str] = []
    for key in sorted(suggested_offsets_by_key.keys()):
        offset = suggested_offsets_by_key[key]
        offset_lines.append(f"    {json.dumps(key)}: {int(offset)},")

    # Build per-label offset map for operator convenience
    offset_map_lines: list[str] = []
    for comp in sorted(comparisons, key=lambda p: p.stem):
        key = f"{reference.stem}:{comp.stem}"
        offset = suggested_offsets_by_key.get(key, 0)
        offset_map_lines.append(f"    {json.dumps(comp.stem)}: {int(offset)},")

    targets_content = "\n".join(targets_lines)
    offset_content = "\n".join(offset_lines)
    offset_map_content = "\n".join(offset_map_lines)

    return f"""\
# ─── Clip Data ────────────────────────────────────────────────────────────────
REFERENCE = {{
    "label": {json.dumps(reference.stem)},
    "path": {json.dumps(str(reference))},
}}

TARGETS = {{
{targets_content}
}}

# Suggested offsets keyed by "{{ref_stem}}:{{comp_stem}}"
suggested_offsets_by_key = {{
{offset_content}
}}

# Per-label offset map (operator convenience, edit here to test manually)
OFFSET_MAP = {{
{offset_map_content}
}}
"""


def _build_main_execution_section() -> str:
    """Build the main execution loop template."""
    return '''\
# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    """Load clips into VSPreview with overlays and suggested offsets."""
    try:
        import vapoursynth as vs
    except ImportError:
        safe_print("ERROR: VapourSynth not found. Install VapourSynth first.")
        sys.exit(1)

    core = vs.core
    load_source = resolve_lwlibavsource(core)

    # Load reference clip
    ref_path = Path(REFERENCE["path"])
    if not ref_path.exists():
        safe_print(f"ERROR: Reference not found: {ref_path}")
        sys.exit(1)

    try:
        ref_clip = load_source(str(ref_path))
    except Exception as e:
        safe_print(f"ERROR: Failed to load reference: {e}")
        sys.exit(1)

    ref_fps_num = ref_clip.fps.numerator
    ref_fps_den = ref_clip.fps.denominator

    safe_print(f"Reference: {REFERENCE['label']} @ {ref_fps_num}/{ref_fps_den} fps")

    # Apply overlay to reference (best-effort)
    try:
        ref_clip = core.text.Text(
            ref_clip,
            f"REF: {REFERENCE['label']}",
            alignment=7,
        )
    except Exception:
        safe_print("Warning: Could not apply text overlay (plugin missing?)")

    clips = [ref_clip]
    labels = [REFERENCE["label"]]

    # Load comparison clips
    for label, path_str in sorted(TARGETS.items()):
        comp_path = Path(path_str)
        if not comp_path.exists():
            safe_print(f"WARNING: Comparison not found: {comp_path}")
            continue

        try:
            comp_clip = load_source(str(comp_path))
        except Exception as e:
            safe_print(f"WARNING: Failed to load {label}: {e}")
            continue

        # FPS harmonization: apply AssumeFPS to match reference
        comp_clip = core.std.AssumeFPS(comp_clip, fpsnum=ref_fps_num, fpsden=ref_fps_den)

        # Get suggested offset
        key = f"{REFERENCE['label']}:{label}"
        offset = suggested_offsets_by_key.get(key, OFFSET_MAP.get(label, 0))

        # Apply overlay with suggested offset (best-effort)
        try:
            overlay_text = f"CMP: {label}\\nSuggested offset: {offset} frames"
            if offset > 0:
                overlay_text += "\\n(+N = comparison starts AFTER reference)"
            elif offset < 0:
                overlay_text += "\\n(-N = comparison starts BEFORE reference)"
            comp_clip = core.text.Text(comp_clip, overlay_text, alignment=7)
        except Exception:
            safe_print("Warning: Could not apply text overlay (plugin missing?)")

        # Slot layout: ref on even, comparison on odd
        # We duplicate reference before each comparison
        clips.append(ref_clip)  # Even slot (duplicate ref)
        labels.append(f"{REFERENCE['label']} (ref)")
        clips.append(comp_clip)  # Odd slot (comparison)
        labels.append(label)

        safe_print(f"Loaded: {label} (offset: {offset})")

    if len(clips) < 2:
        safe_print("ERROR: No comparison clips loaded successfully.")
        sys.exit(1)

    # Output clips for VSPreview
    for i, (clip, label) in enumerate(zip(clips, labels)):
        clip.set_output(i)
        safe_print(f"Output {i}: {label}")

    safe_print("\\nReady for VSPreview. Adjust offsets visually, then confirm in terminal.")


if __name__ == "__main__":
    main()
'''


def _build_script_content(
    reference: Path,
    comparisons: list[Path],
    suggested_offsets_by_key: dict[str, int],
    bootstrap_paths: list[Path],
) -> str:
    """Build the script content for VSPreview.

    This content is deterministic for the same inputs (no timestamp in body).
    """
    header = _build_script_header()
    bootstrap = _build_bootstrap_section(bootstrap_paths)
    helpers = _build_helpers_section()
    clip_data = _build_clip_data_section(reference, comparisons, suggested_offsets_by_key)
    main_execution = _build_main_execution_section()

    return f"{header}\n\n{bootstrap}\n\n{helpers}\n\n\n{clip_data}\n\n{main_execution}"
