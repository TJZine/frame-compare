from __future__ import annotations

import hashlib
import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

_INTER_LICENSE_SHA256 = "262481e844521b326f5ecd053e59b98c8b2da78c8ee1bdbb6e8174305e54935a"


def _load_inventory_owner(repo_root: Path) -> dict[str, object]:
    return cast(
        dict[str, object],
        runpy.run_path(str(repo_root / "tools/windows_portable/write_bundle_inventory.py")),
    )


def _write_packaged_inter_license(bundle: Path, repo_root: Path) -> Path:
    source = repo_root / "src/frame_compare/assets/fonts/Inter-OFL.txt"
    packaged = bundle / "app/src/frame_compare/assets/fonts/Inter-OFL.txt"
    packaged.parent.mkdir(parents=True, exist_ok=True)
    packaged.write_bytes(source.read_bytes())
    return packaged


def test_windows_portable_inventory_promotes_pinned_inter_license(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    bundle = tmp_path / "bundle"
    (bundle / "licenses").mkdir(parents=True)
    packaged = _write_packaged_inter_license(bundle, repo_root)
    owner = _load_inventory_owner(repo_root)
    promote = cast(Callable[[Path], None], owner["_promote_bundled_inter_license"])
    license_inventory = cast(
        Callable[[Path], list[dict[str, object]]],
        owner["_license_inventory"],
    )

    promote(bundle)

    promoted = bundle / "licenses/Inter-OFL.txt"
    assert promoted.read_bytes() == packaged.read_bytes()
    assert hashlib.sha256(promoted.read_bytes()).hexdigest() == _INTER_LICENSE_SHA256
    assert {
        "path": "licenses/Inter-OFL.txt",
        "sha256": _INTER_LICENSE_SHA256,
    } in license_inventory(bundle)


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        (None, "bundled Inter OFL notice is missing"),
        (b"tampered license", "bundled Inter OFL notice SHA-256 mismatch"),
    ],
)
def test_windows_portable_inventory_rejects_invalid_inter_license(
    tmp_path: Path,
    repo_root: Path,
    payload: bytes | None,
    expected_error: str,
) -> None:
    bundle = tmp_path / "bundle"
    (bundle / "licenses").mkdir(parents=True)
    packaged = bundle / "app/src/frame_compare/assets/fonts/Inter-OFL.txt"
    if payload is not None:
        packaged.parent.mkdir(parents=True, exist_ok=True)
        packaged.write_bytes(payload)
    owner = _load_inventory_owner(repo_root)
    promote = cast(Callable[[Path], None], owner["_promote_bundled_inter_license"])

    with pytest.raises(ValueError, match=expected_error):
        promote(bundle)


def test_windows_portable_inventory_documents_inter_source_and_license(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    bundle = tmp_path / "bundle"
    (bundle / "licenses").mkdir(parents=True)
    owner = _load_inventory_owner(repo_root)
    write_source_urls = cast(Callable[..., None], owner["_write_source_urls"])
    write_notices = cast(Callable[..., None], owner["_write_notices"])

    write_source_urls(
        bundle_root=bundle,
        app_version="0.1.0",
        commit_sha="a" * 40,
        artifacts=[],
        corresponding_sources=[],
        distributions=[],
    )
    write_notices(
        bundle_root=bundle,
        artifacts=[],
        corresponding_sources=[],
        distributions=[],
    )

    source_urls = (bundle / "licenses/SOURCE_URLS.txt").read_text(encoding="utf-8")
    notices = (bundle / "licenses/THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8")
    assert (
        "Bundled application assets:\n"
        "- Inter 4.1: https://github.com/rsms/inter/releases/tag/v4.1"
    ) in source_urls
    assert "Bundled application assets:\n- Inter 4.1 (OFL-1.1)" in notices
    assert "source pointers in\nSOURCE_URLS.txt." in notices
