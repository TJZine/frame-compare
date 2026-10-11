from pathlib import Path

import pytest
from rich.console import Console

from frame_compare.analysis.errors import (
    MetricsCalculationError,
    SelectionError,
)
from frame_compare.cli.errors import (
    ExitCode,
    format_error_console,
    get_exit_code,
)
from frame_compare.errors import (
    ErrorContext,
    FrameCompareError,
    PathEscapesRootError,
    normalize_pydantic_errors,
    redact_url_for_error,
)
from frame_compare.orchestration.errors import (
    DirectoryNotFoundError,
    NoVideosFoundError,
)
from frame_compare.render.errors import (
    EncodingError,
    FrameExtractionError,
    OverlayError,
    RenderError,
)
from frame_compare.services.errors import (
    AudioAlignmentError,
    MetadataError,
    ReportError,
    SlowpicsError,
    SlowpicsRateLimitedError,
    SlowpicsUnavailableError,
    TmdbError,
    TmdbRateLimitedError,
)
from frame_compare.utils.cache_errors import CacheCorruptionError, CacheVersionMismatchError
from frame_compare.utils.ffmpeg_errors import FFmpegError, FFmpegNotFoundError
from frame_compare.vs.errors import (
    PluginNotFoundError,
    SourceLoadError,
    TonemapError,
    TonemapRequiresVapourSynthError,
    VapourSynthError,
    VapourSynthNotFoundError,
)
from frame_compare.vsview.errors import (
    VSViewError,
    VSViewNotFoundError,
)


def _render_rich_markup(markup: str) -> str:
    console = Console(record=True, no_color=True, width=200)
    console.print(markup)
    return console.export_text(styles=False)


@pytest.mark.parametrize(
    "error_class,args,expected_code",
    [
        # DependencyError (FC-2xxx)
        (VapourSynthNotFoundError, (), "FC-2001"),
        (VapourSynthError, ("test",), "FC-2002"),
        (PluginNotFoundError, ("lsmas",), "FC-2003"),
        (FFmpegNotFoundError, (), "FC-2005"),
        (FFmpegError, ("test", 1), "FC-2006"),
        (VSViewNotFoundError, (), "FC-2008"),
        (TonemapRequiresVapourSynthError, (), "FC-2009"),
        # InputError (FC-3xxx)
        (NoVideosFoundError, (Path("/test"),), "FC-3001"),
        (DirectoryNotFoundError, (Path("/test"),), "FC-3006"),
        (PathEscapesRootError, (Path("/root"), Path("/other")), "FC-3009"),
        # ProcessingError (FC-4xxx)
        (FrameExtractionError, (42, "clip.mkv"), "FC-4001"),
        (MetricsCalculationError, ("test",), "FC-4002"),
        (TonemapError, ("test",), "FC-4003"),
        (RenderError, (), "FC-4004"),
        (AudioAlignmentError, ("test",), "FC-4005"),
        (CacheCorruptionError, (Path("/cache"),), "FC-4006"),
        (CacheVersionMismatchError, ("1.0", "2.0"), "FC-4007"),
        (SelectionError, ("reason", 10, 5), "FC-4012"),
        (EncodingError, (Path("/out.png"), "test"), "FC-4013"),
        (OverlayError, ("test",), "FC-4014"),
        (SourceLoadError, (Path("/src"), "test"), "FC-4015"),
        (MetadataError, ("test",), "FC-4016"),
        (ReportError, ("test",), "FC-4017"),
        (VSViewError, ("test",), "FC-4019"),
        # NetworkError (FC-5xxx)
        (SlowpicsError, ("test",), "FC-5002"),
        (SlowpicsRateLimitedError, (), "FC-5003"),
        (SlowpicsUnavailableError, (), "FC-5004"),
        (TmdbError, ("test",), "FC-5005"),
        (TmdbRateLimitedError, (), "FC-5006"),
    ],
)
def test_exception_class_contract(error_class, args, expected_code):
    """Every exception has correct code, non-empty name, non-empty hint, valid to_dict()."""
    error = error_class(*args)
    assert error.name
    assert error.hint
    ctx_dict = error.context.to_dict()
    assert ctx_dict["code"] == expected_code
    assert "message" in ctx_dict


def test_vsview_error_omits_public_details() -> None:
    error = VSViewError("launch exited with code 3")

    assert error.context.message == "VSView failed: launch exited with code 3"
    assert error.context.details is None


