"""Validated process execution helpers."""

from __future__ import annotations

import os
import signal
import site
import subprocess
import sys
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager, nullcontext, suppress
from dataclasses import dataclass, field
from pathlib import Path
from shutil import which
from subprocess import DEVNULL, PIPE, CompletedProcess, Popen, SubprocessError, TimeoutExpired
from threading import current_thread, main_thread
from time import monotonic, sleep
from types import FrameType
from typing import Literal

from frame_compare.utils.child_environment import (
    child_environment,
    diagnostic_secrets,
    sanitize_diagnostic,
)

PROBE_STDOUT_BYTES = 256 * 1024
PROBE_STDERR_BYTES = 64 * 1024
_DIAGNOSTIC_EDGE_BYTES = 4096
_READ_BYTES = 64 * 1024
_POLL_SECONDS = 0.005
_CREATE_SUSPENDED = 0x00000004

_MEDIA_EXECUTABLE_ENV = {
    "ffmpeg": "FRAME_COMPARE_FFMPEG_EXECUTABLE",
    "ffprobe": "FRAME_COMPARE_FFPROBE_EXECUTABLE",
}
_PYTHON_INJECTION_ENV_KEYS = (
    "PYTHONHOME",
    "PYTHONINSPECT",
    "PYTHONPATH",
    "PYTHONSTARTUP",
    "PYTHONNOUSERSITE",
)


