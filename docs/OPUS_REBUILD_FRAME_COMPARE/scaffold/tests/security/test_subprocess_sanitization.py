"""Tests for subprocess argument sanitization (FC-3010/FC-3011).

Verifies that subprocess arguments are properly validated to prevent
shell injection and control character attacks.
"""
import pytest

pytestmark = pytest.mark.tier_a


class TestSubprocessSanitization:
    """Test subprocess argument validation.

    Security invariants:
    - FC-3010: Reject shell metacharacters in subprocess arguments
    - FC-3011: Reject control characters in subprocess arguments
    """

    @pytest.mark.parametrize("bad_char", [";", "|", "&", "$", "`"])
    def test_shell_metachar_rejected(self, bad_char: str) -> None:
        """Shell metacharacters raise FC-3010 INVALID_SUBPROCESS_ARG."""
        from frame_compare.errors import InvalidSubprocessArgError
        from frame_compare.utils.subproc import validate_subprocess_arg

        with pytest.raises(InvalidSubprocessArgError) as exc_info:
            validate_subprocess_arg(f"file{bad_char}name.mkv")

        assert exc_info.value.code == "FC-3010"

    @pytest.mark.parametrize("control_char", ["\x00", "\x01", "\x1b", "\x7f", "\n", "\r"])
    def test_control_char_rejected(self, control_char: str) -> None:
        """Control characters raise FC-3011 CONTROL_CHAR_IN_ARG."""
        from frame_compare.errors import ControlCharInArgError
        from frame_compare.utils.subproc import validate_subprocess_arg

        with pytest.raises(ControlCharInArgError) as exc_info:
            validate_subprocess_arg(f"file{control_char}name.mkv")

        assert exc_info.value.code == "FC-3011"

    def test_valid_path_passes(self) -> None:
        """Normal file path passes sanitization."""
        from frame_compare.utils.subproc import validate_subprocess_arg

        # Should not raise
        result = validate_subprocess_arg("/path/to/video file (2024).mkv")
        assert result == "/path/to/video file (2024).mkv"

    def test_valid_numeric_arg_passes(self) -> None:
        """Numeric arguments pass sanitization."""
        from frame_compare.utils.subproc import validate_subprocess_arg

        result = validate_subprocess_arg("-crf")
        assert result == "-crf"

        result = validate_subprocess_arg("23")
        assert result == "23"

    def test_ffmpeg_filter_complex_rejected(self) -> None:
        """Complex filter strings with shell chars are rejected."""
        from frame_compare.errors import InvalidSubprocessArgError
        from frame_compare.utils.subproc import validate_subprocess_arg

        # This should be constructed safely, not passed as a raw string
        with pytest.raises(InvalidSubprocessArgError):
            validate_subprocess_arg("scale=1920:-1;overlay=0:0")
