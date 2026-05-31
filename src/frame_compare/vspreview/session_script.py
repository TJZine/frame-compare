"""VSPreview session script generation and workspace bootstrapping.

This module is responsible for construction of the VapourSynth session script
used for interactive alignment verification, including workspace root detection
and path bootstrapping.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from frame_compare.utils.atomic_write import write_text_atomic


def write_vspreview_session_script(
    reference: Path,
    comparisons: list[Path],
    suggested_offsets_by_key: dict[str, int],
    cache_dir: Path,
) -> Path:
    """Generate and write a self-contained VSPreview script.

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

    script_content = _build_script_content(
        reference=reference,
        comparisons=comparisons,
        suggested_offsets_by_key=suggested_offsets_by_key,
        bootstrap_paths=bootstrap_paths,
    )

    base_timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    script_path = None
    for attempt in range(100):
        suffix = f"_{attempt}" if attempt > 0 else ""
        script_name = f"vspreview_{reference.stem}_{base_timestamp}{suffix}.py"
        candidate_path = sessions_dir / script_name
        if _reserve_empty_file(candidate_path):
            script_path = candidate_path
            break

    if script_path is None:
        random_suffix = uuid.uuid4().hex[:8]
        script_name = f"vspreview_{reference.stem}_{base_timestamp}_{random_suffix}.py"
        script_path = sessions_dir / script_name
        script_path.touch(exist_ok=False)

    write_text_atomic(script_path, script_content, encoding="utf-8")
    return script_path


def _reserve_empty_file(path: Path) -> bool:
    """Atomically reserve a path by exclusively creating an empty file."""
    try:
        path.touch(exist_ok=False)
    except FileExistsError:
        reserved = False
    else:
        reserved = True
    return reserved


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
    return '''\
#!/usr/bin/env python3
"""VSPreview alignment verification session.

Sign convention:
    + trims reference (comparison starts AFTER reference)
    - trims comparison (comparison starts BEFORE reference)

Audio-derived offsets shown here are hints only. This session displays
untrimmed source clips so the operator can inspect source-frame positions.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
'''


