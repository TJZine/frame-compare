"""Installed VSView workspace proof; offscreen native integration, not desktop acceptance."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_NATIVE_WORKSPACE = r"""
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"
import json, subprocess, time, sys, traceback
from pathlib import Path


def abort_native(kind, error, trace):
    # A failed assertion can leave a deliberately held native task. End only
    # this owned child instead of hanging in Qt's interpreter shutdown.
    traceback.print_exception(kind, error, trace)
    sys.stderr.flush()
    os._exit(1)


sys.excepthook = abort_native

root = Path(sys.argv[1]).resolve()
from PySide6.QtWidgets import QApplication
from vsengine.loops import set_loop
from vsview.vsenv import QtEventLoop

app = QApplication([])
set_loop(QtEventLoop(app))
from vsview.vsenv import get_policy

get_policy()
from vsview.app.settings import SettingsManager

SettingsManager(noop=True)
from vsview.app.plugins.manager import PluginManager

PluginManager.load()


def until(predicate, seconds=25):
    end = time.monotonic() + seconds
    while not predicate():
        if time.monotonic() > end:
            raise AssertionError("timeout")
        app.processEvents()
        time.sleep(0.01)


until(lambda: PluginManager.loaded)
from frame_compare.vsview.session_script import write_vsview_session_script

paths = [root / f"{n}.mkv" for n in ("ref", "a", "b")]
for p in paths:
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=160x90:rate=24:duration=2",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-colorspace",
            "bt709",
            "-c:v",
            "ffv1",
            str(p),
        ],
        check=True,
        timeout=30,
    )
audio = {
    f"ref:{n}": json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "not_computed",
            "audio_attempt": None,
        }
    )
    for n in ("a", "b")
}
script = write_vsview_session_script(
    reference=paths[0],
    comparisons=paths[1:],
    suggested_offsets_by_key={"ref:a": None, "ref:b": None},
    audio_review_by_key=audio,
    # Tiny FFV1 sources may lack decoder primaries/transfer. Exercise the same
    # explicit missing-metadata SDR defaults used by generated review sessions.
    frame_props_by_stem={path.stem: {} for path in paths},
    cache_dir=root,
)
from vsview.app.workspace import PythonScriptWorkspace

global_before = SettingsManager.global_settings.model_dump_json()
w = PythonScriptWorkspace()
render_errors = []
w.playback.loadFailed.connect(lambda: render_errors.append(True))
f = w.load_content(script)
until(f.done)
print("load", f.result(), flush=True)
assert f.result() == 0
until(lambda: w.playback.can_reload and not w.tab_manager.disable_switch)
from frame_compare.vsview.alignment_review_panel import AlignmentReviewPanel

panel = next(p for p in w.plugins if isinstance(p, AlignmentReviewPanel))
print("panel", panel.progress_label.text(), panel.guidance_label.text(), flush=True)
assert panel._positions is not None
assert w.tab_manager.sync_playhead_btn.state == 0

until(lambda: panel.use_positions_button.isEnabled())
result_path = script.with_name(script.stem + ".alignment-result.json")
assert not result_path.exists()
assert not panel.isVisible()  # Panel has never been opened.


def frames():
    return tuple(d.frame for d in panel._source_drafts)


def idle():
    return panel._positions is not None and panel._positions.snapshot() is not None


def switch(index):
    w.tab_manager.tabs.setCurrentIndex(index)
    until(idle)
    assert w.outputs_manager.current_voutput.vs_index == index


def seek(n):
    w.playback.seek_to_frame_coalesced(n)
    until(lambda: idle() and w.playback.state.current_frame == n)
    if not panel._saved:
        until(
            lambda: all(
                not d.following or d.frame == panel._positions.snapshot()[i]
                for i, d in enumerate(panel._source_drafts)
            )
        )


# Independent output positions, all while the panel has never been shown.
seek(20)
switch(1)
assert w.playback.state.current_frame == 0
seek(8)
switch(2)
seek(25)
assert frames() == (20, 8, 25), frames()
switch(0)
assert w.playback.state.current_frame == 20
# Hold a real frame bundle after the installed playback worker pops it. Pause
# clears its flags and invalidates its buffer, but cannot retract the popped
# future: that worker still commits when the held native frame is delivered.
from collections import deque
from concurrent.futures import Future
from threading import Event
from PySide6.QtCore import QThreadPool
from vsview.app.outputs.buffer import FrameBuffer, FrameBundle

