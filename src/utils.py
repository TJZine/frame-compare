from __future__ import annotations
import re
from typing import Dict, Optional

from .datatypes import NamingConfig

try:
    from guessit import guessit as _guessit
    GUESSIT_AVAILABLE = True
except Exception:
    GUESSIT_AVAILABLE = False
    _guessit = None

try:
    import anitopy as ani
except Exception:  # fallback stub if anitopy not installed yet
    class _Stub:
        def parse(self, s):
            return {}
    ani = _Stub()

def _extract_release_group_brackets(file_name: str) -> Optional[str]:
    m = re.match(r"^\[(?P<grp>[^\]]+)\]", file_name)
    return m.group("grp") if m else None

def _normalize_episode_number(val) -> str:
    if val is None:
        return ""
    if isinstance(val, (list, tuple)):
        return "-".join(str(x) for x in val)
    return str(val)

def _build_common_metadata(file_name: str, title: str, episode_number, episode_title: str, release_group: Optional[str]) -> Dict[str, str]:
    return {
        "anime_title": title or "",
        "episode_number": _normalize_episode_number(episode_number),
        "episode_title": episode_title or "",
        "release_group": release_group or _extract_release_group_brackets(file_name) or "",
        "file_name": file_name,
    }

def parse_filename_metadata(
    file_name: str,
    naming: Optional[NamingConfig] = None,
    prefer_guessit: Optional[bool] = None,
) -> Dict[str, str]:
    """GuessIt-first filename parser with Anitopy fallback and naming controls."""

    prefer_guess = prefer_guessit
    if prefer_guess is None:
        prefer_guess = naming.prefer_guessit if naming else True

    data: Dict[str, str] | None = None

    if prefer_guess and GUESSIT_AVAILABLE and _guessit is not None:
        try:
            g = _guessit(file_name)
        except Exception:
            g = None
        if isinstance(g, dict):
            data = _build_common_metadata(
                file_name,
                title=g.get("title") or "",
                episode_number=g.get("episode"),
                episode_title=g.get("episode_title") or "",
                release_group=g.get("release_group"),
            )

    if data is None:
        try:
            parsed = ani.parse(file_name) or {}
        except Exception:
            parsed = {}
        data = _build_common_metadata(
            file_name,
            title=parsed.get("anime_title") or parsed.get("title") or "",
            episode_number=parsed.get("episode_number"),
            episode_title=parsed.get("episode_title") or "",
            release_group=parsed.get("release_group"),
        )

    always_full = naming.always_full_filename if naming else True
    display_name = data["file_name"] if always_full else data.get("release_group") or data["file_name"]
    data["display_name"] = display_name
    return data