def _is_executable_file(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def _resolve_cwd(cwd: Path | None) -> Path | None:
    if cwd is None:
        return None
    resolved = cwd.resolve(strict=True)
    if not resolved.is_dir():
        raise NotADirectoryError(str(cwd))
    return resolved


def _media_override_name(executable: str) -> str | None:
    executable_name = Path(executable).name.casefold()
    if executable_name.endswith(".exe"):
        executable_name = executable_name[:-4]
    return _MEDIA_EXECUTABLE_ENV.get(executable_name)


def resolve_optional_executable(executable: str, cwd: Path | None = None) -> str | None:
    """Resolve an optional tool, while rejecting invalid configured media overrides."""
    override_name = _media_override_name(executable)
    if override_name is not None and override_name in os.environ:
        return resolve_executable(executable, cwd)
    try:
        return resolve_executable(executable, cwd)
    except FileNotFoundError:
        return None


def resolve_executable(executable: str, cwd: Path | None = None) -> str:
    """Resolve an executable, honoring fail-closed bundled media overrides.

    The Windows portable launcher sets absolute FFmpeg/ffprobe paths rather than
    adding the standalone FFmpeg DLL directory to ``PATH``. This prevents native
    VapourSynth plugins from accidentally resolving FFmpeg libraries from the
    standalone command-line distribution.
    """
    if not executable:
        raise ValueError("argv[0] must be a non-empty executable name")

    override_name = _media_override_name(executable)
    if override_name is not None and (override := os.environ.get(override_name)) is not None:
        override_path = Path(override)
        if not override_path.is_absolute() or not _is_executable_file(override_path):
            raise FileNotFoundError(override or f"{override_name} is empty")
        return str(override_path)

    executable_path = Path(executable)
    if executable_path.is_absolute():
        if not _is_executable_file(executable_path):
            raise FileNotFoundError(executable)
        return str(executable_path)

    if executable_path.parent != Path():
        base_dir = cwd if cwd is not None else Path.cwd()
        candidate = (base_dir / executable_path).resolve(strict=True)
        if not _is_executable_file(candidate):
            raise FileNotFoundError(executable)
        return str(candidate)

    resolved = which(executable)
    if resolved is None:
        raise FileNotFoundError(executable)
    return resolved


def _normalize_argv(argv: Sequence[str], cwd: Path | None) -> list[str]:
    if not argv:
        raise ValueError("argv must contain at least one element")

    normalized = [str(part) for part in argv]
    normalized[0] = resolve_executable(normalized[0], cwd)
    return normalized


def prepare_python_child(
    argv: Sequence[str],
    *,
    env: dict[str, str] | None = None,
) -> tuple[list[str], dict[str, str]]:
    """Prepare a child Python command with the parent's trusted import policy.

    Safe-path mode excludes the working and script directories from imports.
    Caller-controlled Python injection variables are removed, while an enabled
    parent user site and its ``PYTHONUSERBASE`` remain available to the child.
    When the parent has user-site imports disabled, ``-s`` keeps the child from
    discovering a user site of its own.
    """
    if not argv:
        raise ValueError("argv must contain at least one element")

    child_env = child_environment(env)
    for key in _PYTHON_INJECTION_ENV_KEYS:
        child_env.pop(key, None)

    user_site_enabled = site.ENABLE_USER_SITE and not sys.flags.no_user_site
    python_flags = ["-P"]
    if user_site_enabled:
        if env is not None and "PYTHONUSERBASE" in env:
            child_env["PYTHONUSERBASE"] = env["PYTHONUSERBASE"]
    else:
        child_env.pop("PYTHONUSERBASE", None)
        python_flags.append("-s")

    child_env["PYTHONSAFEPATH"] = "1"
    return [str(argv[0]), *python_flags, *(str(part) for part in argv[1:])], child_env


type OutputStream = Literal["stdout", "stderr"]


class SubprocessAborted(Exception):
    """The owner stopped a process; incomplete output is not a successful result."""


class SubprocessOutputLimitExceeded(SubprocessError):
    """A child emitted more than the caller's byte budget for one stream."""

    def __init__(
        self,
        stream: OutputStream,
        limit: int,
        observed: int,
        diagnostics: bytes,
    ) -> None:
        self.stream = stream
        self.limit = limit
        self.observed = observed  # Bytes read so far, a lower bound on total emitted.
        self.truncated = True
        self.diagnostics = diagnostics
        super().__init__(f"Child {stream} exceeded its {limit:,}-byte limit")


class SubprocessCleanupError(Exception):
    """The child could not be reaped after escalation."""


@dataclass(slots=True)
class OutputBudget:
    """Count raw bytes and retain only small diagnostic edges, even when streaming."""

    stream: OutputStream
    limit: int
    secrets: tuple[str, ...] = field(default_factory=diagnostic_secrets)
    observed: int = field(init=False, default=0)
    _head: bytearray = field(init=False, default_factory=bytearray)
    _tail: bytearray = field(init=False, default_factory=bytearray)

    def consume(self, chunk: bytes) -> None:
        self.observed += len(chunk)
        head_remaining = _DIAGNOSTIC_EDGE_BYTES - len(self._head)
        self._head.extend(chunk[:head_remaining])
        tail_start = max(head_remaining, len(chunk) - _DIAGNOSTIC_EDGE_BYTES)
        self._tail.extend(chunk[tail_start:])
        del self._tail[:-_DIAGNOSTIC_EDGE_BYTES]
        if self.observed > self.limit:
            raise SubprocessOutputLimitExceeded(
                self.stream, self.limit, self.observed, self.diagnostics()
            )

    def diagnostics(self) -> bytes:
        if self.observed == len(self._head) + len(self._tail):
            return sanitize_diagnostic(bytes(self._head + self._tail), self.secrets)[
                : 2 * _DIAGNOSTIC_EDGE_BYTES
            ]
        head = sanitize_diagnostic(bytes(self._head), self.secrets)[:_DIAGNOSTIC_EDGE_BYTES]
        tail = sanitize_diagnostic(bytes(self._tail), self.secrets)[-_DIAGNOSTIC_EDGE_BYTES:]
        return head + b"\n[...output truncated...]\n" + tail

    @property
    def truncated(self) -> bool:
        return self.observed > len(self._head) + len(self._tail)


class _WindowsJob:
    """Own a Windows process tree even after its original leader exits."""

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        class _BasicLimitInformation(ctypes.Structure):
            _fields_ = [
                ("per_process_user_time_limit", ctypes.c_longlong),
                ("per_job_user_time_limit", ctypes.c_longlong),
                ("limit_flags", wintypes.DWORD),
                ("minimum_working_set_size", ctypes.c_size_t),
                ("maximum_working_set_size", ctypes.c_size_t),
                ("active_process_limit", wintypes.DWORD),
                ("affinity", ctypes.c_size_t),
                ("priority_class", wintypes.DWORD),
                ("scheduling_class", wintypes.DWORD),
            ]

        class _IoCounters(ctypes.Structure):
            _fields_ = [
                ("read_operation_count", ctypes.c_ulonglong),
                ("write_operation_count", ctypes.c_ulonglong),
                ("other_operation_count", ctypes.c_ulonglong),
                ("read_transfer_count", ctypes.c_ulonglong),
                ("write_transfer_count", ctypes.c_ulonglong),
                ("other_transfer_count", ctypes.c_ulonglong),
            ]

        class _ExtendedLimitInformation(ctypes.Structure):
            _fields_ = [
                ("basic_limit_information", _BasicLimitInformation),
                ("io_info", _IoCounters),
                ("process_memory_limit", ctypes.c_size_t),
                ("job_memory_limit", ctypes.c_size_t),
                ("peak_process_memory_used", ctypes.c_size_t),
                ("peak_job_memory_used", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self._kernel32 = kernel32
        self._handle = handle
        try:
            limits = _ExtendedLimitInformation()
            limits.basic_limit_information.limit_flags = 0x00002000  # KILL_ON_JOB_CLOSE
            if not kernel32.SetInformationJobObject(
                handle,
                9,
                ctypes.byref(limits),
                ctypes.sizeof(limits),  # ExtendedLimitInformation
            ):
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException:
            kernel32.CloseHandle(handle)
            self._handle = None
            raise

    def assign_and_resume(self, pid: int) -> None:
        import ctypes

        kernel32 = self._kernel32
        # AssignProcessToJobObject needs PROCESS_TERMINATE | PROCESS_SET_QUOTA.
        process_handle = kernel32.OpenProcess(0x0001 | 0x0100, False, pid)
        if not process_handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not kernel32.AssignProcessToJobObject(self._handle, process_handle):
                raise ctypes.WinError(ctypes.get_last_error())
            self._resume_primary_thread(pid)
        finally:
            kernel32.CloseHandle(process_handle)

    def _resume_primary_thread(self, pid: int) -> None:
        import ctypes
        from ctypes import wintypes

        class _ThreadEntry(ctypes.Structure):
            _fields_ = [
                ("size", wintypes.DWORD),
                ("usage", wintypes.DWORD),
                ("thread_id", wintypes.DWORD),
                ("owner_pid", wintypes.DWORD),
                ("base_priority", wintypes.LONG),
                ("delta_priority", wintypes.LONG),
                ("flags", wintypes.DWORD),
            ]

        kernel32 = self._kernel32
        kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel32.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ThreadEntry)]
        kernel32.Thread32First.restype = wintypes.BOOL
        kernel32.Thread32Next.argtypes = kernel32.Thread32First.argtypes
        kernel32.Thread32Next.restype = wintypes.BOOL
        kernel32.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenThread.restype = wintypes.HANDLE
        kernel32.GetProcessIdOfThread.argtypes = [wintypes.HANDLE]
        kernel32.GetProcessIdOfThread.restype = wintypes.DWORD
        kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
        kernel32.ResumeThread.restype = wintypes.DWORD

        # Popen closes the primary thread handle. A CREATE_SUSPENDED child
        # has one thread, which we reopen with the documented Toolhelp API.
        snapshot = kernel32.CreateToolhelp32Snapshot(0x00000004, 0)  # TH32CS_SNAPTHREAD
        if snapshot == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            entry = _ThreadEntry()
            entry.size = ctypes.sizeof(entry)
            found = kernel32.Thread32First(snapshot, ctypes.byref(entry))
            thread_id = None
            while found:
                if entry.owner_pid == pid:
                    if thread_id is not None:
                        raise OSError("Suspended child has multiple threads")
                    thread_id = entry.thread_id
                entry.size = ctypes.sizeof(entry)
                found = kernel32.Thread32Next(snapshot, ctypes.byref(entry))
            if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel32.CloseHandle(snapshot)
        if thread_id is None:
            raise OSError("Could not locate the suspended child's primary thread")

        # THREAD_SUSPEND_RESUME | THREAD_QUERY_LIMITED_INFORMATION
        thread = kernel32.OpenThread(0x0002 | 0x0800, False, thread_id)
        if not thread:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if kernel32.GetProcessIdOfThread(thread) != pid:
                raise OSError("Suspended child's primary thread changed")
            previous_count = kernel32.ResumeThread(thread)
            if previous_count == 0xFFFFFFFF:
                raise ctypes.WinError(ctypes.get_last_error())
            if previous_count != 1:
                raise OSError("Unexpected suspend count for child process")
        finally:
            kernel32.CloseHandle(thread)

    def close(self) -> None:
        if self._handle is None:
            return
        if not self._kernel32.CloseHandle(self._handle):
            import ctypes

            raise ctypes.WinError(ctypes.get_last_error())
        self._handle = None


class OwnedProcessTree:
    """Retain cross-platform ownership of a child's complete process tree."""

    def __init__(self, windows_job: _WindowsJob | None) -> None:
        self._windows_job = windows_job

    def close_windows_job(self) -> None:
        """Stop remaining Windows descendants before waiting for their pipes."""
        if self._windows_job is not None:
            self._windows_job.close()

    def signal(self, process: Popen[bytes], *, force: bool) -> None:
        signal_child_tree(process, force=force, windows_job=self._windows_job)

    def reap(self, process: Popen[bytes]) -> None:
        try:
            reap_stopped_process(process, self._windows_job)
        finally:
            with suppress(OSError):
                self.close_windows_job()


@contextmanager
def _defer_windows_spawn_sigint() -> Generator[None]:
    # A Python SIGINT in Popen could unwind after CreateProcess but before the
    # suspended PID reaches its owner. Replay the caller's handler once owned.
    previous = signal.getsignal(signal.SIGINT)
    if current_thread() is not main_thread() or not callable(previous):
        yield
        return

    pending: list[tuple[int, FrameType | None]] = []

    def defer(signum: int, frame: FrameType | None) -> None:
        pending.append((signum, frame))

    try:
        signal.signal(signal.SIGINT, defer)
        yield
    finally:
        signal.signal(signal.SIGINT, previous)
        for signum, frame in pending:
            previous(signum, frame)


def spawn_owned_process(
    command: Sequence[str],
    *,
    env: Mapping[str, str],
    cwd: Path | None = None,
    capture_output: bool = False,
) -> tuple[Popen[bytes], OwnedProcessTree]:
    """Start an already resolved command inside its owned process tree."""
    windows_job = None
    process = None
    windows = sys.platform == "win32"
    try:
        with _defer_windows_spawn_sigint() if windows else nullcontext():
            if windows:
                windows_job = _WindowsJob()
            process = subprocess.Popen(  # nosec B603
                command,
                cwd=cwd,
                env=env,
                stdin=DEVNULL if capture_output else None,
                stdout=PIPE if capture_output else None,
                stderr=PIPE if capture_output else None,
                bufsize=0,
                shell=False,
                close_fds=True,
                start_new_session=not windows,
                creationflags=_CREATE_SUSPENDED if windows else 0,
            )
        if windows_job is not None:
            windows_job.assign_and_resume(process.pid)
        return process, OwnedProcessTree(windows_job)
    except BaseException:
        if windows_job is not None:
            with suppress(BaseException):
                windows_job.close()
        if process is not None:
            # Assignment may have failed before the job owned the suspended
            # child. Explicitly terminate it and release both pipe endpoints.
            try:
                reap_stopped_process(process)
            finally:
                for stream in (process.stdout, process.stderr):
                    if stream is not None:
                        with suppress(BaseException):
                            stream.close()
        raise


def signal_child_tree(
    process: Popen[bytes] | Popen[str], *, force: bool, windows_job: _WindowsJob | None = None
) -> None:
    """Signal an owned process group or close its kill-on-close job."""
    if sys.platform == "win32":
        if windows_job is not None:
            windows_job.close()
        elif process.poll() is None:
            process.kill() if force else process.terminate()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL if force else signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError:
            # Some POSIX hosts deny signals to an exiting process group.
            if process.poll() is None:
                process.kill() if force else process.terminate()


def reap_stopped_process(
    process: Popen[bytes] | Popen[str], windows_job: _WindowsJob | None = None
) -> None:
    """Stop the owned tree and report failure to reap the child."""
    # Kill the group even if its leader already exited and left writers behind.
    try:
        signal_child_tree(process, force=True, windows_job=windows_job)
    except BaseException:
        with suppress(BaseException):
            process.kill()
    try:
        process.wait(timeout=1.0)
        return
    except BaseException:
        pass
    with suppress(BaseException):
        process.kill()
    try:
        process.wait(timeout=2.0)
    except BaseException as exc:
        raise SubprocessCleanupError("could not reap child after killing it") from exc


def run_subprocess(
    argv: Sequence[str],
    *,
    timeout_seconds: float | None = None,
    cwd: Path | None = None,
    check: bool = True,
    abort: Callable[[], bool] | None = None,
    stdout_consumer: Callable[[bytes], None] | None = None,
    max_stdout_bytes: int | None = None,
    max_stderr_bytes: int = PROBE_STDERR_BYTES,
    env: Mapping[str, str] | None = None,
) -> CompletedProcess[bytes]:
    """Run a child with independently capped stdout/stderr and owned cleanup.

    Stdout remains byte-exact on success. Streamed stdout must supply its own
    byte budget and is never assembled in memory. Failure output is diagnostic
    only, bounded to sanitized head/tail excerpts.
    """
    if stdout_consumer is not None and max_stdout_bytes is None:
        raise ValueError("stdout_consumer and max_stdout_bytes must be supplied together")
    if max_stdout_bytes is None:
        max_stdout_bytes = PROBE_STDOUT_BYTES
    if any(type(limit) is not int or limit < 0 for limit in (max_stdout_bytes, max_stderr_bytes)):
        raise ValueError("output limits must be nonnegative byte counts")
    if abort is not None and abort():
        raise SubprocessAborted()

    resolved_cwd = _resolve_cwd(cwd)
    command = _normalize_argv(argv, resolved_cwd)
    secrets = diagnostic_secrets(env)
    stdout_budget = OutputBudget("stdout", max_stdout_bytes, secrets)
    stderr_budget = OutputBudget("stderr", max_stderr_bytes, secrets)
    deadline = None if timeout_seconds is None else monotonic() + timeout_seconds
    stdout, stderr = bytearray(), bytearray()
    process, process_tree = spawn_owned_process(
        command,
        cwd=resolved_cwd,
        env=child_environment(env),
        capture_output=True,
    )
    descendants_stopped = False
    try:
        assert process.stdout is not None and process.stderr is not None
        readers = {
            process.stdout.fileno(): (stdout_budget, stdout, stdout_consumer),
            process.stderr.fileno(): (stderr_budget, stderr, None),
        }
        # Python 3.13 supports nonblocking anonymous pipes on Windows too.
        # A single owner means there are no reader threads to strand on EOF.
        for fd in readers:
            os.set_blocking(fd, False)
        while readers or process.poll() is None:
            returncode = process.poll()
            if returncode is not None and not descendants_stopped:
                if sys.platform == "win32":
                    process_tree.close_windows_job()
                else:
                    process_tree.signal(process, force=True)
                descendants_stopped = True
            # Keep a known child failure so the caller can distinguish a signal
            # exit from an unrelated failure racing with cancellation.
            if returncode in (None, 0) and abort is not None and abort():
                raise SubprocessAborted()
            remaining = None if deadline is None else deadline - monotonic()
            if remaining is not None and remaining <= 0:
                assert timeout_seconds is not None
                raise TimeoutExpired(
                    _diagnostic_command(command, secrets),
                    timeout_seconds,
                    output=stdout_budget.diagnostics(),
                    stderr=stderr_budget.diagnostics(),
                )
            progressed = False
            for fd, (budget, data, consume) in tuple(readers.items()):
                try:
                    chunk = os.read(fd, min(_READ_BYTES, budget.limit - budget.observed + 1))
                except BlockingIOError:
                    continue
                if not chunk:
                    del readers[fd]
                    continue
                progressed = True
                budget.consume(chunk)
                if consume is None:
                    data.extend(chunk)
                else:
                    consume(chunk)
            if not progressed:
                sleep(_POLL_SECONDS if remaining is None else min(_POLL_SECONDS, remaining))
    finally:
        try:
            process_tree.reap(process)
        finally:
            try:
                if process.stdout is not None:
                    process.stdout.close()
            finally:
                if process.stderr is not None:
                    process.stderr.close()

    assert process.returncode is not None
    if process.returncode:
        result = CompletedProcess(
            _diagnostic_command(command, secrets),
            process.returncode,
            stdout_budget.diagnostics(),
            stderr_budget.diagnostics(),
        )
    else:
        result = CompletedProcess(
            command,
            process.returncode,
            bytes(stdout),
            sanitize_diagnostic(bytes(stderr), secrets)[:max_stderr_bytes],
        )
    if check:
        result.check_returncode()
    return result


def _diagnostic_command(command: list[str], secrets: tuple[str, ...]) -> list[str]:
    return [
        sanitize_diagnostic(part.encode("utf-8", errors="replace"), secrets).decode()
        for part in command
    ]
