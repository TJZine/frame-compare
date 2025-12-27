"""Security tests for upload policy enforcement.

Verifies that network requests enforce HTTPS and host allowlist.
"""

from __future__ import annotations

import pytest


@pytest.mark.tier_a
class TestUploadSecurityPolicy:
    """Tests for network security policy enforcement."""

    def test_https_required_error_on_http(self) -> None:
        """HTTP URLs must raise HttpsRequiredError."""
        from frame_compare.errors import HttpsRequiredError
        from frame_compare.utils.http import validate_external_url

        with pytest.raises(HttpsRequiredError) as exc:
            validate_external_url("http://slow.pics/api/comparison")

        assert exc.value.code == "FC-5010"
        assert "url" in (exc.value.context.details or {})

    def test_host_not_allowed_error_on_unknown_host(self) -> None:
        """Non-allowlisted hosts must raise HostNotAllowedError."""
        from frame_compare.errors import HostNotAllowedError
        from frame_compare.utils.http import validate_external_url

        with pytest.raises(HostNotAllowedError) as exc:
            validate_external_url("https://evil.example.com/api")

        assert exc.value.code == "FC-5011"
        assert "host" in (exc.value.context.details or {})

    def test_slow_pics_allowed(self) -> None:
        """slow.pics is allowed with HTTPS."""
        from frame_compare.utils.http import validate_external_url

        # Should not raise
        validate_external_url("https://slow.pics/api/comparison")

    def test_tmdb_allowed(self) -> None:
        """api.themoviedb.org is allowed with HTTPS."""
        from frame_compare.utils.http import validate_external_url

        # Should not raise
        validate_external_url("https://api.themoviedb.org/3/search/movie")

    def test_allowed_hosts_is_frozen(self) -> None:
        """ALLOWED_HOSTS cannot be modified at runtime."""
        from frame_compare.utils.http import ALLOWED_HOSTS

        assert isinstance(ALLOWED_HOSTS, frozenset), (
            "ALLOWED_HOSTS should be frozenset for immutability"
        )

    def test_error_inheritance(self) -> None:
        """Security errors inherit from NetworkError."""
        from frame_compare.errors import (
            HostNotAllowedError,
            HttpsRequiredError,
            NetworkError,
        )

        assert issubclass(HttpsRequiredError, NetworkError)
        assert issubclass(HostNotAllowedError, NetworkError)

    def test_security_errors_have_exit_code_6(self) -> None:
        """Security policy errors use exit code 6 (network category)."""
        from frame_compare.errors import HostNotAllowedError, HttpsRequiredError

        assert HttpsRequiredError.EXIT_CODE == 6
        assert HostNotAllowedError.EXIT_CODE == 6
