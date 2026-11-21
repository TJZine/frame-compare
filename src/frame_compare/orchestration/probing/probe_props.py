from collections.abc import Mapping

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

_TONEMAP_PREFIXES: tuple[str, ...] = (
    "masteringdisplay",
    "contentlightlevel",
    "dolbyvision",
)


def normalize_probe_prop_key(key: str) -> str:
    return key.lstrip("_").lower()


def compute_tonemap_prop_keys(frame_props: Mapping[str, object]) -> tuple[str, ...]:
    selected: list[str] = []

    for key in frame_props:
        normalized = normalize_probe_prop_key(key)

        if normalized in _TONEMAP_EXACT_KEYS:
            selected.append(key)
            continue

        for prefix in _TONEMAP_PREFIXES:
            if normalized.startswith(prefix):
                selected.append(key)
                break

    selected.sort(key=lambda k: (normalize_probe_prop_key(k), k))
    return tuple(selected)


def compute_preserved_frame_props(
    frame_props: Mapping[str, object],
) -> dict[str, str | int | float]:
    selected_keys = compute_tonemap_prop_keys(frame_props)
    result: dict[str, str | int | float] = {}

    for key in sorted(selected_keys):
        value = frame_props[key]
        normalized = normalize_probe_prop_key(key)

        if normalized == "dolbyvisionrpu":
            result[key] = 1
            continue

        if isinstance(value, str | int | float) and not isinstance(value, bool):
            result[key] = value

    return result
