from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from frame_compare.errors import PathEscapesRootError
from frame_compare.utils.file_lock import FileLockTimeoutError, exclusive_file_lock
from tests.integration import alignment_u4_media_recipes as recipe_source
from tests.integration.alignment_u4_media_recipes import PAIRS, RECIPES, MediaRecipe
from tests.integration.alignment_u4_media_store import GENERATOR, media_key, open_u4_media


def _version() -> bytes:
    return b"ffmpeg-test\nconfiguration: all flags\n"


def _writer(path: Path) -> None:
    path.write_bytes(b"complete-media")


def test_key_uses_exact_recipe_source_and_complete_ffmpeg_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "recipes.py"
    source.write_bytes(Path(recipe_source.__file__).read_bytes())
    monkeypatch.setattr(recipe_source, "__file__", str(source))
    expected = hashlib.sha256(b"u4-media-v1\0" + source.read_bytes() + b"\0" + _version())
    original = media_key(_version())
    assert original == expected.hexdigest()
    for unrelated in ("test_alignment_u4_acceptance.py", "alignment_u4_media_store.py"):
        (tmp_path / unrelated).write_text("assert True\n", encoding="utf-8")
        assert media_key(_version()) == original
    assert media_key(_version() + b"different flags") != original
    source.write_bytes(source.read_bytes() + b"\n# recipe edit\n")
    assert media_key(_version()) != original


def test_demand_dependencies_pairs_and_full_matrix(tmp_path: Path) -> None:
    created: list[str] = []

    def writer(name: str) -> Callable[[Path], None]:
        def write(path: Path) -> None:
            for dependency in RECIPES[name].requires:
                assert (path.parent / f"u4-{dependency}.mkv").read_bytes() == b"complete-media"
            created.append(name)
            _writer(path)

        return write

    recipes = {name: replace(recipe, writer=writer(name)) for name, recipe in RECIPES.items()}
    with open_u4_media(
        tmp_path / "session",
        cache_root=tmp_path / "cache",
        full_matrix=False,
        ffmpeg_version=_version,
        recipes=recipes,
    ) as store:
        assert created == []
        reference, comparison = store.pair("replacement-4")
        assert created == ["reference", "replacement-4"]
        assert reference.is_symlink() and comparison.is_symlink()
        assert reference.read_bytes() == comparison.read_bytes() == b"complete-media"
        # A decoder's adjacent index belongs to this session, outside reusable media.
        comparison.with_suffix(".lwi").write_bytes(b"index")
        assert not list(store.storage.glob("*.lwi"))
        store.path("retimed-25")
        store.path("retimed-25-ntsc")
        assert created == [
            "reference",
            "replacement-4",
            "retimed-25",
            "retimed-ntsc-reference",
            "retimed-25-ntsc",
        ]
        assert store.pair("multipath")[0].name == "u4-multipath-reference.mkv"
        assert store.pair("surround-local")[0].name == "u4-surround-reference.mkv"
        store.materialize_all()
        assert len(created) == len(RECIPES) == 40
        assert set(store.stats["created"]) == set(RECIPES)
        assert set(PAIRS) == set(RECIPES) - {name for name in RECIPES if name.endswith("reference")}
        assert len(list(store.storage.glob("*.mkv"))) == 40

    with open_u4_media(
        tmp_path / "warm",
        cache_root=tmp_path / "cache",
        full_matrix=True,
        ffmpeg_version=_version,
        recipes=recipes,
    ) as store:
        assert store.stats["created"] == []
        assert set(store.stats["reused"]) == set(RECIPES)
        assert len(created) == 40


def test_without_cache_is_lazy_and_publishes_regular_files(tmp_path: Path) -> None:
    with open_u4_media(
        tmp_path,
        cache_root=None,
        full_matrix=False,
        ffmpeg_version=_version,
        recipes={"reference": MediaRecipe(_writer)},
    ) as store:
        assert not list(tmp_path.iterdir())
        path = store.path("reference")
        assert path.read_bytes() == b"complete-media"
        assert not path.is_symlink()
        assert store.path("reference") == path
        assert store.stats["created"] == ["reference"]


