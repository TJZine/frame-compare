"""Contained bridge for retained positions in the pinned VSView 0.13 workspace.

The public API exposes only the active frame and hides navigation callbacks when
the tool panel is closed. Read the workspace's existing per-output authority;
never reconstruct it by sampling the active output. No dependency hooks are patched.
"""

from __future__ import annotations

from importlib.metadata import version
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QThreadPool
from vsview.api import PluginAPI

from frame_compare.vsview.alignment_review_contract import AlignmentReviewWorkspaceMetadata


class WorkspacePositions:
    def __init__(
        self, api: PluginAPI, script: Path, metadata: AlignmentReviewWorkspaceMetadata
    ) -> None:
        if version("vsview") != "0.13.0":
            raise RuntimeError("Automatic frame tracking requires VSView 0.13.0")
        # This is the only private VSView access in Frame Compare. Keep the
        # version gate until a public retained-position API replaces it.
        from vsview.app.plugins._controller import get_controller

        controller = cast(Any, get_controller(api))
        self._workspace: Any = controller._PluginWorkspaceController__workspace
        self._api = api
        self._script = script
        self._metadata = metadata
        self._identities: dict[int, dict[str, Any]] = {
            output.vs_index: dict(output.kwargs)
            for output in self._workspace.outputs_manager.voutputs
        }
        if self.snapshot(require_idle=False) is None:
            raise RuntimeError("Workspace does not match the validated review session")

    def unlink(self) -> None:
        # Same session-local control used by FileWorkspace.init_load. This
        # changes the generated workspace only, never global preferences.
        self._workspace.tab_manager.sync_playhead_btn.set_state(state=0)

    def snapshot(self, *, require_idle: bool = True) -> tuple[int, ...] | None:
        workspace = self._workspace
        if self._api.file_path != self._script:
            return None
        playback = workspace.playback
        # VSView stops playback before an already dequeued frame necessarily
        # commits. Its named-task counter also misses wrappers still queued in
        # this shared pool. Qt counts assigned/recycled workers before their
        # Python wrapper starts, so require quiescence of the actual executor.
        # This intentionally also waits for other VSView background jobs.
        if require_idle and QThreadPool.globalInstance().activeThreadCount() != 0:
            return None
        if require_idle and (
            playback.state.is_playing
            or playback.has_pending_frame
            or playback._timeline_rendering
            or not playback.can_reload
            or workspace.tab_manager.disable_switch
            or workspace._is_failed
        ):
            return None
        sources = (self._metadata.reference, *self._metadata.comparisons)
        outputs = {output.vs_index: output for output in workspace.outputs_manager.voutputs}
        if len(outputs) != len(sources):
            return None
        active = workspace.outputs_manager.current_voutput
        if require_idle and (active is None or active.last_frame != playback.state.current_frame):
            return None
        frames: list[int] = []
        for source in sources:
            output = outputs.get(source.output_id)
            if (
                output is None
                or output.kwargs != self._identities.get(source.output_id)
                or output.kwargs.get("frame_compare_session_id") != self._metadata.session_id
                or output.vs_output.clip.num_frames != source.source_frame_count
            ):
                return None
            frame = output.last_frame
            if isinstance(frame, bool) or not isinstance(frame, int):
                return None
            if not 0 <= frame < source.source_frame_count:
                return None
            frames.append(frame)
        return tuple(frames)
