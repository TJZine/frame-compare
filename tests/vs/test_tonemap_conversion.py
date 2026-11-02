import asyncio
from unittest.mock import MagicMock

import pytest
import vapoursynth as vs

import frame_compare.vs.tonemap_conversion as tonemap_module


def test_to_rgbs_no_op_when_already_rgbs_real():
    from frame_compare.vs.tonemap_conversion import to_rgbs

    mock_clip = MagicMock()
    mock_clip.format.id = vs.RGBS

    result = to_rgbs(mock_clip)

    assert result is mock_clip
    mock_clip.resize.Bicubic.assert_not_called()


def test_to_rgbs_converts_non_rgbs():
    from frame_compare.vs.tonemap_conversion import to_rgbs

    mock_clip = MagicMock()
    mock_clip.format.id = 1

    mock_resized = MagicMock()
    mock_clip.resize.Bicubic.return_value = mock_resized

    result = to_rgbs(mock_clip)

    assert result is mock_resized
    mock_clip.resize.Bicubic.assert_called_once_with(
        format=vs.RGBS,
        matrix_in=vs.MATRIX_BT709,
        range_in=vs.RANGE_LIMITED,
    )


@pytest.mark.parametrize(
    "props, is_hdr, expected_kwargs",
    [
        pytest.param(
            {"_Matrix": 9},
            True,
            {"matrix_in": 9, "range_in": vs.RANGE_LIMITED},
            id="existing_matrix",
        ),
        pytest.param(
            {"_Matrix": b"9"},
            True,
            {"matrix_in": 9, "range_in": vs.RANGE_LIMITED},
            id="parseable_matrix",
        ),
        pytest.param(
            {"_Matrix": 9, "_Transfer": 16, "_Primaries": 9, "_Range": vs.RANGE_LIMITED},
            True,
            {"matrix_in": 9, "range_in": vs.RANGE_LIMITED, "transfer_in": 16, "primaries_in": 9},
            id="complete_signal",
        ),
        pytest.param(
            {"_Matrix": 9, "_ColorRange": 1},
            True,
            {"matrix_in": 9, "range_in": vs.RANGE_LIMITED},
            id="deprecated_limited",
        ),
        pytest.param(
            {"_Matrix": 9, "_ColorRange": 0},
            True,
            {"matrix_in": 9, "range_in": vs.RANGE_FULL},
            id="deprecated_full",
        ),
        pytest.param(
            {"_Matrix": 2},
            False,
            {"matrix_in": vs.MATRIX_BT709, "range_in": vs.RANGE_LIMITED},
            id="unspecified_sdr",
        ),
        pytest.param(
            {"_Matrix": 2},
            True,
            {"matrix_in": vs.MATRIX_BT2020_NCL, "range_in": vs.RANGE_LIMITED},
            id="unspecified_hdr",
        ),
        pytest.param(
            {"_Matrix": "oops"},
            False,
            {"matrix_in": vs.MATRIX_BT709, "range_in": vs.RANGE_LIMITED},
            id="unparseable_sdr",
        ),
        pytest.param(
            {"_Matrix": b"oops"},
            True,
            {"matrix_in": vs.MATRIX_BT2020_NCL, "range_in": vs.RANGE_LIMITED},
            id="unparseable_bytes_hdr",
        ),
    ],
)
def test_convert_non_rgb_signal_cases(
    props: dict[str, object], is_hdr: bool, expected_kwargs: dict[str, int]
) -> None:
    clip = MagicMock()
    resized = MagicMock()
    clip.resize.Bicubic.return_value = resized
    result = tonemap_module.convert_non_rgb_with_matrix_hint(
        clip, target_format=vs.RGBS, props=props, detected_is_hdr=is_hdr
    )
    assert result is resized
    clip.resize.Bicubic.assert_called_once_with(format=vs.RGBS, **expected_kwargs)


@pytest.mark.parametrize("operation", ["metadata", "rgb_conversion"])
@pytest.mark.parametrize("interrupted_before_frame", [False, True])
def test_tonemap_conversion_checks_frame_and_next_native_admission(
    operation: str, interrupted_before_frame: bool
) -> None:
    from frame_compare.utils.cancellation import _RunInterrupt, cancellation_checkpoint

    async def run() -> None:
        task = asyncio.current_task()
        assert task is not None
        clip = MagicMock()

        def frame(_index: int) -> MagicMock:
            task.cancel()
            return MagicMock(props={"_Matrix": 9, "_Transfer": 16, "_Primaries": 9})

        clip.get_frame.side_effect = frame
        if interrupted_before_frame:
            task.cancel()
        with pytest.raises(_RunInterrupt):
            if operation == "metadata":
                tonemap_module.resolve_hdr_tonemap_inputs(clip, None)
            else:
                tonemap_module.convert_non_rgb_with_matrix_hint(clip, target_format=vs.RGBS)
        assert clip.get_frame.call_count == (0 if interrupted_before_frame else 1)
        clip.resize.Bicubic.assert_not_called()
        assert task.cancelling() == 1
        await cancellation_checkpoint()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run())