def _build_bootstrap_section(bootstrap_paths: list[Path]) -> str:
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
    return '''\
# ─── Safe Print Helper ────────────────────────────────────────────────────────
def _reconfigure_text_stream(stream):
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return False

    failure_reason = None
    try:
        reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, LookupError, OSError, TypeError, UnicodeError, ValueError) as error:
        failure_reason = f"{type(error).__name__}: {error}"
    else:
        return True
    return failure_reason is None


_reconfigure_text_stream(sys.stdout)
_reconfigure_text_stream(sys.stderr)


def _ansi_enabled():
    return "NO_COLOR" not in os.environ and getattr(sys.stdout, "isatty", lambda: False)()


def _style(text, code):
    if not _ansi_enabled():
        return text
    return f"\\033[{code}m{text}\\033[0m"


def _header(text):
    return _style(text, "1;36")


def _key(text):
    return _style(text, "34")


def _value(text):
    return _style(text, "97")


def _hint(text):
    return _style(text, "33")


def _warning(text):
    return _style(text, "33")


def _error(text):
    return _style(text, "31")


def safe_print(*args, **kwargs):
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
    targets_lines: list[str] = []
    for comp in sorted(comparisons, key=lambda p: p.stem):
        targets_lines.append(f"    {json.dumps(comp.stem)}: {json.dumps(str(comp))},")

    offset_lines: list[str] = []
    for key in sorted(suggested_offsets_by_key.keys()):
        offset = suggested_offsets_by_key[key]
        offset_lines.append(f"    {json.dumps(key)}: {int(offset)},")

    targets_content = "\n".join(targets_lines)
    offset_content = "\n".join(offset_lines)

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
"""


def _build_main_execution_section() -> str:
    return """\
# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    try:
        import vapoursynth as vs
    except ImportError:
        safe_print(_error("ERROR: VapourSynth not found. Install VapourSynth first."))
        sys.exit(1)

    core = vs.core
    try:
        load_source = resolve_lwlibavsource(core)
    except RuntimeError as e:
        safe_print(_error(f"ERROR: Failed to resolve LWLibavSource loader: {e}"))
        sys.exit(1)

    ref_path = Path(REFERENCE["path"])
    if not ref_path.exists():
        safe_print(_error(f"ERROR: Reference not found: {ref_path}"))
        sys.exit(1)

    try:
        ref_clip = load_source(str(ref_path))
    except Exception as e:
        safe_print(_error(f"ERROR: Failed to load reference: {e}"))
        sys.exit(1)

    ref_fps_num = ref_clip.fps.numerator
    ref_fps_den = ref_clip.fps.denominator

    safe_print("")
    safe_print(_header("VSPreview Bootstrap"))
    reference_fps = f"{ref_fps_num}/{ref_fps_den} fps"
    safe_print(
        f"  {_key('reference')}  {_value(REFERENCE['label'])} @ {_hint(reference_fps)}"
    )

    # Apply overlay to reference (best-effort)
    try:
        ref_clip = core.text.Text(
            ref_clip,
            f"REF: {REFERENCE['label']}",
            alignment=7,
        )
    except Exception:
        safe_print(_warning("Warning: Could not apply reference text overlay (plugin missing?)"))

    loaded_comparisons = []

    for label, path_str in sorted(TARGETS.items()):
        comp_path = Path(path_str)
        if not comp_path.exists():
            safe_print(_warning(f"WARNING: Comparison not found: {comp_path}"))
            continue

        try:
            comp_clip = load_source(str(comp_path))
        except Exception as e:
            safe_print(_warning(f"WARNING: Failed to load {label}: {e}"))
            continue

        # FPS harmonization: apply AssumeFPS to match reference
        comp_clip = core.std.AssumeFPS(comp_clip, fpsnum=ref_fps_num, fpsden=ref_fps_den)

        key = f"{REFERENCE['label']}:{label}"
        suggested_offset = int(suggested_offsets_by_key.get(key, 0))
        if suggested_offset >= 0:
            hint_pair = f"hint pair: ref frame {suggested_offset} ~= comparison frame 0"
        else:
            hint_pair = f"hint pair: ref frame 0 ~= comparison frame {-suggested_offset}"

        # Apply overlay with the audio-derived hint only (best-effort)
        try:
            overlay_text = (
                f"CMP: {label}\\n"
                f"Audio hint: {suggested_offset} frames\\n"
                f"{hint_pair}"
            )
            if suggested_offset > 0:
                overlay_text += "\\n(+N would trim reference after confirmation)"
            elif suggested_offset < 0:
                overlay_text += "\\n(-N would trim comparison after confirmation)"
            comp_clip = core.text.Text(comp_clip, overlay_text, alignment=7)
        except Exception:
            safe_print(_warning("Warning: Could not apply comparison text overlay (plugin missing?)"))

        loaded_comparisons.append(
            {
                "label": label,
                "clip": comp_clip,
                "suggested_offset": suggested_offset,
            }
        )

        safe_print(
            f"  {_key('loaded')}     {_value(label)} "
            f"{_hint(f'(audio hint: {suggested_offset})')}"
        )

    if not loaded_comparisons:
        safe_print(_error("ERROR: No comparison clips loaded successfully."))
        sys.exit(1)

    clips = []
    labels = []
    for entry in loaded_comparisons:
        clips.append(ref_clip)  # Even slot (untrimmed reference)
        labels.append(f"{REFERENCE['label']} (ref)")
        clips.append(entry["clip"])  # Odd slot (untrimmed comparison)
        labels.append(f"{entry['label']} (audio hint: {entry['suggested_offset']})")

    for i, (clip, label) in enumerate(zip(clips, labels)):
        clip.set_output(i)
        safe_print(f"  {_key(f'output {i:<2}')}  {_value(label)}")

    safe_print("\\n" + _header("VSPreview Ready"))
    safe_print(
        f"  {_key('inspect')}   inspect untrimmed source clips, "
        "then confirm source frames in the terminal"
    )

main()
"""


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
