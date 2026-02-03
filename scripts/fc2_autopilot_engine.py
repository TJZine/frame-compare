#!/usr/bin/env python3
"""Engine abstraction for FC2 autopilot (exec vs app-server)."""

from __future__ import annotations

import dataclasses
import json
import select
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, cast

from fc2_codex_appserver_client import (
    AppServerError,
    AppServerRequestError,
    AppServerTimeoutError,
    CodexAppServerProcess,
    JsonObject,
    JsonValue,
)

ROLE_PLANNING = "planning"
ROLE_PLAN_REVIEW = "plan_review"
ROLE_CODING = "coding"
ROLE_VERIFY_REVIEW = "verify_review"


@dataclasses.dataclass(frozen=True)
class RolePolicy:
    model: str
    effort: str


ROLE_POLICY: dict[str, RolePolicy] = {
    ROLE_PLANNING: RolePolicy(model="gpt-5.2", effort="high"),
    ROLE_PLAN_REVIEW: RolePolicy(model="gpt-5.2", effort="high"),
    ROLE_CODING: RolePolicy(model="gpt-5.2-codex", effort="medium"),
    ROLE_VERIFY_REVIEW: RolePolicy(model="gpt-5.2-codex", effort="high"),
}

ROLE_PROFILE: dict[str, str] = {
    ROLE_PLANNING: "fc2_planning",
    ROLE_PLAN_REVIEW: "fc2_plan_review",
    ROLE_CODING: "fc2_coding",
    ROLE_VERIFY_REVIEW: "fc2_verify_review",
}


@dataclasses.dataclass(frozen=True)
class TurnResult:
    turn_id: str | None
    status: str
    error: JsonObject | None
    transcript: JsonObject | None


class AutopilotEngine(Protocol):
    def run_turn(self, *, role: str, message: str, model: str, effort: str) -> TurnResult:
        """Run a single role turn and return the completion metadata."""
        ...

    def close(self) -> None:
        """Release any engine resources."""
        ...


class AutopilotStopError(Exception):
    """Deterministic stop for expected autopilot failures."""


class ExecEngine:
    """Exec-based engine using codex exec profiles."""

    def __init__(self, *, repo_root: Path) -> None:
        self._repo_root = repo_root

    def run_turn(self, *, role: str, message: str, model: str, effort: str) -> TurnResult:
        """Run a single codex exec session for the given role."""
        del model
        del effort
        profile = ROLE_PROFILE.get(role)
        if profile is None:
            raise AutopilotStopError(f"Unknown role for exec engine: {role}")
        _run_codex_exec(self._repo_root, profile, message)
        return TurnResult(turn_id=None, status="completed", error=None, transcript=None)

    def close(self) -> None:
        return


