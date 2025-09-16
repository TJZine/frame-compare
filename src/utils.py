from __future__ import annotations
import re
from typing import Dict, Optional
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
        def parse(self, s): return {}
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

def parse_filename_metadata(file_name: str, prefer_guessit: bool = True) -> Dict[str, str]:
    """GuessIt-first, Anitopy-fallback parser used for labels/slow.pics names."""
    if prefer_guessit and GUESSIT_AVAILABLE and _guessit is not None:
        try:
            g = _guessit(file_name)
            return {
                'anime_title': g.get('title') or "",
                'episode_number': _normalize_episode_number(g.get('episode')),
                'episode_title': g.get('episode_title') or "",
                'release_group': g.get('release_group') or _extract_release_group_brackets(file_name),
                'file_name': file_name,
            }
        except Exception:
            pass
    a = ani.parse(file_name) or {}
    return {
        'anime_title': a.get('anime_title') or a.get('title') or "",
        'episode_number': _normalize_episode_number(a.get('episode_number')),
        'episode_title': a.get('episode_title') or "",
        'release_group': a.get('release_group') or _extract_release_group_brackets(file_name),
        'file_name': file_name,
    }
