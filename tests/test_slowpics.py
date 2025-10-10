from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, cast

import pytest
import requests

from src import slowpics
from src.datatypes import SlowpicsConfig


class FakeResponse:
    def __init__(self, status_code: int = 200, json_data: Any | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.content = text.encode("utf-8")

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


class FakeSession:
    def __init__(self, responses: List[FakeResponse], cookies: dict[str, str] | None = None) -> None:
        self._responses = responses
        self.headers: dict[str, str] = {}
        base = {"XSRF-TOKEN": "token"} if cookies is None else cookies
        self.cookies: FakeCookies = FakeCookies(base)
        self.calls: list[dict[str, Any]] = []

    def _next(self) -> FakeResponse:
        if not self._responses:
            raise AssertionError("Unexpected request: no prepared response")
        return self._responses.pop(0)

    def get(self, url: str, timeout: float | None = None) -> requests.Response:
        self.calls.append({"method": "GET", "url": url, "timeout": timeout})
        return cast(requests.Response, self._next())

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
        self.calls.append(
            {
                "method": "POST",
                "url": url,
                "timeout": timeout,
                "json": json,
                "files": files,
                "data": data,
                "headers": headers,
            }
        )
        return cast(requests.Response, self._next())


def _install_session(
    monkeypatch: pytest.MonkeyPatch,
    responses: List[FakeResponse],
    cookies: dict[str, str] | None = None,
) -> FakeSession:
    session = FakeSession(responses, cookies)
    monkeypatch.setattr(slowpics.requests, "Session", lambda: session)
    return session


class DummyEncoder:
    instances: List["DummyEncoder"] = []

    def __init__(self, fields: dict[str, Any], boundary: str) -> None:
        self.fields = fields
        self.boundary = boundary
        self.content_type = "multipart/form-data"
        self.len = len(str(fields))
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


def test_session_bootstrap_single_shot(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = SlowpicsConfig()
    image = _write_image(tmp_path, "123 - ClipA.png")

    responses = [
        FakeResponse(200),
        FakeResponse(200, {"collectionUuid": "abc", "key": "def", "images": [["img1"]]}),
        FakeResponse(200, text="OK"),
    ]
    session = _install_session(monkeypatch, responses)

    url = slowpics.upload_comparison([str(image)], tmp_path, cfg)

    assert url == "https://slow.pics/c/def"
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


def test_missing_xsrf_token_raises(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = SlowpicsConfig()
    image = _write_image(tmp_path, "123 - ClipA.png")

    responses = [FakeResponse(200)]
    _install_session(monkeypatch, responses, cookies={})

    with pytest.raises(slowpics.SlowpicsAPIError, match="Missing XSRF token"):
        slowpics.upload_comparison([str(image)], tmp_path, cfg)


def test_legacy_collection_creation_fields(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_legacy_collection_tmdb_identifier_normalization(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_tmdb_identifier_accepts_prefixed_values(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_legacy_image_upload_loop(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_large_image_upload_scales_timeout(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_image_upload_non_ok_raises(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_no_json_api_calls(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_url_short_form_always(tmp_path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
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


def test_url_matches_creation_key(tmp_path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
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


def test_missing_key_raises(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = SlowpicsConfig()
    image = _write_image(tmp_path, "123 - ClipA.png")

    responses = [
        FakeResponse(200),
        FakeResponse(200, {"collectionUuid": "abc", "images": [["img1"]]}),
    ]
    _install_session(monkeypatch, responses)

    with pytest.raises(slowpics.SlowpicsAPIError, match="Missing collection key in slow.pics response"):
        slowpics.upload_comparison([str(image)], tmp_path, cfg)
