"""Basic tests for the errors module."""

from frame_compare.errors import (
    ConfigNotFoundError,
    ConfigValidationError,
    ErrorContext,
    FrameCompareError,
    NoVideosFoundError,
)


class TestErrorContext:
    """Tests for ErrorContext dataclass."""

    def test_error_context_minimal(self):
        """ErrorContext works with just code and message."""
        ctx = ErrorContext(code="FC-0001", name="TEST_ERROR", message="Test error")
        assert ctx.code == "FC-0001"
        assert ctx.name == "TEST_ERROR"
        assert ctx.message == "Test error"
        assert ctx.hint is None
        assert ctx.details is None

    def test_error_context_full(self):
        """ErrorContext works with all fields."""
        ctx = ErrorContext(
            code="FC-0001",
            name="TEST_ERROR",
            message="Test error",
            details={"key": "value"},
            hint="Try this",
            cause=ValueError("underlying"),
        )
        assert ctx.code == "FC-0001"
        assert ctx.name == "TEST_ERROR"
        assert ctx.message == "Test error"
        assert ctx.hint == "Try this"
        assert ctx.details == {"key": "value"}
        assert isinstance(ctx.cause, ValueError)


class TestFrameCompareError:
    """Tests for base FrameCompareError."""

    def test_error_properties(self):
        """Error exposes context properties."""
        error = FrameCompareError(ErrorContext(
            code="FC-0001",
            name="TEST_ERROR",
            message="Test error",
            hint="Do something",
        ))

        assert error.code == "FC-0001"
        assert error.name == "TEST_ERROR"
        assert error.message == "Test error"
        assert error.hint == "Do something"
        assert str(error) == "Test error"


class TestConfigErrors:
    """Tests for configuration errors."""

    def test_config_not_found(self):
        """ConfigNotFoundError includes path and hint."""
        error = ConfigNotFoundError("/path/to/config.toml")

        assert error.code == "FC-1001"
        assert "/path/to/config.toml" in error.message
        assert error.hint is not None
        assert "wizard" in error.hint

    def test_config_validation_error(self):
        """ConfigValidationError lists invalid fields."""
        errors = [{"loc": ["analysis", "frame_count"], "msg": "too small"}]
        error = ConfigValidationError(errors)

        assert error.code == "FC-1003"
        assert "frame_count" in error.message
        assert error.details is not None


class TestInputErrors:
    """Tests for input errors."""

    def test_no_videos_found(self):
        """NoVideosFoundError includes path and patterns."""
        error = NoVideosFoundError("/workspace/videos", ["*.mkv"])

        assert error.code == "FC-3001"
        assert "/workspace/videos" in error.message
        assert error.details is not None
        assert error.details.get("patterns") == ["*.mkv"]


class TestErrorContextSerialization:
    """Tests for ErrorContext serialization."""

    def test_to_dict_minimal(self):
        """to_dict includes required fields."""
        ctx = ErrorContext(code="FC-0001", name="TEST", message="Test message")
        result = ctx.to_dict()

        assert result["code"] == "FC-0001"
        assert result["name"] == "TEST"
        assert result["message"] == "Test message"
        assert "hint" not in result
        assert "details" not in result

    def test_to_dict_full(self):
        """to_dict includes optional fields when present."""
        ctx = ErrorContext(
            code="FC-0001",
            name="TEST",
            message="Test message",
            hint="Try this",
            details={"key": "value"},
        )
        result = ctx.to_dict()

        assert result["hint"] == "Try this"
        assert result["details"] == {"key": "value"}

