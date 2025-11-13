from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, List

import pytest
import requests
from _pytest.logging import LogCaptureFixture

import src.frame_compare.slowpics as slowpics
from src.datatypes import SlowpicsConfig
from src.frame_compare import net


class FakeResponse(requests.Response):
    def __init__(self, status_code: int = 200, json_data: Any | None = None, text: str = "") -> None:
        super().__init__()
        self.status_code = status_code
        self._json_data = json_data
        self._content = text.encode("utf-8")
        self.encoding = "utf-8"

    def json(self) -> Any:
        if self._json_data is None:
            raise ValueError("No JSON content")
        return self._json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}", response=self)


class FakeCookies(dict):
    def get_dict(self) -> dict[str, str]:
        return dict(self)


class SessionRecorder:
    """Tracks every FakeSession created during a test run."""

    def __init__(self, responses: List[FakeResponse], cookies: dict[str, str] | None = None) -> None:
        self._responses = responses
        self._cookies = cookies
        self.sessions: List["FakeSession"] = []
        self.responses_lock = threading.Lock()
        self.calls: list[dict[str, Any]] = []
        self.mounts: list[tuple[str, Any]] = []
        self._calls_lock = threading.Lock()
        self._mounts_lock = threading.Lock()

    def new_session(self) -> "FakeSession":
        session_id = len(self.sessions)
        session = FakeSession(
            self._responses,
            self._cookies,
            session_id=session_id,
            recorder=self,
            responses_lock=self.responses_lock,
        )
        self.sessions.append(session)
        return session

    def record_call(self, entry: dict[str, Any]) -> None:
        with self._calls_lock:
            self.calls.append(entry)

    def record_mount(self, prefix: str, adapter: Any) -> None:
        with self._mounts_lock:
            self.mounts.append((prefix, adapter))

    @property
    def closed(self) -> bool:
        if not self.sessions:
            return False
        return self.sessions[0].closed


class FakeSession:
    def __init__(
        self,
        responses: List[FakeResponse],
        cookies: dict[str, str] | None = None,
        *,
        session_id: int = 0,
        recorder: SessionRecorder | None = None,
        responses_lock: threading.Lock | None = None,
    ) -> None:
        self._responses = responses
        self._responses_lock = responses_lock or threading.Lock()
        self.headers: dict[str, str] = {}
        base = {"XSRF-TOKEN": "token"} if cookies is None else dict(cookies)
        self.cookies: FakeCookies = FakeCookies(base)
        self.calls: list[dict[str, Any]] = []
        self.closed = False
        self._lock = threading.Lock()
        self.mounts: list[tuple[str, Any]] = []
        self._recorder = recorder
        self._session_id = session_id

    def close(self) -> None:
        self.closed = True

    def __enter__(self) -> "FakeSession":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: Any | None,
    ) -> bool:
        self.close()
        return False

    def _next(self) -> FakeResponse:
        with self._responses_lock:
            if not self._responses:
                raise AssertionError("Unexpected request: no prepared response")
            return self._responses.pop(0)

    def _record_call(self, entry: dict[str, Any]) -> None:
        with self._lock:
            self.calls.append(entry)
        if self._recorder is not None:
            self._recorder.record_call(entry)

    def get(self, url: str, timeout: float | None = None) -> requests.Response:
        self._record_call({"method": "GET", "url": url, "timeout": timeout})
        return self._next()

    def post(
        self,
        url: str,
        *,
        json: Any | None = None,
        files: Any | None = None,
        data: Any | None = None,
        headers: Any | None = None,
        timeout: float | None = None,
    ) -> requests.Response:
        entry = {
            "method": "POST",
            "url": url,
            "timeout": timeout,
            "json": json,
            "files": files,
            "data": data,
            "headers": headers,
        }
        self._record_call(entry)
        return self._next()

    def mount(self, prefix: str, adapter: Any) -> None:
        with self._lock:
            self.mounts.append((prefix, adapter))
        if self._recorder is not None:
            self._recorder.record_mount(prefix, adapter)