output = w.outputs_manager.current_voutput
with w.env.use():
    delayed_frame = output.prepared_clip.get_frame(21)
held = Future()
buffer = FrameBuffer(output, w.env)
buffer._bundles = deque([FrameBundle(21, held, {})])
w.playback.state.buffer = buffer
w.playback.state.is_playing = True
play_task = w.playback._play_next_frame()
until(lambda: not buffer._bundles)
assert play_task.running() and not held.done()
w.playback.stop()
assert not w.playback.state.is_playing
assert w.playback.can_reload and not w.playback.has_pending_frame
assert not w.playback._timeline_rendering and not w.tab_manager.disable_switch
assert output.last_frame == 20
try:
    assert panel._positions.snapshot() is None, "paused in-flight frame was accepted"
    panel._save_positions()
    assert not result_path.exists()
finally:
    held.set_result(delayed_frame)
    until(play_task.done)
assert play_task.result() is None
until(idle)
assert output.last_frame == w.playback.state.current_frame == 21
assert not w.playback.state.is_playing
seek(20)

# Also cover a playback task queued before its named-task wrapper starts. A
# separate held job occupies the only pool thread; no production hook is changed.
pool = QThreadPool.globalInstance()
maximum = pool.maxThreadCount()
release = Event()
pool.setMaxThreadCount(1)
try:
    blocker = w.loop.to_thread_named("ReviewPauseBarrier", release.wait, 10)
    until(blocker.running)
    w.playback.state.is_playing = True
    queued = w.playback._play_next_frame()
    assert not queued.running() and not queued.done()
    w.playback.stop()
    assert not w.playback.state.is_playing
    assert panel._positions.snapshot() is None, "queued playback task was accepted"
    panel._save_positions()
    assert not result_path.exists()
finally:
    release.set()
    pool.setMaxThreadCount(maximum)
until(queued.done)
assert queued.result() is None
until(idle)
print("PAUSE_DRAIN_OK held-native-frame queued-task no-early-sidecar")

# Queued/active rendering is blocked even after the pending queue is cleared.
w.playback.seek_to_frame_coalesced(21)
assert w.playback._timeline_rendering and not w.playback.has_pending_frame
assert panel._positions.snapshot() is None
panel._save_positions()
assert not result_path.exists()
w.playback.seek_to_frame_coalesced(22)
w.playback.seek_to_frame_coalesced(23)
until(lambda: idle() and w.playback.state.current_frame == 23)
until(lambda: frames() == (23, 8, 25))
# Reopen then select a different tool, browse, and reopen without stale values.
w.show()
w.plugin_splitter.toggle_right_panel(True)
index = w.plugin_splitter.plugin_tabs.indexOf(panel)
w.plugin_splitter.plugin_tabs.setCurrentIndex(index)
app.processEvents()
assert panel.isVisible()
w.plugin_splitter.toggle_right_panel(False)
switch(1)
seek(0)
assert frames() == (23, 0, 25)
w.plugin_splitter.toggle_right_panel(True)
other = next(i for i in range(w.plugin_splitter.plugin_tabs.count()) if i != index)
w.plugin_splitter.plugin_tabs.setCurrentIndex(other)
assert not panel.isVisible()
switch(2)
seek(7)
w.plugin_splitter.plugin_tabs.setCurrentIndex(index)
until(lambda: frames() == (23, 0, 7))
assert [f.text() for f in panel.frame_inputs] == ["23", "0", "7"]
# Exercise the actual workspace shortcut context, including adjacent controls.
from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy, QTest


def space(control):
    if panel.body_widget.isAncestorOf(control):
        panel.body_scroll.ensureWidgetVisible(control)
    control.setFocus()
    app.processEvents()
    assert app.focusWidget() is control
    activated = QSignalSpy(control.clicked if hasattr(control, "clicked") else control.toggled)
    QTest.keyClick(control, Qt.Key.Key_Space)
    app.processEvents()
    assert activated.count() == 1, "panel control did not activate exactly once"
    assert not w.playback.state.is_playing, "panel activation started playback"


