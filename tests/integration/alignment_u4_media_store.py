"""Session-owned, lazy U4 media publication without native runtime imports."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import uuid
from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import TypedDict

from frame_compare.utils.file_lock import exclusive_file_lock
from frame_compare.utils.paths import require_managed_immediate_child
from frame_compare.utils.subproc import run_subprocess
from tests.integration import alignment_u4_media_recipes as recipe_source
from tests.integration.alignment_u4_media_recipes import PAIRS, RECIPES, MediaRecipe

GENERATOR = "test_alignment_u4_acceptance"


def _ffmpeg_version() -> bytes:
    return run_subprocess(["ffmpeg", "-version"], timeout_seconds=10).stdout


def media_key(ffmpeg_version: bytes) -> str:
    return hashlib.sha256(
        b"u4-media-v1\0" + Path(recipe_source.__file__).read_bytes() + b"\0" + ffmpeg_version
    ).hexdigest()


class MediaStats(TypedDict):
    key: str
    created: list[str]
    reused: list[str]
    seconds: dict[str, float]


class U4MediaStore:
    def __init__(
        self,
        root: Path,
        storage: Path,
        key: str,
        recipes: Mapping[str, MediaRecipe],
    ) -> None:
        self.root = root
        self.storage = storage
        self.key = key
        self.recipes = recipes
        self._created: list[str] = []
        self._reused: list[str] = []
        self._seconds: dict[str, float] = {}
        self._materialized: dict[str, Path] = {}

    @property
    def stats(self) -> MediaStats:
        return {
            "key": self.key,
            "created": list(self._created),
            "reused": list(self._reused),
            "seconds": dict(self._seconds),
        }

    def path(self, name: str) -> Path:
        if name in self._materialized:
            return self._materialized[name]
        recipe = self.recipes[name]
        for dependency in recipe.requires:
            self.path(dependency)
        destination = self.storage / f"u4-{name}.mkv"
        started = time.perf_counter()
        if destination.is_file():
            self._reused.append(name)
        else:
            temporary = destination.with_name(f".{destination.stem}.tmp{destination.suffix}")
            try:
                recipe.writer(temporary)
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
            self._created.append(name)
        self._seconds[name] = time.perf_counter() - started
        session_path = self.root / destination.name
        if session_path != destination:
            session_path.symlink_to(destination)
        self._materialized[name] = session_path
        return session_path

    def pair(self, name: str) -> tuple[Path, Path]:
        reference, comparison = PAIRS[name]
        return self.path(reference), self.path(comparison)

    def materialize_all(self) -> None:
        for name in self.recipes:
            self.path(name)

    def write_stats(self) -> None:
        artifact_root = os.environ.get("FRAME_COMPARE_E2E_ARTIFACTS")
        if artifact_root:
            directory = Path(artifact_root)
            directory.mkdir(parents=True, exist_ok=True)
            worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
            path = directory / f"u4-media-{worker}-{uuid.uuid4().hex}.json"
            path.write_text(json.dumps(self.stats, indent=2) + "\n", encoding="utf-8")


def _prune(generator_root: Path, current: Path) -> None:
    for previous in generator_root.iterdir():
        if previous == current or previous.name == ".verifier.lock":
            continue
        if previous.is_symlink():
            previous.unlink()
        elif previous.is_dir():
            shutil.rmtree(previous)
        elif previous.name.startswith("."):
            previous.unlink()
    for temporary in current.iterdir():
        if temporary.name.startswith(".") and temporary.name != ".verifier.lock":
            if temporary.is_dir() and not temporary.is_symlink():
                shutil.rmtree(temporary)
            else:
                temporary.unlink()


@contextmanager
def open_u4_media(
    tmp_root: Path,
    *,
    cache_root: Path | None,
    full_matrix: bool,
    ffmpeg_version: Callable[[], bytes] = _ffmpeg_version,
    recipes: Mapping[str, MediaRecipe] = RECIPES,
) -> Generator[U4MediaStore]:
    key = media_key(ffmpeg_version())
    tmp_root.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def session(storage: Path) -> Generator[U4MediaStore]:
        store = U4MediaStore(tmp_root, storage, key, recipes)
        try:
            if full_matrix:
                store.materialize_all()
            yield store
        finally:
            store.write_stats()

    if cache_root is None:
        with session(tmp_root) as store:
            yield store
        return

    resolved_cache_root = cache_root.resolve()
    generator_root = require_managed_immediate_child(
        resolved_cache_root, resolved_cache_root / GENERATOR
    )
    with exclusive_file_lock(generator_root / ".verifier.lock", timeout_seconds=0):
        cached = require_managed_immediate_child(generator_root, generator_root / key)
        cached.mkdir(exist_ok=True)
        _prune(generator_root, cached)
        with session(cached) as store:
            yield store
