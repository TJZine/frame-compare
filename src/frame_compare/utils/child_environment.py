"""Frame Compare credentials that must stay in the owning process."""

from __future__ import annotations

import os
import re
import unicodedata
from collections.abc import Mapping

# Match explicit owners, including the release/migration aliases. Do not
# filter unrelated runtime settings (e.g. plugin paths and fingerprints).
_CREDENTIAL_NAMES = frozenset(
    {
        "FRAME_COMPARE_SLOWPICS__WEBHOOK_URL",
        "FRAME_COMPARE_TMDB__API_KEY",
        "SIGNING_KEY_XML_PATH",
        "WINDOWS_UPDATE_SIGNING_KEY_XML",
        "SOURCE_SIGNING_KEY",
        "SIGNING_KEY_MIGRATION_TOKEN",
    }
)
_SLOWPICS_CREDENTIAL = re.compile(
    r"FRAME_COMPARE_SLOWPICS__(?:API_KEY|TOKEN|API_TOKEN|PASSWORD|COOKIE|SECRET)\Z"
)


def _is_app_credential(name: str) -> bool:
    name = name.upper()
    return name in _CREDENTIAL_NAMES or _SLOWPICS_CREDENTIAL.fullmatch(name) is not None


def child_environment(environment: Mapping[str, str] | None = None) -> dict[str, str]:
    """Filter the complete effective environment after any caller overrides."""
    source = os.environ if environment is None else environment
    return {name: value for name, value in source.items() if not _is_app_credential(name)}


def diagnostic_secrets(environment: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """Snapshot app-owned secret values before launching a child."""
    values = {
        value
        for source in (os.environ, environment or {})
        for name, value in source.items()
        if value and _is_app_credential(name)
    }
    return tuple(sorted(values, key=lambda value: (-len(value), value)))


def sanitize_diagnostic(output: bytes, secrets: tuple[str, ...]) -> bytes:
    text = output.decode("utf-8", errors="replace")
    if secrets:
        pattern = "|".join(re.escape(value) for value in secrets)
        text = re.sub(pattern, "<redacted>", text)
    return "".join(
        char if char in "\n\t" or unicodedata.category(char) not in {"Cc", "Cf"} else " "
        for char in text
    ).encode("utf-8")
