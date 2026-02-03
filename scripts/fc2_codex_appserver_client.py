#!/usr/bin/env python3
"""Codex app-server JSONL client for FC2 autopilot."""

from __future__ import annotations

import dataclasses
import json
import queue
import subprocess
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO, cast

JsonPrimitive = str | int | float | bool | None
JsonValue = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject = dict[str, JsonValue]


@dataclasses.dataclass(frozen=True)
class TurnCompletion:
    turn_id: str
    status: str
    error: JsonObject | None


@dataclasses.dataclass(frozen=True)
class TurnTranscript:
    turn_id: str
    status: str | None
    error: JsonObject | None
    items: list[JsonObject]


class AppServerError(Exception):
    """Base error for Codex app-server failures."""


class AppServerRequestError(AppServerError):
    """Raised when a request returns an error response."""

    def __init__(self, method: str, error: JsonObject) -> None:
        super().__init__(f"Request failed: {method}: {error}")
        self.method = method
        self.error = error


class AppServerTimeoutError(AppServerError):
    """Raised when waiting for a response or turn completion times out."""


class CodexAppServerProcess:
    """Manage a codex app-server subprocess and JSONL protocol."""

    def __init__(self, *, cwd: Path, event_log_path: Path | None = None) -> None:
        self._cwd = cwd
        self._event_log_path = event_log_path
        self._event_log_handle: TextIO | None = None

        self._process: subprocess.Popen[str] | None = None
        self._reader_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        self._request_id = 0
        self._request_id_lock = threading.Lock()

        self._response_condition = threading.Condition()
        self._responses_by_id: dict[int, JsonObject] = {}

        self._event_queue: queue.Queue[tuple[str, JsonObject]] = queue.Queue()
        self._events_by_turn: dict[str, list[JsonObject]] = {}
        self._events_lock = threading.Lock()

        self._server_request_handler: Callable[[JsonObject], None] | None = None
        self._initialized = False

    def start(self) -> None:
        """Start the app-server subprocess and background reader thread.

        Raises:
            RuntimeError: If the process is already running or stdio cannot be opened.
        """
        if self._process is not None:
            raise RuntimeError("App-server process already started.")

        self._process = subprocess.Popen(
            ["codex", "app-server"],
            cwd=str(self._cwd),
            text=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            bufsize=1,
        )
        if self._process.stdin is None or self._process.stdout is None:
            raise RuntimeError("Failed to open app-server stdio streams.")

        if self._event_log_path is not None:
            self._event_log_path.parent.mkdir(parents=True, exist_ok=True)
            self._event_log_handle = self._event_log_path.open("a", encoding="utf-8")

        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def stop(self) -> None:
        """Terminate the app-server subprocess and close open handles."""
        self._stop_event.set()
        if self._process is None:
            return

        try:
            self._process.terminate()
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=5)

        if self._reader_thread is not None:
            self._reader_thread.join(timeout=2)

        if self._event_log_handle is not None:
            self._event_log_handle.close()

        self._process = None
        self._reader_thread = None
        self._event_log_handle = None

    def set_server_request_handler(self, handler: Callable[[JsonObject], None]) -> None:
        """Register a handler for server-initiated requests (approvals, prompts)."""
        self._server_request_handler = handler

    def initialize(self, *, client_info: JsonObject) -> None:
        """Perform the initialize/initialized handshake.

        Raises:
            RuntimeError: If initialize is called more than once.
            AppServerRequestError: If the server rejects initialization.
        """
        if self._initialized:
            raise RuntimeError("App-server already initialized.")
        _ = self.request("initialize", {"clientInfo": client_info})
        self.notify("initialized", {})
        self._initialized = True

    def request(self, method: str, params: JsonObject) -> JsonObject:
        """Send a JSON-RPC request and return the result payload.

        Raises:
            AppServerRequestError: If the server responds with an error or malformed payload.
            AppServerTimeoutError: If the response times out.
        """
        request_id = self._next_request_id()
        payload: JsonObject = {"id": request_id, "method": method, "params": params}
        self._send(payload)
        response = self._wait_for_response(request_id, timeout_s=60)
        if "error" in response:
            error = response["error"]
            if isinstance(error, dict):
                raise AppServerRequestError(method, error)
            raise AppServerRequestError(method, {"message": "Unknown error", "error": error})
        result = response.get("result")
        if not isinstance(result, dict):
            raise AppServerRequestError(method, {"message": "Malformed result", "result": result})
        return result

    def notify(self, method: str, params: JsonObject) -> None:
        """Send a notification (no response expected)."""
        payload: JsonObject = {"method": method, "params": params}
        self._send(payload)

    def respond(self, request_id: int | str, result: JsonObject) -> None:
        """Respond to a server-initiated request."""
        payload: JsonObject = {"id": request_id, "result": result}
        self._send(payload)

    def wait_for_turn_completed(
        self,
        *,
        thread_id: str,
        turn_id: str,
        timeout_s: float,
        on_notification: Callable[[JsonObject], None] | None = None,
    ) -> TurnCompletion:
        """Wait for a specific turn to complete.

        Raises:
            AppServerTimeoutError: If the turn does not complete within the timeout.
            AppServerError: If the server emits an error notification.
        """
        deadline = time.monotonic() + timeout_s
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AppServerTimeoutError(f"Timed out waiting for turn {turn_id} completion.")

            try:
                kind, payload = self._event_queue.get(timeout=remaining)
            except queue.Empty as exc:
                raise AppServerTimeoutError(
                    f"Timed out waiting for turn {turn_id} completion."
                ) from exc

            if kind == "server_request":
                handler = self._server_request_handler
                if handler is None:
                    raise AppServerError("Server requested approval but no handler is configured.")
                handler(payload)
                continue

            if "error" in payload:
                raise AppServerError(f"App-server error notification: {payload}")

            if on_notification is not None:
                on_notification(payload)

            if _is_turn_completed(payload, turn_id):
                status, error = _parse_turn_completion(payload)
                return TurnCompletion(turn_id=turn_id, status=status, error=error)

    def collect_turn_transcript(self, *, thread_id: str, turn_id: str) -> TurnTranscript:
        """Collect a minimal transcript for a completed turn."""
        del thread_id
        with self._events_lock:
            events = list(self._events_by_turn.get(turn_id, []))

        status: str | None = None
        error: JsonObject | None = None
        items: list[JsonObject] = []

        for event in events:
            method = event.get("method")
            if isinstance(method, str) and method.startswith("item/"):
                items.append(event)
            if _is_turn_completed(event, turn_id):
                status, error = _parse_turn_completion(event)

        return TurnTranscript(turn_id=turn_id, status=status, error=error, items=items)

    def _reader_loop(self) -> None:
        if self._process is None or self._process.stdout is None:
            return
        while not self._stop_event.is_set():
            line = self._process.stdout.readline()
            if not line:
                break
            raw = line.strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                payload = cast(
                    JsonObject,
                    {"error": {"message": "Invalid JSON from app-server", "raw": raw}},
                )
            else:
                if isinstance(parsed, dict):
                    payload = cast(JsonObject, parsed)
                else:
                    payload = cast(
                        JsonObject,
                        {"error": {"message": "Non-object JSON from app-server", "raw": raw}},
                    )

            self._log_event("in", payload)

            if (
                "id" in payload
                and ("result" in payload or "error" in payload)
                and "method" not in payload
            ):
                request_id = payload["id"]
                if isinstance(request_id, int):
                    with self._response_condition:
                        self._responses_by_id[request_id] = payload
                        self._response_condition.notify_all()
                continue

            if (
                "id" in payload
                and "method" in payload
                and "result" not in payload
                and "error" not in payload
            ):
                self._event_queue.put(("server_request", payload))
                continue

            turn_id = _extract_turn_id(payload)
            if turn_id is not None:
                with self._events_lock:
                    self._events_by_turn.setdefault(turn_id, []).append(payload)

            self._event_queue.put(("notification", payload))

    def _next_request_id(self) -> int:
        with self._request_id_lock:
            self._request_id += 1
            return self._request_id

    def _send(self, payload: JsonObject) -> None:
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("App-server process is not running.")
        data = json.dumps(payload, separators=(",", ":"))
        self._process.stdin.write(data + "\n")
        self._process.stdin.flush()
        self._log_event("out", payload)

    def _wait_for_response(self, request_id: int, *, timeout_s: float) -> JsonObject:
        deadline = time.monotonic() + timeout_s
        with self._response_condition:
            while request_id not in self._responses_by_id:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AppServerTimeoutError(
                        f"Timed out waiting for response to request {request_id}."
                    )
                self._response_condition.wait(timeout=remaining)
            return self._responses_by_id.pop(request_id)

    def _log_event(self, direction: str, payload: JsonObject) -> None:
        if self._event_log_handle is None:
            return
        ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        record = {"ts": ts, "direction": direction, "payload": payload}
        handle = self._event_log_handle
        handle.write(json.dumps(record) + "\n")
        handle.flush()


def _extract_turn_id(payload: JsonObject) -> str | None:
    params = payload.get("params")
    if isinstance(params, dict):
        turn_id = params.get("turnId")
        if isinstance(turn_id, str):
            return turn_id
        turn = params.get("turn")
        if isinstance(turn, dict):
            inner_id = turn.get("id")
            if isinstance(inner_id, str):
                return inner_id
    return None


def _is_turn_completed(payload: JsonObject, turn_id: str) -> bool:
    method = payload.get("method")
    if method != "turn/completed":
        return False
    params = payload.get("params")
    if not isinstance(params, dict):
        return False
    turn = params.get("turn")
    if not isinstance(turn, dict):
        return False
    return turn.get("id") == turn_id


def _parse_turn_completion(payload: JsonObject) -> tuple[str, JsonObject | None]:
    params = payload.get("params")
    if not isinstance(params, dict):
        return "unknown", {"message": "Missing params in turn completion"}
    turn = params.get("turn")
    if not isinstance(turn, dict):
        return "unknown", {"message": "Missing turn in completion"}
    status = turn.get("status")
    status_text = status if isinstance(status, str) else "unknown"
    error = None
    if "error" in turn and isinstance(turn["error"], dict):
        error = turn["error"]
    return status_text, error
