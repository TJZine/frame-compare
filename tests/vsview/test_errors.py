"""VSView error-code contract tests."""

from frame_compare.vsview.errors import VSViewError, VSViewNotFoundError


def test_not_found_error_keeps_numeric_code_with_vsview_name() -> None:
    error = VSViewNotFoundError()

    assert error.context.code == "FC-2008"
    assert error.context.name == "VSVIEW_NOT_FOUND"
    assert "VSView" in error.context.message


def test_runtime_error_keeps_numeric_code_with_vsview_name() -> None:
    error = VSViewError("launch exited with code 7")

    assert error.context.code == "FC-4019"
    assert error.context.name == "VSVIEW_ERROR"
    assert error.public_reason == "launch exited with code 7"