class AppServerEngine:
    """App-server engine with persistent role threads and streamed events."""

    def __init__(
        self,
        *,
        repo_root: Path,
        run_id: str,
        run_dir: Path,
        event_log_path: Path,
        threads_path: Path,
        config_path: Path,
    ) -> None:
        self._repo_root = repo_root
        self._run_id = run_id
        self._run_dir = run_dir
        self._event_log_path = event_log_path
        self._threads_path = threads_path
        self._config_path = config_path

        self._client = CodexAppServerProcess(cwd=repo_root, event_log_path=event_log_path)
        self._client.start()
        try:
            try:
                self._client.initialize(
                    client_info={
                        "name": "fc2_autopilot",
                        "title": "FC2 Autopilot",
                        "version": "1.0.0",
                    }
                )
            except (AppServerRequestError, AppServerTimeoutError, AppServerError) as exc:
                raise AutopilotStopError(f"STOP: app-server initialize failed: {exc}") from exc
            self._client.set_server_request_handler(self._handle_server_request)

            self._preflight_models()
            self._preflight_config()

            self._threads_by_role = self._load_or_create_threads()
            self._role_by_thread = {
                thread_id: role for role, thread_id in self._threads_by_role.items()
            }

            self._active_role: str | None = None
            self._last_progress_ts = 0.0
            self._last_progress_label: str | None = None
        except Exception:
            self._client.stop()
            raise

    def run_turn(self, *, role: str, message: str, model: str, effort: str) -> TurnResult:
        """Run a single app-server turn and wait for completion.

        Raises:
            AutopilotStopError: If the turn fails or the server reports an error.
        """
        thread_id = self._threads_by_role.get(role)
        if thread_id is None:
            raise AutopilotStopError(f"Missing thread id for role {role}")

        summary = _summary_for_model(model)
        params: JsonObject = {
            "threadId": thread_id,
            "cwd": str(self._repo_root),
            "model": model,
            "effort": effort,
            "input": [
                {
                    "type": "text",
                    "text": message,
                }
            ],
        }
        if summary is not None:
            params["summary"] = summary

        try:
            response = self._client.request("turn/start", params)
        except (AppServerRequestError, AppServerTimeoutError, AppServerError) as exc:
            raise AutopilotStopError(f"STOP: app-server turn/start failed: {exc}") from exc

        turn = response.get("turn")
        if not isinstance(turn, dict):
            raise AutopilotStopError("STOP: app-server turn/start response missing turn id.")

        turn_id_value = turn.get("id")
        if not isinstance(turn_id_value, str):
            raise AutopilotStopError("STOP: app-server turn/start response missing turn id.")
        turn_id = turn_id_value
        self._active_role = role

        try:
            completion = self._client.wait_for_turn_completed(
                thread_id=thread_id,
                turn_id=turn_id,
                timeout_s=60 * 60,
                on_notification=self._handle_notification,
            )
        except (AppServerTimeoutError, AppServerError) as exc:
            raise AutopilotStopError(f"STOP: app-server turn failed: {exc}") from exc

        transcript = self._client.collect_turn_transcript(thread_id=thread_id, turn_id=turn_id)
        if completion.status != "completed":
            raise AutopilotStopError(
                f"STOP: app-server turn not completed: {completion.status} {completion.error}"
            )

        transcript_payload = cast(
            JsonObject,
            {
                "turn_id": transcript.turn_id,
                "status": transcript.status,
                "error": transcript.error,
                "items": transcript.items,
            },
        )
        return TurnResult(
            turn_id=turn_id,
            status=completion.status,
            error=completion.error,
            transcript=transcript_payload,
        )

    def close(self) -> None:
        self._client.stop()

    def _preflight_models(self) -> None:
        try:
            response = self._client.request("model/list", {})
        except (AppServerRequestError, AppServerTimeoutError, AppServerError) as exc:
            raise AutopilotStopError(f"STOP: app-server model/list failed: {exc}") from exc

        data = response.get("data")
        if not isinstance(data, list):
            raise AutopilotStopError("STOP: app-server model/list response missing data.")

        model_efforts: dict[str, set[str]] = {}
        for entry in data:
            if not isinstance(entry, dict):
                continue
            model_name = entry.get("model")
            if not isinstance(model_name, str):
                continue
            supported = entry.get("supportedReasoningEfforts")
            if not isinstance(supported, list):
                continue
            efforts: set[str] = set()
            for effort_entry in supported:
                if not isinstance(effort_entry, dict):
                    continue
                effort = effort_entry.get("reasoningEffort")
                if isinstance(effort, str):
                    efforts.add(effort)
            if model_name in model_efforts:
                model_efforts[model_name].update(efforts)
            else:
                model_efforts[model_name] = set(efforts)

        required = {
            "gpt-5.2": {"high"},
            "gpt-5.2-codex": {"medium", "high"},
        }
        missing: list[str] = []
        for model_name, efforts in required.items():
            available = model_efforts.get(model_name, set())
            if not efforts.issubset(available):
                missing.append(f"{model_name} (needs {sorted(efforts)})")

        if missing:
            raise AutopilotStopError(
                "STOP: app-server model list missing required models/efforts: " + ", ".join(missing)
            )

    def _preflight_config(self) -> None:
        try:
            response = self._client.request(
                "config/read",
                {"cwd": str(self._repo_root), "includeLayers": True},
            )
        except (AppServerRequestError, AppServerTimeoutError, AppServerError) as exc:
            raise AutopilotStopError(f"STOP: app-server config/read failed: {exc}") from exc

        self._write_json(self._config_path, response)

        config = response.get("config")
        if not isinstance(config, dict):
            raise AutopilotStopError("STOP: app-server config/read missing config payload.")

        approval_policy = config.get("approval_policy")
        sandbox_mode = config.get("sandbox_mode")
        if approval_policy != "on-request" or sandbox_mode != "workspace-write":
            raise AutopilotStopError(
                "STOP: app-server config does not match expected baseline: "
                f"approval_policy={approval_policy}, sandbox_mode={sandbox_mode}"
            )

    def _load_or_create_threads(self) -> dict[str, str]:
        if self._threads_path.exists():
            data_raw = json.loads(self._threads_path.read_text(encoding="utf-8"))
            if not isinstance(data_raw, dict):
                raise AutopilotStopError("STOP: appserver_threads.json is not a JSON object.")
            data = cast(dict[str, JsonValue], data_raw)
            threads: dict[str, str] = {}
            for role in [ROLE_PLANNING, ROLE_PLAN_REVIEW, ROLE_CODING, ROLE_VERIFY_REVIEW]:
                thread_id = data.get(role)
                if not isinstance(thread_id, str):
                    raise AutopilotStopError(
                        "STOP: appserver_threads.json missing thread id for "
                        f"{role} (RUN_ID={self._run_id})."
                    )
                threads[role] = thread_id
                self._resume_thread(role, thread_id)
            return threads

        threads: dict[str, str] = {}
        for role in [ROLE_PLANNING, ROLE_PLAN_REVIEW, ROLE_CODING, ROLE_VERIFY_REVIEW]:
            policy = ROLE_POLICY[role]
            params: JsonObject = {"cwd": str(self._repo_root), "model": policy.model}
            try:
                response = self._client.request("thread/start", params)
            except (AppServerRequestError, AppServerTimeoutError, AppServerError) as exc:
                raise AutopilotStopError(f"STOP: thread/start failed for {role}: {exc}") from exc

            thread = response.get("thread")
            if not isinstance(thread, dict):
                raise AutopilotStopError("STOP: thread/start response missing thread id.")
            thread_id_value = thread.get("id")
            if not isinstance(thread_id_value, str):
                raise AutopilotStopError("STOP: thread/start response missing thread id.")
            threads[role] = thread_id_value

        self._write_json(self._threads_path, threads)
        return threads

    def _resume_thread(self, role: str, thread_id: str) -> None:
        try:
            _ = self._client.request("thread/resume", {"threadId": thread_id})
        except (AppServerRequestError, AppServerTimeoutError, AppServerError) as exc:
            raise AutopilotStopError(
                f"STOP: thread/resume failed for {role} (RUN_ID={self._run_id}, "
                f"threadId={thread_id}): {exc}"
            ) from exc

    def _handle_notification(self, payload: JsonObject) -> None:
        method = payload.get("method")
        if not isinstance(method, str):
            return

        params = payload.get("params")
        thread_id: str | None = None
        turn_id: str | None = None
        if isinstance(params, dict):
            thread_id_value = params.get("threadId")
            thread_id = thread_id_value if isinstance(thread_id_value, str) else None
            turn_id_value = params.get("turnId")
            if isinstance(turn_id_value, str):
                turn_id = turn_id_value
            turn = params.get("turn")
            if isinstance(turn, dict):
                turn_inner_id = turn.get("id")
                if isinstance(turn_inner_id, str):
                    turn_id = turn_inner_id

        role = self._role_by_thread.get(thread_id or "", self._active_role or "unknown")

        if method == "thread/started" and thread_id:
            print(f"[app-server][{self._run_id}][{role}] thread started: {thread_id}")
            return

        if method == "turn/started" and turn_id:
            print(f"[app-server][{self._run_id}][{role}] turn started: {turn_id}")
            return

        if method == "turn/completed" and turn_id:
            status = None
            if isinstance(params, dict):
                turn = params.get("turn")
                if isinstance(turn, dict) and isinstance(turn.get("status"), str):
                    status = turn.get("status")
            status_text = status or "unknown"
            print(f"[app-server][{self._run_id}][{role}] turn completed: {turn_id} ({status_text})")
            return

        summary = _summarize_event(payload)
        if summary is not None:
            now = time.monotonic()
            if now - self._last_progress_ts >= 2.0 or summary != self._last_progress_label:
                self._last_progress_ts = now
                self._last_progress_label = summary
                print(f"[app-server][{self._run_id}][{role}] {summary}")

    def _handle_server_request(self, request: JsonObject) -> None:
        request_id = request.get("id")
        if not isinstance(request_id, int | str):
            raise AutopilotStopError(f"STOP: server request missing id: {request}")

        method = request.get("method")
        params = request.get("params")
        if not isinstance(method, str) or not isinstance(params, dict):
            raise AutopilotStopError(f"STOP: malformed server request: {request}")

        thread_id_value = params.get("threadId")
        thread_id = thread_id_value if isinstance(thread_id_value, str) else None
        role = self._role_by_thread.get(thread_id or "", "unknown")

        print(f"APPROVAL REQUIRED ({role} | {self._run_id})")
        summary = _format_approval_summary(method, params)
        if summary:
            print(summary)

        approved = _prompt_approval(timeout_s=300.0)
        decision = "accept" if approved else "decline"
        self._client.respond(request_id, {"decision": decision})

        if not approved:
            raise AutopilotStopError("STOP: approval declined.")

    def _write_json(self, path: Path, payload: Mapping[str, JsonValue]) -> None:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_codex_exec(repo_root: Path, profile: str, message: str) -> None:
    import subprocess

    subprocess.run(
        ["codex", "exec", "--profile", profile, "-C", str(repo_root), message],
        cwd=str(repo_root),
        check=True,
        text=True,
    )