def test_exit_code_enum_values():
    assert ExitCode.SUCCESS == 0
    assert ExitCode.GENERAL_ERROR == 1
    assert ExitCode.CONFIG_ERROR == 2
    assert ExitCode.DEPENDENCY_ERROR == 3
    assert ExitCode.INPUT_ERROR == 4
    assert ExitCode.PROCESSING_ERROR == 5
    assert ExitCode.NETWORK_ERROR == 6
    assert ExitCode.INTERRUPTED == 130


def test_get_exit_code_unknown():
    error = FrameCompareError(ErrorContext(code="FC-0000", name="UNKNOWN", message="test"))
    assert get_exit_code(error) == ExitCode.GENERAL_ERROR


@pytest.mark.parametrize(
    "code,expected",
    [
        ("FC-1000", ExitCode.CONFIG_ERROR),
        ("FC-2000", ExitCode.DEPENDENCY_ERROR),
        ("FC-3000", ExitCode.INPUT_ERROR),
        ("FC-4000", ExitCode.PROCESSING_ERROR),
        ("FC-5000", ExitCode.NETWORK_ERROR),
    ],
)
def test_get_exit_code_maps_by_error_code_prefix_for_generic_error(code, expected):
    error = FrameCompareError(ErrorContext(code=code, name="GENERIC", message="test"))
    assert get_exit_code(error) == expected


@pytest.mark.parametrize(
    ("error", "verbose", "hint", "present", "absent"),
    [
        (
            VapourSynthNotFoundError(),
            False,
            "--verbose",
            ["Hint:"],
            ["Details:", "For more details, run with --verbose"],
        ),
        (
            CacheCorruptionError(Path("/cache")),
            True,
            "--verbose",
            ["Details:", "path:", str(Path("/cache"))],
            [],
        ),
        (
            CacheCorruptionError(Path("/cache")),
            False,
            "--verbose",
            ["For more details, run with --verbose"],
            ["Details:"],
        ),
        (
            CacheCorruptionError(Path("/cache")),
            False,
            None,
            ["Details:", "path:"],
            ["For more details, run with --verbose"],
        ),
        (RenderError(), True, "--verbose", [], ["Details:"]),
        (
            FrameCompareError(
                ErrorContext(
                    code="FC-3001",
                    name="BRACKETED_VALUE",
                    message="File [1080p] missing",
                    hint="Try [literal] brackets",
                    details={"path": "C:/videos/[sample].mkv"},
                )
            ),
            True,
            "--verbose",
            [
                "Error [FC-3001]: File [1080p] missing",
                "Hint: Try [literal] brackets",
                "path: C:/videos/[sample].mkv",
            ],
            ["[[FC-3001]]"],
        ),
    ],
    ids=[
        "basic",
        "verbose-details",
        "hidden-details",
        "no-hint",
        "verbose-empty",
        "literal-brackets",
    ],
)
def test_format_error_console_details_and_literal_markup(
    error: FrameCompareError,
    verbose: bool,
    hint: str | None,
    present: list[str],
    absent: list[str],
) -> None:
    rendered = _render_rich_markup(format_error_console(error, verbose=verbose, verbose_hint=hint))
    assert f"Error [{error.code}]: {error.context.message}" in rendered
    for fragment in present:
        assert fragment in rendered
    for fragment in absent:
        assert fragment not in rendered


def test_error_context_omits_non_public_and_empty_fields() -> None:
    context = ErrorContext(
        code="FC-0001",
        name="SAMPLE",
        message="Sample failure",
        details={},
        hint="",
        cause=RuntimeError("secret stack detail"),
    )

    assert context.to_dict() == {
        "code": "FC-0001",
        "name": "SAMPLE",
        "message": "Sample failure",
    }
    assert "secret stack detail" not in str(FrameCompareError(context))


def test_error_formatting_helpers_are_json_safe() -> None:
    url = "https://user:secret@[2001:db8::1]:443/path?api_key=secret#frag"
    assert redact_url_for_error(url) == "https://[2001:db8::1]:443/path"

    assert normalize_pydantic_errors(
        [
            {
                "loc": ("analysis", "frame_count"),
                "ctx": {"limit": 100, "path": Path("/config.toml")},
            }
        ]
    ) == [
        {
            "loc": ["analysis", "frame_count"],
            "ctx": {"limit": 100, "path": str(Path("/config.toml"))},
        }
    ]
