from pathlib import Path
from typing import Any, List

import pytest
import requests

from src.datatypes import SlowpicsConfig
from src import slowpics


class FakeResponse:
    def __init__(self, status_code: int = 200, json_data: Any | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def json(self) -> Any:
        if self._json_data is None:
            raise ValueError("No JSON content")
        return self._json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}", response=self)


class FakeSession:
    def __init__(self, responses: List[FakeResponse], cookies: dict[str, str] | None = None) -> None:
        self._responses = responses
        self.headers: dict[str, str] = {}
        self.cookies = {"XSRF-TOKEN": "token"} if cookies is None else cookies
        self.calls: list[dict[str, Any]] = []

    def _next(self) -> FakeResponse:
        if not self._responses:
            raise AssertionError("Unexpected request: no prepared response")
        return self._responses.pop(0)

    def get(self, url: str, timeout: float | None = None):
        self.calls.append({"method": "GET", "url": url})
        return self._next()

    def post(self, url: str, *, json: Any | None = None, files: Any | None = None, data: Any | None = None, timeout: float | None = None):
        self.calls.append({"method": "POST", "url": url, "json": json, "files": files, "data": data})
        return self._next()


def _install_session(monkeypatch: pytest.MonkeyPatch, responses: List[FakeResponse], cookies: dict[str, str] | None = None) -> FakeSession:
    session = FakeSession(responses, cookies)
    monkeypatch.setattr(slowpics.requests, "Session", lambda: session)
    return session


def test_happy_path_returns_url(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = SlowpicsConfig(collection_name="Test", webhook_url="https://example.com/hook")
    image = tmp_path / "frame.png"
    image.write_bytes(b"data")

    responses = [
        FakeResponse(200, text=""),
        FakeResponse(200, {"uuid": "abc", "key": "def"}),
        FakeResponse(200),
        FakeResponse(200),
        FakeResponse(200),
    ]
    session = _install_session(monkeypatch, responses)

    url = slowpics.upload_comparison([str(image)], tmp_path, cfg)

    assert url == "https://slow.pics/c/abc/def"
    shortcut = tmp_path / "slowpics_abc.url"
    assert shortcut.exists()
    assert [call["method"] for call in session.calls] == ["GET", "POST", "POST", "POST", "POST"]
    assert session.calls[-1]["url"] == "https://example.com/hook"


def test_create_collection_4xx_raises(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = SlowpicsConfig()
    image = tmp_path / "frame.png"
    image.write_bytes(b"data")

    responses = [
        FakeResponse(200),
        FakeResponse(400, text="bad request"),
    ]
    _install_session(monkeypatch, responses)

    with pytest.raises(slowpics.SlowpicsAPIError):
        slowpics.upload_comparison([str(image)], tmp_path, cfg)


def test_upload_failure_raises(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = SlowpicsConfig()
    image = tmp_path / "frame.png"
    image.write_bytes(b"data")

    responses = [
        FakeResponse(200),
        FakeResponse(200, {"uuid": "abc", "key": "def"}),
        FakeResponse(500, text="server error"),
    ]
    _install_session(monkeypatch, responses)

    with pytest.raises(slowpics.SlowpicsAPIError):
        slowpics.upload_comparison([str(image)], tmp_path, cfg)


def test_webhook_direct_post_failures_logged(tmp_path, monkeypatch: pytest.MonkeyPatch, caplog) -> None:
    cfg = SlowpicsConfig(collection_name="Test", webhook_url="https://example.com/hook")
    image = tmp_path / "frame.png"
    image.write_bytes(b"data")

    responses = [
        FakeResponse(200),
        FakeResponse(200, {"uuid": "abc", "key": "def"}),
        FakeResponse(200),
        FakeResponse(200),
        FakeResponse(500, text="fail"),
        FakeResponse(500, text="fail"),
        FakeResponse(500, text="fail"),
    ]
    session = _install_session(monkeypatch, responses)
    monkeypatch.setattr(slowpics.time, "sleep", lambda _: None)

    with caplog.at_level("WARNING"):
        url = slowpics.upload_comparison([str(image)], tmp_path, cfg)

    assert url == "https://slow.pics/c/abc/def"
    assert any("Webhook post attempt" in record.message for record in caplog.records)
    assert session.calls[-1]["method"] == "POST"


def test_missing_xsrf_token_raises(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = SlowpicsConfig()
    image = tmp_path / "frame.png"
    image.write_bytes(b"data")

    responses = [FakeResponse(200)]
    _install_session(monkeypatch, responses, cookies={})

    with pytest.raises(slowpics.SlowpicsAPIError):
        slowpics.upload_comparison([str(image)], tmp_path, cfg)