def test_pruning_is_owned_and_does_not_unlink_held_lock(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    generator = cache / GENERATOR
    generator.mkdir(parents=True)
    foreign = cache / "another-generator" / "key"
    foreign.mkdir(parents=True)
    sentinel = foreign / "keep"
    sentinel.write_bytes(b"foreign")
    for name in ("old-key", ".tmp-abandoned"):
        (generator / name).mkdir()
        (generator / name / "partial").write_bytes(b"old")
    (generator / ".temporary").write_bytes(b"old")
    current = generator / media_key(_version())
    current.mkdir()
    (current / ".u4-reference.tmp.mkv").write_bytes(b"partial")
    (current / "u4-reference.mkv").write_bytes(b"complete-media")
    lock = generator / ".verifier.lock"
    lock.write_bytes(b"lock")
    inode = lock.stat().st_ino
    with open_u4_media(
        tmp_path / "session",
        cache_root=cache,
        full_matrix=False,
        ffmpeg_version=_version,
        recipes={"reference": MediaRecipe(_writer)},
    ) as store:
        assert set(generator.iterdir()) == {current, lock}
        assert set(current.iterdir()) == {current / "u4-reference.mkv"}
        assert lock.stat().st_ino == inode
        with pytest.raises(FileLockTimeoutError), exclusive_file_lock(lock, timeout_seconds=0):
            pass
        assert store.path("reference").read_bytes() == b"complete-media"
        assert store.stats["reused"] == ["reference"]
    assert sentinel.read_bytes() == b"foreign"


@pytest.mark.parametrize("redirect", ["generator", "current-key"])
def test_redirected_cache_directory_is_refused_before_pruning(
    tmp_path: Path, redirect: str
) -> None:
    cache = tmp_path / "cache"
    generator = cache / GENERATOR
    redirected = generator if redirect == "generator" else generator / media_key(_version())
    redirected.parent.mkdir(parents=True)
    external = tmp_path / "external"
    hidden = external / ".retain-this"
    hidden.mkdir(parents=True)
    sentinel = hidden / "sentinel.txt"
    sentinel.write_bytes(b"unrelated data")
    redirected.symlink_to(external, target_is_directory=True)

    with (
        pytest.raises(PathEscapesRootError, match="escapes root"),
        open_u4_media(
            tmp_path / "session",
            cache_root=cache,
            full_matrix=False,
            ffmpeg_version=_version,
            recipes={},
        ),
    ):
        pass

    assert sentinel.read_bytes() == b"unrelated data"
    assert set(external.iterdir()) == {hidden}
    assert redirected.is_symlink()


def test_writer_failure_never_publishes_partial_and_retry_succeeds(tmp_path: Path) -> None:
    attempts = 0

    def failing(path: Path) -> None:
        nonlocal attempts
        attempts += 1
        path.write_bytes(b"partial")
        if attempts == 1:
            raise RuntimeError("writer failed")
        path.write_bytes(b"complete-media")

    with open_u4_media(
        tmp_path / "session",
        cache_root=tmp_path / "cache",
        full_matrix=False,
        ffmpeg_version=_version,
        recipes={"reference": MediaRecipe(failing)},
    ) as store:
        with pytest.raises(RuntimeError, match="writer failed"):
            store.path("reference")
        assert list(store.storage.iterdir()) == []
        assert list(store.root.iterdir()) == []
        assert store.stats["created"] == []
        assert store.path("reference").read_bytes() == b"complete-media"
        assert store.stats["created"] == ["reference"]


def test_session_lock_rejects_overlap_until_teardown(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    lock = cache / GENERATOR / ".verifier.lock"

    def writer(path: Path) -> None:
        with pytest.raises(FileLockTimeoutError), exclusive_file_lock(lock, timeout_seconds=0):
            pass
        _writer(path)

    def open_session(name: str):
        return open_u4_media(
            tmp_path / name,
            cache_root=cache,
            full_matrix=False,
            ffmpeg_version=_version,
            recipes={"reference": MediaRecipe(writer)},
        )

    with open_session("first") as first:
        first.path("reference")
        unfinished = cache / GENERATOR / ".tmp-other-verifier"
        unfinished.mkdir()
        with pytest.raises(FileLockTimeoutError), open_session("overlap"):
            pass
        # Use a distinct process too: a removed/recreated lock inode would admit it.
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import sys
from pathlib import Path
from frame_compare.utils.file_lock import exclusive_file_lock, FileLockTimeoutError
try:
    with exclusive_file_lock(Path(sys.argv[1]), timeout_seconds=0):
        raise SystemExit('overlap admitted')
except FileLockTimeoutError:
    pass
""",
                str(lock),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        assert unfinished.is_dir()
    with open_session("next") as next_session:
        assert next_session.path("reference").read_bytes() == b"complete-media"
        assert not unfinished.exists()


def test_worker_stats_are_written_on_session_teardown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifacts = tmp_path / "artifacts"
    monkeypatch.setenv("FRAME_COMPARE_E2E_ARTIFACTS", str(artifacts))
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw3")
    with open_u4_media(
        tmp_path / "session",
        cache_root=None,
        full_matrix=True,
        ffmpeg_version=_version,
        recipes={"reference": MediaRecipe(_writer)},
    ) as store:
        key = store.key
    (stats_path,) = artifacts.glob("u4-media-gw3-*.json")
    stats = json.loads(stats_path.read_text())
    assert stats["key"] == key
    assert stats["created"] == ["reference"]
    assert stats["reused"] == []
    assert stats["seconds"]["reference"] >= 0
