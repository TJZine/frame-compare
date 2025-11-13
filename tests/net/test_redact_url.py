from __future__ import annotations

import pytest

from src.frame_compare import net


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://[::1", "url"),
        ("https://example.com/path?token=abc", "example.com"),
        ("https://example.com", "example.com"),
        ("/status/health", "/status/health"),
    ],
)
def test_redact_url_for_logs(url: str, expected: str) -> None:
    assert net.redact_url_for_logs(url) == expected
