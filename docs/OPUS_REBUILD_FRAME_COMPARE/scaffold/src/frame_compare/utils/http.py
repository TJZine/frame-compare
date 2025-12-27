"""HTTP utilities with security policy enforcement."""

from __future__ import annotations

from urllib.parse import urlparse

from frame_compare.errors import HostNotAllowedError, HttpsRequiredError

# Allowlist of hosts permitted for external requests (SSRF prevention)
ALLOWED_HOSTS = frozenset({"slow.pics", "api.themoviedb.org"})


def validate_external_url(url: str) -> None:
    """Validate URL against security policy.

    Args:
        url: The URL to validate

    Raises:
        HttpsRequiredError: If URL is not HTTPS
        HostNotAllowedError: If host not in allowlist
    """
    parsed = urlparse(url)

    if parsed.scheme != "https":
        raise HttpsRequiredError(url)

    hostname = parsed.hostname
    if hostname is None or hostname not in ALLOWED_HOSTS:
        raise HostNotAllowedError(hostname or "unknown")
