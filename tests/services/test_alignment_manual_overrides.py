"""Viewer-neutral manual alignment override persistence tests."""

from __future__ import annotations

from pathlib import Path
from typing import IO, Any
from unittest.mock import patch

import pytest

from frame_compare.services.alignment_manual_overrides import (
    MANUAL_OVERRIDES_FILE,
    ManualOverride,
    load_manual_overrides,
    save_manual_override,
)


def _override(comparison: str, offset: int) -> ManualOverride:
    return ManualOverride(
        reference_clip="ref",
        comparison_clip=comparison,
        frame_offset=offset,
        timestamp="2026-01-03T12:00:00Z",
    )


def test_manual_overrides_v2_round_trip_preserves_values(tmp_path: Path) -> None:
    first = _override("comp_a", 42)
    second = _override("comp_b", -10)

    save_manual_override(tmp_path, first)
    save_manual_override(tmp_path, second)

    assert load_manual_overrides(tmp_path) == {
        "ref:comp_a": first,
        "ref:comp_b": second,
    }


def test_load_manual_overrides_missing_file_is_empty(tmp_path: Path) -> None:
    assert load_manual_overrides(tmp_path) == {}


def test_load_manual_overrides_corrupt_file_is_empty(tmp_path: Path) -> None:
    (tmp_path / MANUAL_OVERRIDES_FILE).write_text(
        "this is not valid TOML [[[",
        encoding="utf-8",
    )

    assert load_manual_overrides(tmp_path) == {}


def test_load_manual_overrides_invalid_utf8_file_is_empty(tmp_path: Path) -> None:
    (tmp_path / MANUAL_OVERRIDES_FILE).write_bytes(b"\xff")

    assert load_manual_overrides(tmp_path) == {}


def test_load_manual_overrides_unsupported_version_is_empty(tmp_path: Path) -> None:
    (tmp_path / MANUAL_OVERRIDES_FILE).write_text(
        'version = "999"\n["ref:comp"]\nframe_offset = 4\n',
        encoding="utf-8",
    )

    assert load_manual_overrides(tmp_path) == {}


def test_load_manual_overrides_skips_invalid_entries(tmp_path: Path) -> None:
    (tmp_path / MANUAL_OVERRIDES_FILE).write_text(
        """\
version = "2"

["ref:invalid"]
reference_clip = "ref"
comparison_clip = "invalid"
frame_offset = true
timestamp = "2026-01-03T12:00:00Z"

["ref:valid"]
reference_clip = "ref"
comparison_clip = "valid"
frame_offset = -7
timestamp = "2026-01-03T12:00:00Z"
""",
        encoding="utf-8",
    )

    assert load_manual_overrides(tmp_path) == {"ref:valid": _override("valid", -7)}


def test_load_manual_overrides_read_error_is_empty(tmp_path: Path) -> None:
    path = tmp_path / MANUAL_OVERRIDES_FILE
    path.write_text('version = "2"\n', encoding="utf-8")

    with (
        patch("pathlib.Path.open", side_effect=OSError("permission denied")),
        patch("frame_compare.services.alignment_manual_overrides.log.warning") as warning,
    ):
        result = load_manual_overrides(tmp_path)

    assert result == {}
    assert warning.call_args.args[0] == "manual_overrides_read_error"


def test_save_manual_override_merges_overwrites_and_orders_keys(tmp_path: Path) -> None:
    zeta = _override("zeta", 10)
    alpha = _override("alpha", 20)
    updated_zeta = _override("zeta", 99)

    save_manual_override(tmp_path, zeta)
    save_manual_override(tmp_path, alpha)
    save_manual_override(tmp_path, updated_zeta)

    assert load_manual_overrides(tmp_path) == {
        "ref:alpha": alpha,
        "ref:zeta": updated_zeta,
    }
    content = (tmp_path / MANUAL_OVERRIDES_FILE).read_text(encoding="utf-8")
    assert "confirmed" not in content
    assert content.startswith('version = "2"')
    assert content.index('["ref:alpha"]') < content.index('["ref:zeta"]')


