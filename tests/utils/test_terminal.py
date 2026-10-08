import os

import pytest

from frame_compare.utils.terminal import no_color_requested, stream_is_tty


class _BrokenTTY:
    def isatty(self) -> bool:
        raise ValueError("closed stream")


class _InteractiveTTY:
    def isatty(self) -> bool:
        return True


def test_no_color_requested_respects_explicit_flag_and_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert no_color_requested(explicit_no_color=True) is True
    monkeypatch.setenv("NO_COLOR", "")
    assert no_color_requested() is True
    monkeypatch.delenv("NO_COLOR")
    assert no_color_requested() is False


def test_stream_is_tty_handles_missing_and_broken_streams() -> None:
    assert stream_is_tty(object()) is False
    assert stream_is_tty(_BrokenTTY()) is False
    assert stream_is_tty(_InteractiveTTY()) is True


@pytest.mark.skipif(os.name != "posix", reason="Real PTY signal proof requires a POSIX host")
@pytest.mark.parametrize("prompt", ["reuse", "retry", "upload"])
def test_first_sigint_interrupts_real_pty_prompt_and_restores_runner(prompt: str) -> None:
    import json
    import pty
    import selectors
    import signal
    import subprocess
    import sys

    code = """
import asyncio, json, signal, sys
from pathlib import Path
from dataclasses import replace
import typer
from rich.console import Console
from frame_compare.cli.run_command import (
    build_confirm_full_window_retry_callback, build_confirm_slowpics_upload_callback,
    confirm_full_window_retry_on_stderr,
)
from frame_compare.config.schema import ConfigSchema, Visibility
from frame_compare.services.alignment_reuse_prompt import _read_reuse_response
from frame_compare.orchestration.types import (
    FullWindowRetryConfirmationRequest, SlowpicsUploadConfirmationRequest,
)
from tests.cli.run_command_test_support import base_args, deps, DepsOptions
class Input:
    def __getattr__(self, name):
        return getattr(original_input, name)
    def readline(self, *args):
        print("READY", flush=True)
        return original_input.readline(*args)
original_input = sys.stdin
sys.stdin = Input()
observed = {}
async def main():
    saved = signal.getsignal(signal.SIGINT)
    try:
        if sys.argv[1] == "reuse":
            _read_reuse_response(no_color=True)
        elif sys.argv[1] == "retry":
            callback = build_confirm_full_window_retry_callback(deps=deps(DepsOptions(
                confirm_full_window_retry=confirm_full_window_retry_on_stderr,
            )))
            callback(FullWindowRetryConfirmationRequest(requested_frame_count=1, eligible_frame_count=0, ignore_lead_seconds=1.0, ignore_trail_seconds=1.0))
        else:
            callback = build_confirm_slowpics_upload_callback(
                args=base_args(), deps=deps(DepsOptions(confirm_upload=typer.confirm)),
                console=Console(stderr=True), resolve_effective_config=ConfigSchema,
                visibility=Visibility.PUBLIC,
            )
            callback(SlowpicsUploadConfirmationRequest(report_path=Path("report.html")))
        observed["answered"] = True
    except BaseException:
        await asyncio.sleep(0)
        raise
    finally:
        observed["restored"] = signal.getsignal(signal.SIGINT) is saved
        observed["count"] = asyncio.current_task().cancelling()
try:
    asyncio.run(main())
except KeyboardInterrupt:
    print(json.dumps(observed), flush=True)
    raise SystemExit(130)
"""
    master, slave = pty.openpty()
    process = subprocess.Popen(  # noqa: S603 - explicit test interpreter and argv
        [sys.executable, "-c", code, prompt],
        stdin=slave,
        stderr=slave,
        stdout=subprocess.PIPE,
        text=True,
    )
    os.close(slave)
    try:
        assert process.stdout is not None
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(timeout=3), "prompt did not start"
        assert process.stdout.readline().strip().endswith("READY")
        os.kill(process.pid, signal.SIGINT)
        stdout, _ = process.communicate(timeout=3)
        assert process.returncode == 130, stdout
        observed = json.loads(stdout)
        assert observed == {"restored": True, "count": 1}
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=3)
        if process.stdout is not None:
            process.stdout.close()
        os.close(master)


def test_interruptible_prompt_leaves_foreign_handler_and_eof_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio
    import signal
    import sys

    from typer import Abort

    from frame_compare.utils.terminal import interruptible_prompt

    monkeypatch.setattr(sys, "stdin", _InteractiveTTY())
    original = signal.getsignal(signal.SIGINT)
    saved = original

    async def verify() -> None:
        # asyncio.run does not take over a foreign handler.
        assert signal.getsignal(signal.SIGINT) is saved
        with pytest.raises(Abort), interruptible_prompt():
            raise Abort() from EOFError()
        assert signal.getsignal(signal.SIGINT) is saved
        task = asyncio.current_task()
        assert task is not None
        assert task.cancelling() == 0

    def foreign(_signal: int, _frame: object) -> None:
        raise AssertionError("foreign handler invoked")

    signal.signal(signal.SIGINT, foreign)
    try:
        saved = foreign
        asyncio.run(verify())
    finally:
        signal.signal(signal.SIGINT, original)


@pytest.mark.parametrize("outcome", ["answer", "eof", "error"])
def test_runner_prompt_restores_handler_without_counting_non_interrupts(
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
) -> None:
    import asyncio
    import signal
    import sys

    from typer import Abort

    from frame_compare.utils.terminal import interruptible_prompt

    monkeypatch.setattr(sys, "stdin", _InteractiveTTY())
    original = signal.getsignal(signal.SIGINT)

    async def verify() -> None:
        saved = signal.getsignal(signal.SIGINT)
        try:
            with interruptible_prompt():
                if outcome == "eof":
                    raise Abort() from EOFError()
                if outcome == "error":
                    raise ValueError("read failed")
        except (Abort, ValueError):
            assert outcome != "answer"
        finally:
            assert signal.getsignal(signal.SIGINT) is saved
        task = asyncio.current_task()
        assert task is not None
        assert task.cancelling() == 0

    signal.signal(signal.SIGINT, signal.default_int_handler)
    try:
        asyncio.run(verify())
    finally:
        signal.signal(signal.SIGINT, original)


@pytest.mark.parametrize("when", ["before", "during"])
def test_prompt_pending_interrupt_never_becomes_an_answer(
    monkeypatch: pytest.MonkeyPatch,
    when: str,
) -> None:
    import asyncio
    import signal
    import sys

    from frame_compare.utils.cancellation import _RunInterrupt, cancellation_checkpoint
    from frame_compare.utils.terminal import interruptible_prompt

    monkeypatch.setattr(sys, "stdin", _InteractiveTTY())
    read: list[bool] = []
    answered: list[bool] = []

    async def verify() -> None:
        task = asyncio.current_task()
        assert task is not None
        saved = signal.getsignal(signal.SIGINT)
        if when == "before":
            task.cancel()
        with pytest.raises(_RunInterrupt):
            with interruptible_prompt():
                read.append(True)
                task.cancel()
            answered.append(True)
        assert signal.getsignal(signal.SIGINT) is saved
        await cancellation_checkpoint()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(verify())
    assert read == ([] if when == "before" else [True])
    assert answered == []