space(panel.manual_toggle)
assert panel.manual_toggle.isChecked() and panel.manual_group.isVisible()
for details in panel.audio_detail_groups:
    space(details)
    assert details.isChecked()
    space(details)
    assert not details.isChecked()
# Space outside panel controls still belongs to the viewer.
panel.progress_label.setFocus()
QTest.keyClick(panel.progress_label, Qt.Key.Key_Space)
app.processEvents()
assert w.playback.state.is_playing
w.playback.stop()
until(idle)
seek(7)
# Playback rejects confirmation, including stale enabled handler invocation.
w.playback.state.is_playing = True
panel._save_positions()
assert not result_path.exists()
w.playback.state.is_playing = False
# Exact source identity and active-state consistency fail closed.
out = w.outputs_manager.voutputs[1]
identity = out.kwargs["frame_compare_session_id"]
out.kwargs["frame_compare_session_id"] = "wrong-session"
assert panel._positions.snapshot() is None
out.kwargs["frame_compare_session_id"] = identity
w.playback.state.current_frame = 6
assert panel._positions.snapshot() is None
w.playback.state.current_frame = 7
# Manual drafts survive hidden browsing and advanced-basis changes.
panel.frame_inputs[0].setText("10")
switch(0)
seek(27)
assert panel.frame_inputs[0].text() == "10"
panel.basis_selector.setCurrentIndex(1)
panel.offset_inputs[0].setText("+2")
panel.basis_selector.setCurrentIndex(0)
assert panel.frame_inputs[0].text() == "10"
panel.viewer_buttons[0].click()
until(lambda: frames() == (27, 0, 7))
# A held real pool job must remain explained even with every frame entered.
release = Event()
blocker = w.loop.to_thread_named("ReviewManualBarrier", release.wait, 20)
until(blocker.running)
try:
    panel._update_positions()
    assert all("enter a frame manually" not in p.text() for p in panel.proposal_labels)
    for field, value in zip(panel.frame_inputs, (27, 0, 7)):
        field.setText(str(value + 1))
        field.setText(str(value))
    assert frames() == (27, 0, 7)
    assert all(p.text() == "Manually entered" for p in panel.proposal_labels)
    assert "3/3 frames entered" in panel.progress_label.text()
    assert "waiting" in panel.progress_label.text()
    assert panel.guidance_label.isVisible() and "background work" in panel.guidance_label.text()
    assert "does not bypass" in panel.guidance_label.text()
    assert not panel.use_positions_button.isEnabled()
    panel._save_positions()
    assert not result_path.exists()
finally:
    release.set()
until(blocker.done)
until(lambda: panel.use_positions_button.isEnabled())
assert frames() == (27, 0, 7)
assert panel.progress_label.text() == "3/3 frames ready"
assert "Waiting" not in panel.guidance_label.text()
space(panel.viewer_buttons[0])
assert panel._source_drafts[0].following
print("MANUAL_POOL_WAIT_OK drafts-retained no-early-sidecar readiness-restored")
# Save failure leaves editing enabled; successful retry freezes exact set.
import frame_compare.vsview.alignment_review_panel as panel_module

write = panel_module.write_alignment_review_result


def fail(*args):
    raise OSError("injected disk failure")


panel_module.write_alignment_review_result = fail
space(panel.use_positions_button)
assert not result_path.exists() and not panel._saved
assert not panel.frame_inputs[0].isReadOnly()
assert "Could not save alignment" in panel.error_label.text()
panel._update_positions()
assert "Could not save alignment" in panel.error_label.text()
release = Event()
blocker = w.loop.to_thread_named("ReviewErrorBarrier", release.wait, 20)
until(blocker.running)
try:
    panel._update_positions()
    assert "Waiting" in panel.guidance_label.text()
    assert "Could not save alignment" in panel.error_label.text()
finally:
    release.set()
until(blocker.done)
until(lambda: panel.use_positions_button.isEnabled())
writes = []


def counted_write(*args):
    writes.append(args)
    return write(*args)