def _prompt_approval(*, timeout_s: float) -> bool:
    """Prompt for approval with timeout. Returns True only for explicit 'y'."""
    print("APPROVE (y/N): ", end="", flush=True)
    if sys.stdin is None:
        return False
    try:
        ready, _, _ = select.select([sys.stdin], [], [], timeout_s)
    except (ValueError, OSError):
        return False
    if not ready:
        return False
    response = sys.stdin.readline()
    if response is None:
        return False
    return response.strip().lower() == "y"


def _format_approval_summary(method: str, params: Mapping[str, JsonValue]) -> str:
    lines: list[str] = [f"Method: {method}"]
    reason = params.get("reason")
    if isinstance(reason, str) and reason:
        lines.append(f"Reason: {reason}")

    if method == "item/commandExecution/requestApproval":
        command = params.get("command")
        cwd = params.get("cwd")
        if isinstance(command, str):
            lines.append(f"Command: {command}")
        if isinstance(cwd, str):
            lines.append(f"CWD: {cwd}")
    elif method == "item/fileChange/requestApproval":
        grant_root = params.get("grantRoot")
        if isinstance(grant_root, str):
            lines.append(f"Grant Root: {grant_root}")

    return "\n".join(lines)


def _summary_for_model(model: str) -> str | None:
    if model == "gpt-5.2-codex":
        return "detailed"
    return "concise"