def test_save_manual_override_read_error_replaces_stale_file(tmp_path: Path) -> None:
    path = tmp_path / MANUAL_OVERRIDES_FILE
    path.write_text(
        'version = "2"\n["old:entry"]\nreference_clip = "old"\n'
        'comparison_clip = "entry"\nframe_offset = 1\n'
        'timestamp = "2026-01-03T12:00:00Z"\n',
        encoding="utf-8",
    )
    override = _override("comp", 99)
    original_open = Path.open

    def _open_with_read_failure(
        open_path: Path,
        mode: str = "r",
        buffering: int = -1,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> IO[Any]:
        if open_path == path and "r" in mode:
            raise OSError("stale handle")
        return original_open(open_path, mode, buffering, encoding, errors, newline)

    with (
        patch("pathlib.Path.open", _open_with_read_failure),
        patch("frame_compare.services.alignment_manual_overrides.log.warning") as warning,
    ):
        save_manual_override(tmp_path, override)

    assert warning.call_args.args[0] == "manual_overrides_read_existing_error"
    assert load_manual_overrides(tmp_path) == {"ref:comp": override}


def test_save_manual_override_invalid_utf8_replaces_stale_file(tmp_path: Path) -> None:
    path = tmp_path / MANUAL_OVERRIDES_FILE
    path.write_bytes(b"\xff")
    override = _override("comp", 99)

    save_manual_override(tmp_path, override)

    assert load_manual_overrides(tmp_path) == {"ref:comp": override}


def test_save_manual_override_write_error_is_warning_only(tmp_path: Path) -> None:
    with (
        patch(
            "frame_compare.services.alignment_manual_overrides.write_bytes_atomic",
            side_effect=OSError("disk full"),
        ),
        patch("frame_compare.services.alignment_manual_overrides.log.warning") as warning,
    ):
        save_manual_override(tmp_path, _override("comp", 10))

    assert warning.call_args.args[0] == "manual_overrides_write_error"


def test_pending_interrupt_prevents_atomic_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio
    import os

    from frame_compare.utils.cancellation import _RunInterrupt, cancellation_checkpoint

    target = tmp_path / MANUAL_OVERRIDES_FILE
    real_fsync = os.fsync

    def cancel_at_fsync(fd: int) -> None:
        real_fsync(fd)
        task = asyncio.current_task()
        assert task is not None
        task.cancel()

    monkeypatch.setattr("frame_compare.utils.atomic_write.os.fsync", cancel_at_fsync)

    async def publish() -> None:
        with pytest.raises(_RunInterrupt):
            save_manual_override(tmp_path, _override("comp", 2))
        await cancellation_checkpoint()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(publish())
    assert not target.exists()
    assert list(target.parent.glob(f".{target.name}.*")) == []


@pytest.mark.parametrize("confirmed", ["true", "false"])
def test_previous_format_is_rejected_and_replaced(tmp_path: Path, confirmed: str) -> None:
    path = tmp_path / MANUAL_OVERRIDES_FILE
    path.write_text(
        'version = "1"\n["ref:old"]\nreference_clip = "ref"\n'
        'comparison_clip = "old"\nframe_offset = 0\n'
        f'timestamp = "2026-01-03T12:00:00Z"\nconfirmed = {confirmed}\n',
        encoding="utf-8",
    )
    assert load_manual_overrides(tmp_path) == {}
    replacement = _override("new", 0)
    save_manual_override(tmp_path, replacement)
    assert load_manual_overrides(tmp_path) == {"ref:new": replacement}
    assert "confirmed" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "content",
    [
        pytest.param("x = " + "{x=" * 1500 + "0" + "}" * 1500, id="deep"),
        pytest.param("x = " + "1" * 5000, id="integer-limit"),
    ],
)
def test_parser_limits_miss_and_write_repairs(tmp_path: Path, content: str) -> None:
    (tmp_path / MANUAL_OVERRIDES_FILE).write_text(content, encoding="utf-8")
    assert load_manual_overrides(tmp_path) == {}
    override = _override("comp", 7)
    with patch("frame_compare.services.alignment_manual_overrides.log.warning") as warning:
        save_manual_override(tmp_path, override)
    warning.assert_called_once_with(
        "manual_overrides_corrupt_on_write", path=str(tmp_path / MANUAL_OVERRIDES_FILE)
    )
    assert load_manual_overrides(tmp_path) == {"ref:comp": override}
