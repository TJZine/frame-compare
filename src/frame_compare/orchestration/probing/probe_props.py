"""Probe prop key selection and preservation helpers.

Pure, deterministic functions for selecting tonemap-related prop keys
and extracting TOML-safe preserved props from VapourSynth frame-props mappings.
"""

from collections.abc import Mapping

# Exact base names that trigger inclusion (normalized)
_TONEMAP_EXACT_KEYS: frozenset[str] = frozenset(
    {
        "matrix",
        "primaries",
        "transfer",
        "range",
        "colorrange",
        "masteringdisplayprimaries",
        "masteringdisplayluminance",
        "contentlightlevelmax",
        "contentlightlevelaverage",
    }
)

# Prefixes that trigger inclusion (normalized)
_TONEMAP_PREFIXES: tuple[str, ...] = (
    "masteringdisplay",
    "contentlightlevel",
    "dolbyvision",
)


def normalize_probe_prop_key(key: str) -> str:
    """Normalize a VapourSynth prop key for matching.

    Rules:
        - Strip all leading underscores.
        - Lower-case.

    Examples:
        "_Transfer" -> "transfer"
        "__Matrix" -> "matrix"
        "DolbyVision_L6_MaxCLL" -> "dolbyvision_l6_maxcll"

    Args:
        key: The original prop key.

    Returns:
        Normalized key for matching purposes.
    """
    return key.lstrip("_").lower()


def compute_tonemap_prop_keys(frame_props: Mapping[str, object]) -> tuple[str, ...]:
    """Return a deterministic, ordered tuple of tonemap-related original prop keys.

    Selection (include key if any match):
        - normalized key equals one of:
          {"matrix","primaries","transfer","range","colorrange",
           "masteringdisplayprimaries","masteringdisplayluminance",
           "contentlightlevelmax","contentlightlevelaverage"}
        - normalized key starts with one of:
          {"masteringdisplay","contentlightlevel","dolbyvision"}

    Ordering (deterministic):
        - Sort selected keys by (normalize_probe_prop_key(key), key) and return as a tuple.

    Args:
        frame_props: Mapping of VapourSynth frame property names to values.

    Returns:
        Ordered tuple of original prop keys that are tonemap-related.
    """
    selected: list[str] = []

    for key in frame_props:
        normalized = normalize_probe_prop_key(key)

        # Check exact match
        if normalized in _TONEMAP_EXACT_KEYS:
            selected.append(key)
            continue

        # Check prefix match
        for prefix in _TONEMAP_PREFIXES:
            if normalized.startswith(prefix):
                selected.append(key)
                break

    # Sort by (normalized, original) for deterministic ordering
    selected.sort(key=lambda k: (normalize_probe_prop_key(k), k))
    return tuple(selected)


def compute_preserved_frame_props(
    frame_props: Mapping[str, object],
) -> dict[str, str | int | float]:
    """Return TOML-safe, tonemap-relevant props extracted from a frame-props mapping.

    Selection:
        - Start from compute_tonemap_prop_keys(frame_props).
        - Include only values that are TOML-safe primitives (str|int|float), except:
          - If any key normalizes to "dolbyvisionrpu", persist that key with value 1
            (presence indicator; do not persist the blob/bytes).

    Output determinism:
        - Return a dict populated in sorted key order (lexicographic by original key).

    Args:
        frame_props: Mapping of VapourSynth frame property names to values.

    Returns:
        Dict of preserved props with TOML-safe values, in sorted key order.
    """
    selected_keys = compute_tonemap_prop_keys(frame_props)
    result: dict[str, str | int | float] = {}

    # Sort keys lexicographically by original key for insertion order
    for key in sorted(selected_keys):
        value = frame_props[key]
        normalized = normalize_probe_prop_key(key)

        # Special handling for DolbyVisionRPU: persist as presence indicator (1)
        if normalized == "dolbyvisionrpu":
            result[key] = 1
            continue

        # Only include TOML-safe primitives (str, int, float)
        if isinstance(value, str | int | float) and not isinstance(value, bool):
            result[key] = value

    return result
