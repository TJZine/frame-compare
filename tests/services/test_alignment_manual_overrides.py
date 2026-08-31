"""Viewer-neutral manual alignment override persistence tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from frame_compare.services.alignment_manual_overrides import (
    MANUAL_OVERRIDES_FILE,
    ManualOverride,
    load_manual_overrides,
    save_manual_override,
)


def _override(comparison: str, offset: int, *, confirmed: bool = True) -> ManualOverride:
    return ManualOverride(
        reference_clip="ref",
        comparison_clip=comparison,
        frame_offset=offset,
        timestamp="2026-01-03T12:00:00Z",
        confirmed=confirmed,
    )


def test_manual_overrides_v1_round_trip_preserves_values(tmp_path: Path) -> None:
    first = _override("comp_a", 42)
    second = _override("comp_b", -10, confirmed=False)

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


def test_load_manual_overrides_unsupported_version_is_empty(tmp_path: Path) -> None:
    (tmp_path / MANUAL_OVERRIDES_FILE).write_text(
        'version = "999"\n["ref:comp"]\nframe_offset = 4\n',
        encoding="utf-8",
    )

    assert load_manual_overrides(tmp_path) == {}


def test_load_manual_overrides_skips_invalid_entries(tmp_path: Path) -> None:
    (tmp_path / MANUAL_OVERRIDES_FILE).write_text(
        """\
version = "1"

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
confirmed = false
""",
        encoding="utf-8",
    )

    assert load_manual_overrides(tmp_path) == {"ref:valid": _override("valid", -7, confirmed=False)}


def test_load_manual_overrides_read_error_is_empty(tmp_path: Path) -> None:
    path = tmp_path / MANUAL_OVERRIDES_FILE
    path.write_text('version = "1"\n', encoding="utf-8")

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
    updated_zeta = _override("zeta", 99, confirmed=False)

    save_manual_override(tmp_path, zeta)
    save_manual_override(tmp_path, alpha)
    save_manual_override(tmp_path, updated_zeta)

    assert load_manual_overrides(tmp_path) == {
        "ref:alpha": alpha,
        "ref:zeta": updated_zeta,
    }
    content = (tmp_path / MANUAL_OVERRIDES_FILE).read_text(encoding="utf-8")
    assert content.startswith('version = "1"')
    assert content.index('["ref:alpha"]') < content.index('["ref:zeta"]')


def test_save_manual_override_uses_atomic_bytes_write(tmp_path: Path) -> None:
    override = _override("comp", 10)
    calls: list[tuple[Path, bytes]] = []

    def _write(path: Path, content: bytes) -> None:
        calls.append((path, content))
        path.write_bytes(content)

    with patch(
        "frame_compare.services.alignment_manual_overrides.write_bytes_atomic",
        _write,
    ):
        save_manual_override(tmp_path, override)

    assert [path for path, _ in calls] == [tmp_path / MANUAL_OVERRIDES_FILE]
    assert load_manual_overrides(tmp_path) == {"ref:comp": override}


def test_save_manual_override_read_error_replaces_stale_file(tmp_path: Path) -> None:
    path = tmp_path / MANUAL_OVERRIDES_FILE
    path.write_text(
        'version = "1"\n["old:entry"]\nreference_clip = "old"\n'
        'comparison_clip = "entry"\nframe_offset = 1\n'
        'timestamp = "2026-01-03T12:00:00Z"\n',
        encoding="utf-8",
    )
    override = _override("comp", 99)
    original_open = Path.open

    def _open_with_read_failure(open_path: Path, mode: str = "r", *args: object, **kwargs: object):
        if open_path == path and "r" in mode:
            raise OSError("stale handle")
        return original_open(open_path, mode, *args, **kwargs)

    with (
        patch("pathlib.Path.open", _open_with_read_failure),
        patch("frame_compare.services.alignment_manual_overrides.log.warning") as warning,
    ):
        save_manual_override(tmp_path, override)

    assert warning.call_args.args[0] == "manual_overrides_read_existing_error"
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