def _install_session(
    monkeypatch: pytest.MonkeyPatch,
    responses: List[FakeResponse],
    cookies: dict[str, str] | None = None,
) -> SessionRecorder:
    recorder = SessionRecorder(responses, cookies)
    monkeypatch.setattr(slowpics.requests, "Session", recorder.new_session)
    return recorder


class DummyEncoder:
    instances: List["DummyEncoder"] = []
    _lock = threading.Lock()

    def __init__(self, fields: dict[str, Any], boundary: str) -> None:
        self.fields = fields
        self.boundary = boundary
        self.content_type = "multipart/form-data"
        self.len = len(str(fields))
        with DummyEncoder._lock:
            DummyEncoder.instances.append(self)

    def to_string(self) -> bytes:
        return b"encoded"


@pytest.fixture(autouse=True)
def _install_encoder(monkeypatch: pytest.MonkeyPatch):
    DummyEncoder.instances = []
    monkeypatch.setattr(slowpics, "MultipartEncoder", DummyEncoder)


def _write_image(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_bytes(b"data")
    return path


def test_session_bootstrap_single_shot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    cfg = SlowpicsConfig()
    image = _write_image(tmp_path, "123 - ClipA.png")

    captured_adapter: dict[str, Any] = {}

    class DummyAdapter:
        def __init__(
            self,
            *,
            max_retries: Any,
            pool_connections: int,
            pool_maxsize: int,
        ) -> None:
            captured_adapter["max_retries"] = max_retries
            captured_adapter["pool_connections"] = pool_connections
            captured_adapter["pool_maxsize"] = pool_maxsize

    monkeypatch.setattr(slowpics, "HTTPAdapter", DummyAdapter)
    caplog.set_level(logging.INFO, logger="src.frame_compare.slowpics")

    responses = [
        FakeResponse(200),
        FakeResponse(200, {"collectionUuid": "abc", "key": "def", "images": [["img1"]]}),
        FakeResponse(200, text="OK"),
    ]
    session = _install_session(monkeypatch, responses)

    url = slowpics.upload_comparison([str(image)], tmp_path, cfg)

    assert url == "https://slow.pics/c/def"
    assert session.closed is True
    assert len(session.calls) == 3
    landing = session.calls[0]
    assert landing["method"] == "GET"
    assert landing["url"] == "https://slow.pics/comparison"
    assert landing["timeout"] == 10
    post_urls = [call["url"] for call in session.calls[1:]]
    assert post_urls == ["https://slow.pics/upload/comparison", "https://slow.pics/upload/image"]
    assert len(DummyEncoder.instances) == 2  # comparison + image
    image_call = session.calls[2]
    assert image_call["timeout"][0] == pytest.approx(10.0)
    assert image_call["timeout"][1] >= cfg.image_upload_timeout_seconds
    assert session.mounts and session.mounts[0][0] == "https://"
    adapter_kwargs = captured_adapter
    assert adapter_kwargs["max_retries"].total == 3
    assert adapter_kwargs["max_retries"].backoff_factor == pytest.approx(0.1)
    assert adapter_kwargs["max_retries"].allowed_methods == net.ALLOWED_METHODS
    assert adapter_kwargs["max_retries"].status_forcelist == net.RETRY_STATUS
    assert adapter_kwargs["pool_connections"] == 4
    assert adapter_kwargs["pool_maxsize"] == 4
    assert any("slow.pics upload complete" in record.getMessage() for record in caplog.records)


def test_missing_xsrf_token_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = SlowpicsConfig()
    image = _write_image(tmp_path, "123 - ClipA.png")

    responses = [FakeResponse(200)]
    _install_session(monkeypatch, responses, cookies={})

    with pytest.raises(slowpics.SlowpicsAPIError, match="Missing XSRF token"):
        slowpics.upload_comparison([str(image)], tmp_path, cfg)


def test_legacy_collection_creation_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = SlowpicsConfig(
        collection_name="My Collection",
        is_hentai=True,
        remove_after_days=3,
        tmdb_id="TMDB123",
    )

    files = [
        _write_image(tmp_path, "100 - ClipA.png"),
        _write_image(tmp_path, "100 - ClipB.png"),
        _write_image(tmp_path, "200 - ClipA.png"),
        _write_image(tmp_path, "200 - ClipB.png"),
    ]

    responses = [
        FakeResponse(200),
        FakeResponse(200, {"collectionUuid": "abc", "key": "def", "images": [["img1", "img2"], ["img3", "img4"]]}),
        FakeResponse(200, text="OK"),
        FakeResponse(200, text="OK"),
        FakeResponse(200, text="OK"),
        FakeResponse(200, text="OK"),
    ]
    _install_session(monkeypatch, responses)

    url = slowpics.upload_comparison([str(path) for path in files], tmp_path, cfg)
    assert url == "https://slow.pics/c/def"

    comparison_fields = DummyEncoder.instances[0].fields
    assert comparison_fields["collectionName"] == "My Collection"
    assert comparison_fields["hentai"] == "true"
    assert comparison_fields["optimize-images"] == "true"
    assert comparison_fields["public"] == "true"
    assert comparison_fields["tmdbId"] == "TMDB123"
    assert comparison_fields["removeAfter"] == "3"
    assert "browserId" in comparison_fields
    assert comparison_fields["comparisons[0].name"] == "100"
    assert comparison_fields["comparisons[0].imageNames[0]"] == "ClipA"
    assert comparison_fields["comparisons[0].imageNames[1]"] == "ClipB"
    assert comparison_fields["comparisons[1].name"] == "200"


def test_legacy_collection_tmdb_identifier_normalization(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = SlowpicsConfig(
        collection_name="Example",
        tmdb_id="98765",
        tmdb_category="MOVIE",
    )

    files = [
        _write_image(tmp_path, "10 - ClipA.png"),
        _write_image(tmp_path, "10 - ClipB.png"),
    ]

    responses = [
        FakeResponse(200),
        FakeResponse(200, {"collectionUuid": "abc", "key": "def", "images": [["img1", "img2"]]}),
        FakeResponse(200, text="OK"),
        FakeResponse(200, text="OK"),
    ]
    _install_session(monkeypatch, responses)

    slowpics.upload_comparison([str(path) for path in files], tmp_path, cfg)

    comparison_fields = DummyEncoder.instances[0].fields
    assert comparison_fields["tmdbId"] == "MOVIE_98765"


def test_tmdb_identifier_accepts_prefixed_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = SlowpicsConfig(
        collection_name="Example",
        tmdb_id="tv/76543",
    )

    files = [
        _write_image(tmp_path, "10 - ClipA.png"),
        _write_image(tmp_path, "10 - ClipB.png"),
    ]

    responses = [
        FakeResponse(200),
        FakeResponse(200, {"collectionUuid": "abc", "key": "def", "images": [["img1", "img2"]]}),
        FakeResponse(200, text="OK"),
        FakeResponse(200, text="OK"),
    ]
    _install_session(monkeypatch, responses)

    slowpics.upload_comparison([str(path) for path in files], tmp_path, cfg)

    comparison_fields = DummyEncoder.instances[0].fields
    assert comparison_fields["tmdbId"] == "TV_76543"


def test_progress_callback_invoked_per_image(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = SlowpicsConfig(collection_name="Example")
    files = [
        _write_image(tmp_path, "10 - ClipA.png"),
        _write_image(tmp_path, "10 - ClipB.png"),
    ]
    responses = [
        FakeResponse(200),
        FakeResponse(200, {"collectionUuid": "abc", "key": "def", "images": [["img1", "img2"]]}),
        FakeResponse(200, text="OK"),
        FakeResponse(200, text="OK"),
    ]
    _install_session(monkeypatch, responses)
    calls: list[int] = []

    def progress(value: int) -> None:
        calls.append(value)

    slowpics.upload_comparison(
        [str(path) for path in files],
        tmp_path,
        cfg,
        progress_callback=progress,
        max_workers=2,
    )

    assert sum(calls) == len(files)


def test_worker_sessions_reused_for_multiple_uploads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = SlowpicsConfig(collection_name="ReusePool")
    files = [
        _write_image(tmp_path, "10 - ClipA.png"),
        _write_image(tmp_path, "10 - ClipB.png"),
        _write_image(tmp_path, "20 - ClipA.png"),
        _write_image(tmp_path, "20 - ClipB.png"),
    ]
    responses = [
        FakeResponse(200),
        FakeResponse(
            200,
            {"collectionUuid": "abc", "key": "def", "images": [["img1", "img2"], ["img3", "img4"]]},
        ),
    ]
    responses.extend(FakeResponse(200, text="OK") for _ in files)
    recorder = _install_session(monkeypatch, responses)

    slowpics.upload_comparison([str(path) for path in files], tmp_path, cfg, max_workers=2)

    # requests.Session is called for bootstrap + collection + worker_count sessions
    assert len(recorder.sessions) == 1 + 1 + min(2, len(files))
    worker_sessions = recorder.sessions[2:]
    assert len(worker_sessions) == min(2, len(files))
    per_session_uploads = [
        sum(1 for call in session.calls if call["url"].endswith("/upload/image"))
        for session in worker_sessions
    ]
    assert sum(per_session_uploads) == len(files)
    # At least one worker should handle multiple uploads when there are more jobs than workers.
    assert any(count >= 2 for count in per_session_uploads)


def test_legacy_image_upload_loop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = SlowpicsConfig()
    image = _write_image(tmp_path, "123 - ClipA.png")

    responses = [
        FakeResponse(200),
        FakeResponse(200, {"collectionUuid": "abc", "key": "def", "images": [["img1"]]}),
        FakeResponse(200, text="OK"),
    ]
    _install_session(monkeypatch, responses)

    slowpics.upload_comparison([str(image)], tmp_path, cfg)

    # Instance 0: collection creation, Instance 1: image upload
    upload_fields = DummyEncoder.instances[1].fields
    assert upload_fields["collectionUuid"] == "abc"
    assert upload_fields["imageUuid"] == "img1"
    assert "browserId" in upload_fields
    file_tuple = upload_fields["file"]
    assert file_tuple[0] == "123 - ClipA.png"
    assert file_tuple[2] == "image/png"


def test_large_image_upload_scales_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = SlowpicsConfig(image_upload_timeout_seconds=30)
    image = tmp_path / "123 - ClipA.png"
    image.write_bytes(b"x" * 8 * 1024 * 1024)  # 8 MiB file

    responses = [
        FakeResponse(200),
        FakeResponse(200, {"collectionUuid": "abc", "key": "def", "images": [["img1"]]}),
        FakeResponse(200, text="OK"),
    ]
    session = _install_session(monkeypatch, responses)

    slowpics.upload_comparison([str(image)], tmp_path, cfg)

    image_call = session.calls[-1]
    assert image_call["timeout"][0] == pytest.approx(10.0)
    assert image_call["timeout"][1] > cfg.image_upload_timeout_seconds


def test_image_upload_non_ok_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = SlowpicsConfig()
    image = _write_image(tmp_path, "123 - ClipA.png")

    responses = [
        FakeResponse(200),
        FakeResponse(200, {"collectionUuid": "abc", "key": "def", "images": [["img1"]]}),
        FakeResponse(200, text="not ok"),
    ]
    _install_session(monkeypatch, responses)

    with pytest.raises(slowpics.SlowpicsAPIError, match="Unexpected slow.pics response"):
        slowpics.upload_comparison([str(image)], tmp_path, cfg)


def test_no_json_api_calls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = SlowpicsConfig()
    image = _write_image(tmp_path, "123 - ClipA.png")

    responses = [
        FakeResponse(200),
        FakeResponse(200, {"collectionUuid": "abc", "key": "def", "images": [["img1"]]}),
        FakeResponse(200, text="OK"),
    ]
    session = _install_session(monkeypatch, responses)

    slowpics.upload_comparison([str(image)], tmp_path, cfg)

    assert all("/api/" not in call["url"] for call in session.calls if call["method"] == "POST")


def test_url_short_form_always(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    cfg = SlowpicsConfig()
    image = _write_image(tmp_path, "123 - ClipA.png")

    responses = [
        FakeResponse(200),
        FakeResponse(
            200,
            {
                "collectionUuid": "collection-uuid",
                "key": "Dq2Nb5Mx",
                "images": [["img1"]],
            },
        ),
        FakeResponse(200, text="OK"),
    ]
    _install_session(monkeypatch, responses)

    with caplog.at_level(logging.INFO):
        url = slowpics.upload_comparison([str(image)], tmp_path, cfg)

    assert url == "https://slow.pics/c/Dq2Nb5Mx"
    assert f"Slow.pics: {url}" in caplog.messages
    assert all("/c/collection-uuid/" not in message for message in caplog.messages)


def test_url_matches_creation_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    cfg = SlowpicsConfig()
    image = _write_image(tmp_path, "123 - ClipA.png")

    responses = [
        FakeResponse(200),
        FakeResponse(
            200,
            {
                "collectionUuid": "legacy-uuid",
                "key": "c74BM7mj",
                "images": [["img-from-response"]],
            },
        ),
        FakeResponse(200, text="OK"),
    ]
    _install_session(monkeypatch, responses)

    with caplog.at_level(logging.INFO):
        url = slowpics.upload_comparison([str(image)], tmp_path, cfg)

    assert url == "https://slow.pics/c/c74BM7mj"
    assert f"Slow.pics: {url}" in caplog.messages
    assert len(DummyEncoder.instances) >= 2
    upload_fields = DummyEncoder.instances[1].fields
    assert upload_fields["collectionUuid"] == "legacy-uuid"
    assert upload_fields["imageUuid"] == "img-from-response"


def test_shortcut_write_failure_does_not_abort_upload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: LogCaptureFixture,
) -> None:
    cfg = SlowpicsConfig(create_url_shortcut=True)
    image = _write_image(tmp_path, "123 - ClipA.png")

    responses = [
        FakeResponse(200),
        FakeResponse(200, {"collectionUuid": "abc", "key": "def", "images": [["img1"]]}),
        FakeResponse(200, text="OK"),
    ]
    _install_session(monkeypatch, responses)

    original_write_text = Path.write_text

    def failing_write_text(
        self: Path,
        data: str,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> int:
        if self.suffix.lower() == ".url":
            raise OSError("disk full")
        return original_write_text(self, data, encoding=encoding, errors=errors, newline=newline)

    monkeypatch.setattr(Path, "write_text", failing_write_text)
    caplog.set_level(logging.WARNING, logger="src.frame_compare.slowpics")

    url = slowpics.upload_comparison([str(image)], tmp_path, cfg)

    assert url == "https://slow.pics/c/def"
    assert not list(tmp_path.glob("*.url"))
    assert any("Failed to write slow.pics shortcut" in record.getMessage() for record in caplog.records)


@pytest.mark.parametrize(
    ("collection_name", "canonical_url", "expected"),
    [
        ("Simple Title", "https://slow.pics/c/abc123", "Simple_Title.url"),
        ("Title with / separators", "https://slow.pics/c/key", "Title_with_separators.url"),
        ("   ", "https://slow.pics/c/key", "key.url"),
        ("../escape_attempt", "https://slow.pics/c/key", "escape_attempt.url"),
    ],
)
def test_build_shortcut_filename_sanitizes_and_falls_back(
    collection_name: str,
    canonical_url: str,
    expected: str,
) -> None:
    actual = slowpics.build_shortcut_filename(collection_name, canonical_url)
    assert actual == expected


def test_build_shortcut_filename_uses_default_when_no_segment() -> None:
    actual = slowpics.build_shortcut_filename("", "not-a-url")
    assert actual == "not-a-url.url"


def test_build_shortcut_filename_truncates_long_names() -> None:
    long_name = "x" * 200
    filename = slowpics.build_shortcut_filename(long_name, "https://slow.pics/c/key")
    assert filename.endswith(".url")
    basename = filename[:-4]
    assert len(basename) == 120
    assert set(basename) == {"x"}


def test_missing_key_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = SlowpicsConfig()
    image = _write_image(tmp_path, "123 - ClipA.png")

    responses = [
        FakeResponse(200),
        FakeResponse(200, {"collectionUuid": "abc", "images": [["img1"]]}),
    ]
    _install_session(monkeypatch, responses)

    with pytest.raises(slowpics.SlowpicsAPIError, match="Missing collection key in slow.pics response"):
        slowpics.upload_comparison([str(image)], tmp_path, cfg)
