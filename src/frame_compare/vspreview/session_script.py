"""VSPreview session script generation and workspace bootstrapping.

This module is responsible for construction of the VapourSynth session script
used for interactive alignment verification, including workspace root detection
and path bootstrapping.
"""

from __future__ import annotations

import json
import math
import uuid
from datetime import UTC, datetime
from pathlib import Path

from frame_compare.utils.atomic_write import write_text_atomic
from frame_compare.vs.source import INDEX_CONSTRUCTION_FAILURE_MARKER, source_index_path


def write_vspreview_session_script(
    reference: Path,
    comparisons: list[Path],
    suggested_offsets_by_key: dict[str, int | None],
    cache_dir: Path,
    frame_props_by_stem: dict[str, dict[str, str | int | float]] | None = None,
    presentation_names_by_stem: dict[str, str] | None = None,
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
        frame_props_by_stem=frame_props_by_stem,
        presentation_names_by_stem=presentation_names_by_stem,
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
    marker = json.dumps(INDEX_CONSTRUCTION_FAILURE_MARKER)
    return (
        f"INDEX_CONSTRUCTION_FAILURE_MARKER = {marker}\n\n"
        + '''\
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
    return "NO_COLOR" not in os.environ and getattr(sys.stderr, "isatty", lambda: False)()


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


def _status(marker):
    codes = {"[RUN]": "96", "[OK]": "32", "[WARN]": "33", "[FAIL]": "31"}
    return _style(marker, codes[marker])


def _status_line(marker, text):
    return f"  {_status(marker)} {text}"


def safe_print(*args, **kwargs):
    kwargs.setdefault("file", sys.stderr)
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # Fallback for problematic consoles
        text = " ".join(str(a) for a in args)
        print(text.encode("ascii", errors="replace").decode("ascii"), **kwargs)


def resolve_lwlibavsource(core):
    """Resolve LWLibavSource from the VapourSynth R79 core.lsmas namespace."""
    if hasattr(core, "lsmas") and hasattr(core.lsmas, "LWLibavSource"):
        return core.lsmas
    raise RuntimeError("LWLibavSource not found on core.lsmas")


def load_preview_source(loader, path, index_path, display_name):
    try:
        return loader.LWLibavSource(str(path), cachefile=str(index_path))
    except Exception as original_error:
        if INDEX_CONSTRUCTION_FAILURE_MARKER not in str(original_error).casefold():
            raise

        safe_print(
            _status_line(
                "[WARN]",
                f"Retrying {display_name} without an L-SMASH index cache after index construction failed",
            )
        )
        try:
            return loader.LWLibavSource(str(path), cache=0)
        except Exception as fallback_error:
            raise original_error from fallback_error


FRAME_PROP_ALIASES = {
    "_Matrix": ("_Matrix", "Matrix"),
    "_Transfer": ("_Transfer", "Transfer"),
    "_Primaries": ("_Primaries", "Primaries"),
}
UNSPECIFIED_FRAME_PROP = 2


def _parse_frame_prop_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, bytes):
        try:
            value = value.decode("ascii")
        except UnicodeDecodeError:
            return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdecimal():
            return int(stripped)
    return None


def _join_prop_names(names):
    return "/".join(names)


def _read_prop(props, canonical_key):
    for key in FRAME_PROP_ALIASES[canonical_key]:
        if key in props:
            return props[key]
    raise KeyError(canonical_key)


def collect_preview_assumption(label, display_name):
    props = FRAME_PROPS_BY_LABEL.get(label)
    if props is None:
        return None

    missing = []
    unspecified = []
    unparseable = []
    for key in FRAME_PROP_ALIASES:
        try:
            raw_value = _read_prop(props, key)
        except KeyError:
            missing.append(key)
            continue
        except Exception:
            unparseable.append(key)
            continue

        parsed_value = _parse_frame_prop_int(raw_value)
        if parsed_value is None:
            unparseable.append(key)
        elif parsed_value == UNSPECIFIED_FRAME_PROP:
            unspecified.append(key)

    details = []
    if missing:
        details.append(f"missing {_join_prop_names(missing)}")
    if unspecified:
        details.append(f"unspecified {_join_prop_names(unspecified)}")
    if unparseable:
        details.append(f"unparseable {_join_prop_names(unparseable)}")
    if not details:
        return None

    return (
        f"{display_name} {'; '.join(details)}; "
        "using display-safe BT.709 defaults for preview only; "
        "render/report semantics unchanged"
    )


def apply_preview_defaults(core, clip, label):
    props = FRAME_PROPS_BY_LABEL.get(label)
    if props is None:
        return clip

    defaults = {}
    for key in FRAME_PROP_ALIASES:
        try:
            parsed_value = _parse_frame_prop_int(_read_prop(props, key))
        except Exception:
            parsed_value = None
        if parsed_value is None or parsed_value == UNSPECIFIED_FRAME_PROP:
            defaults[key] = 1
    if not defaults:
        return clip
    return core.std.SetFrameProps(clip, **defaults)
'''
    )


def _build_clip_data_section(
    reference: Path,
    comparisons: list[Path],
    suggested_offsets_by_key: dict[str, int | None],
    frame_props_by_stem: dict[str, dict[str, str | int | float]] | None,
    presentation_names_by_stem: dict[str, str] | None,
) -> str:
    presentation_names = presentation_names_by_stem or {}
    targets_lines: list[str] = []
    for comp in comparisons:
        targets_lines.append(
            f"    {json.dumps(comp.stem)}: {{"
            f'"path": {json.dumps(str(comp))}, '
            f'"index_path": {json.dumps(str(source_index_path(comp)))}, '
            f'"display_name": {json.dumps(presentation_names.get(comp.stem, comp.stem))}'
            "},"
        )

    offset_lines: list[str] = []
    for key in sorted(suggested_offsets_by_key.keys()):
        offset = suggested_offsets_by_key[key]
        offset_value = "None" if offset is None else str(int(offset))
        offset_lines.append(f"    {json.dumps(key)}: {offset_value},")

    targets_content = "\n".join(targets_lines)
    offset_content = "\n".join(offset_lines)
    frame_props_content = json.dumps(
        _preview_frame_props_for_script(frame_props_by_stem),
        sort_keys=True,
        indent=4,
        allow_nan=False,
    )

    return f"""\
# ─── Clip Data ────────────────────────────────────────────────────────────────
REFERENCE = {{
    "label": {json.dumps(reference.stem)},
    "path": {json.dumps(str(reference))},
    "index_path": {json.dumps(str(source_index_path(reference)))},
    "display_name": {json.dumps(presentation_names.get(reference.stem, reference.stem))},
}}

TARGETS = {{
{targets_content}
}}

# Suggested offsets keyed by "{{ref_stem}}:{{comp_stem}}"
suggested_offsets_by_key = {{
{offset_content}
}}

FRAME_PROPS_BY_LABEL = {frame_props_content}
"""


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


def _build_main_execution_section() -> str:
    return """\
# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    try:
        import vapoursynth as vs
    except ImportError:
        safe_print(_status_line("[FAIL]", "VapourSynth is unavailable"))
        sys.exit(1)
    core = vs.core
    try:
        load_source = resolve_lwlibavsource(core)
    except RuntimeError as e:
        safe_print(_status_line("[FAIL]", f"Failed to resolve LWLibavSource loader: {e}"))
        sys.exit(1)

    ref_path = Path(REFERENCE["path"])
    if not ref_path.exists():
        safe_print(_status_line("[FAIL]", f"Reference not found: {ref_path}"))
        sys.exit(1)

    safe_print("")
    safe_print(_status_line("[RUN]", "VSPreview Bootstrap"))
    safe_print(f"    {_key('reference')}     {_value(REFERENCE['display_name'])}")

    try:
        ref_clip = load_preview_source(
            load_source,
            ref_path,
            Path(REFERENCE["index_path"]),
            REFERENCE["display_name"],
        )
    except Exception as e:
        safe_print(_status_line("[FAIL]", f"Reference source could not be loaded: {e}"))
        sys.exit(1)

    ref_fps_num = ref_clip.fps.numerator
    ref_fps_den = ref_clip.fps.denominator
    preview_assumptions = []
    ref_assumption = collect_preview_assumption(
        REFERENCE["label"], REFERENCE["display_name"]
    )
    if ref_assumption is not None:
        preview_assumptions.append(ref_assumption)
    ref_clip = apply_preview_defaults(core, ref_clip, REFERENCE["label"])

    safe_print(f"    {_key('fps')}           {_hint(f'{ref_fps_num}/{ref_fps_den}')}")

    # Apply overlay to reference (best-effort)
    try:
        ref_clip = core.text.Text(
            ref_clip,
            f"REF: {REFERENCE['display_name']}",
            alignment=7,
        )
    except Exception:
        safe_print(_status_line("[WARN]", "Could not apply reference text overlay"))

    loaded_comparison_count = 0

    for comparison_number, (label, target) in enumerate(TARGETS.items(), start=1):
        comp_path = Path(target["path"])
        display_name = target["display_name"]
        safe_print("")
        safe_print(f"    {_key(f'comparison {comparison_number}')}  {_value(display_name)}")
        if not comp_path.exists():
            safe_print(_status_line("[WARN]", f"Comparison source not found: {comp_path}"))
            continue

        try:
            comp_clip = load_preview_source(
                load_source,
                comp_path,
                Path(target["index_path"]),
                display_name,
            )
        except Exception as e:
            safe_print(_status_line("[WARN]", f"Comparison source could not be loaded: {e}"))
            continue

        comp_assumption = collect_preview_assumption(label, display_name)
        if comp_assumption is not None:
            preview_assumptions.append(comp_assumption)

        # FPS harmonization: apply AssumeFPS to match reference
        comp_clip = core.std.AssumeFPS(comp_clip, fpsnum=ref_fps_num, fpsden=ref_fps_den)
        comp_clip = apply_preview_defaults(core, comp_clip, label)

        key = f"{REFERENCE['label']}:{label}"
        suggested_offset = suggested_offsets_by_key.get(key)
        if suggested_offset is None:
            audio_hint = "no trusted audio hint"
            hint_pair = "Suggested match: unavailable"
            trim_hint = "Find matching source frames manually"
        elif suggested_offset > 0:
            audio_hint = f"+{suggested_offset}f"
            hint_pair = f"Suggested match: REF {suggested_offset} <-> CMP 0"
            trim_hint = f"If confirmed: trim {suggested_offset}f from reference"
        elif suggested_offset < 0:
            audio_hint = f"{suggested_offset}f"
            comparison_frame = -suggested_offset
            hint_pair = f"Suggested match: REF 0 <-> CMP {comparison_frame}"
            trim_hint = f"If confirmed: trim {comparison_frame}f from comparison"
        else:
            audio_hint = "+0f"
            hint_pair = "Suggested match: REF 0 <-> CMP 0"
            trim_hint = "If confirmed: no trim"

        # Apply overlay with the audio-derived hint only (best-effort)
        try:
            overlay_text = (
                f"CMP: {display_name}\\n"
                f"Audio hint: {audio_hint}\\n"
                f"{hint_pair}\\n"
                f"{trim_hint}"
            )
            comp_clip = core.text.Text(comp_clip, overlay_text, alignment=7)
        except Exception:
            safe_print(_status_line("[WARN]", "Could not apply comparison text overlay"))

        safe_print(f"    {_key('audio hint')}    {_hint(audio_hint)}")
        reference_output = loaded_comparison_count * 2
        comparison_output = reference_output + 1
        ref_clip.set_output(reference_output)
        comp_clip.set_output(comparison_output)
        safe_print(
            f"    {_key('outputs')}       "
            f"Reference {reference_output} | Comparison {comparison_number} {comparison_output}"
        )
        loaded_comparison_count += 1

    if loaded_comparison_count == 0:
        safe_print(_status_line("[FAIL]", "No comparison clips loaded successfully"))
        sys.exit(1)

    if preview_assumptions:
        safe_print("\\n    " + _header("VSPreview Assumptions"))
        for assumption in preview_assumptions:
            safe_print(f"    {_key('preview')}   {_hint(assumption)}")

    safe_print("\\n" + _status_line("[OK]", "VSPreview Ready"))
    safe_print("    Inspect the untrimmed clips in VSPreview, then return here to confirm frames.")

main()
"""


def _build_script_content(
    reference: Path,
    comparisons: list[Path],
    suggested_offsets_by_key: dict[str, int | None],
    bootstrap_paths: list[Path],
    frame_props_by_stem: dict[str, dict[str, str | int | float]] | None = None,
    presentation_names_by_stem: dict[str, str] | None = None,
) -> str:
    """Build the script content for VSPreview.

    This content is deterministic for the same inputs (no timestamp in body).
    """
    header = _build_script_header()
    bootstrap = _build_bootstrap_section(bootstrap_paths)
    helpers = _build_helpers_section()
    clip_data = _build_clip_data_section(
        reference,
        comparisons,
        suggested_offsets_by_key,
        frame_props_by_stem,
        presentation_names_by_stem,
    )
    main_execution = _build_main_execution_section()

    return f"{header}\n\n{bootstrap}\n\n{helpers}\n\n\n{clip_data}\n\n{main_execution}"