panel_module.write_alignment_review_result = counted_write
space(panel.use_positions_button)
assert panel._saved
assert len(writes) == 1
assert panel.progress_label.text() == "Alignment choices saved"
assert panel.guidance_label.text() == "Close VSView to resume Frame Compare."
payload = json.loads(result_path.read_text())
assert payload["decisions"] == [
    {
        "comparison_key": "ref:a",
        "action": "confirmed",
        "reference_source_frame": 27,
        "comparison_source_frame": 0,
    },
    {
        "comparison_key": "ref:b",
        "action": "confirmed",
        "reference_source_frame": 27,
        "comparison_source_frame": 7,
    },
], payload
seek(30)
assert frames() == (27, 0, 7)
assert not panel._position_timer.isActive()
# Fresh rebind after reload uses the same panel and one destruction callback.
result_path.unlink()
callback_count = len(w.cbs_on_destroy)
reload = w.reload_content()
until(reload.done)
assert reload.result() == 0
until(idle)
until(lambda: panel._position_timer.isActive())
assert len(w.cbs_on_destroy) == callback_count
assert w.tab_manager.sync_playhead_btn.state == 0
assert all(d.following for d in panel._source_drafts)
# The shared action also activates in known-offset mode, and Keep saves once.
space(panel.manual_toggle)
panel.basis_selector.setCurrentIndex(1)
for field in panel.offset_inputs:
    field.setText("0")
space(panel.use_positions_button)
assert panel._saved and len(writes) == 2
assert all(d["action"] == "confirmed" for d in json.loads(result_path.read_text())["decisions"])
result_path.unlink()
reload = w.reload_content()
until(reload.done)
assert reload.result() == 0
until(lambda: panel._position_timer.isActive() and idle())
space(panel.keep_button)
assert panel._saved and panel._kept_current and len(writes) == 3
assert all(d["action"] == "keep_current" for d in json.loads(result_path.read_text())["decisions"])
assert panel.guidance_label.text() == "Close VSView to resume Frame Compare."
panel_module.write_alignment_review_result = write
print("KEYBOARD_OK disclosure audio viewer-frame confirm-both-bases keep single-writes viewer-space")
assert not render_errors, render_errors
assert SettingsManager.global_settings.model_dump_json() == global_before
# Ordinary sessions retain their own default linking and inactive panel.
ordinary = root / "ordinary.py"
ordinary.write_text(
    "import vapoursynth as vs\nvs.core.std.BlankClip(width=64,height=32,length=2,format=vs.RGB24).set_output()\n"
)
other_workspace = PythonScriptWorkspace()
loaded = other_workspace.load_content(ordinary)
until(loaded.done)
assert loaded.result() == 0
until(
    lambda: other_workspace.playback.can_reload and not other_workspace.tab_manager.disable_switch
)
ordinary_panel = next(p for p in other_workspace.plugins if isinstance(p, AlignmentReviewPanel))
assert ordinary_panel._positions is None and not ordinary_panel._position_timer.isActive()
assert other_workspace.tab_manager.sync_playhead_btn.state == 1
other_workspace.deleteLater()
app.processEvents()
# Destruction releases tracking; never closes another native application.
w.deleteLater()
app.processEvents()
assert panel._positions is None
assert not panel._position_timer.isActive()
print(
    "WORKSPACE_OK never-opened hidden other-tool rapid-seek independent zero sidecar freeze reload cleanup"
)
"""


@pytest.mark.vs_required
def test_installed_workspace_retains_hidden_positions_and_unlinks(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg unavailable for generated native workspace media")
    doctor = subprocess.run(
        [
            sys.executable,
            "-c",
            "import vapoursynth as vs; import PySide6,vsview; assert hasattr(vs.core, 'lsmas')",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if doctor.returncode:
        pytest.skip("Native VapourSynth/PySide6/VSView/L-SMASH unavailable")
    result = subprocess.run(
        [sys.executable, "-c", _NATIVE_WORKSPACE, str(tmp_path)],
        cwd=Path(__file__).resolve().parents[2],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        errors="replace",
        timeout=90,
        check=False,
    )
    (tmp_path / "native-workspace.log").write_text(
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}", encoding="utf-8"
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert "WORKSPACE_OK" in result.stdout