def _summarize_event(payload: JsonObject) -> str | None:
    method = payload.get("method")
    if not isinstance(method, str):
        return None

    if method == "codex/event/exec_command_begin":
        cmd = _extract_exec_command(payload)
        if cmd:
            return f"exec: {cmd}"
        return "exec: command started"

    if method == "codex/event/exec_command_end":
        exit_code = _extract_exec_exit_code(payload)
        if exit_code is not None:
            return f"exec done (exit={exit_code})"
        return "exec done"

    if method == "turn/diff/updated":
        diff_path = _extract_diff_path(payload)
        if diff_path:
            return f"diff updated: {diff_path}"
        return "diff updated"

    if method == "item/agentMessage/delta":
        return "assistant message streaming"

    if method == "item/commandExecution/outputDelta":
        return "command output streaming"

    return None


def _extract_exec_command(payload: JsonObject) -> str | None:
    params = payload.get("params")
    if not isinstance(params, dict):
        return None
    msg = params.get("msg")
    if not isinstance(msg, dict):
        return None
    parsed_cmd = msg.get("parsed_cmd")
    if isinstance(parsed_cmd, list) and parsed_cmd:
        first = parsed_cmd[0]
        if isinstance(first, dict):
            cmd_type = first.get("type")
            path = first.get("path")
            if isinstance(cmd_type, str) and isinstance(path, str):
                return f"{cmd_type} {path}"
    command = msg.get("command")
    if isinstance(command, list) and command:
        return " ".join(str(part) for part in command)
    if isinstance(command, str):
        return command
    return None


def _extract_exec_exit_code(payload: JsonObject) -> int | None:
    params = payload.get("params")
    if not isinstance(params, dict):
        return None
    msg = params.get("msg")
    if not isinstance(msg, dict):
        return None
    exit_code = msg.get("exit_code")
    return exit_code if isinstance(exit_code, int) else None


def _extract_diff_path(payload: JsonObject) -> str | None:
    params = payload.get("params")
    if not isinstance(params, dict):
        return None
    diff = params.get("diff")
    if not isinstance(diff, str):
        return None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            return line.removeprefix("+++ b/").strip()
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4 and parts[3].startswith("b/"):
                return parts[3].removeprefix("b/")
    return None
