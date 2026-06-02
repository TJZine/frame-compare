"""Service-owned slow.pics post-upload policy and side effects."""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from frame_compare.config.schema import SlowpicsConfig
from frame_compare.services.slowpics_shortcut import create_slowpics_url_shortcut
from frame_compare.services.slowpics_webhook import deliver_slowpics_webhook
from frame_compare.utils.post_upload_actions import PostUploadActionResult, PostUploadActionResults
from frame_compare.utils.types import WorkspacePaths

log = structlog.get_logger()


@dataclass(frozen=True)
class SlowpicsPostUploadRequest:
    """Service inputs for optional post-upload slow.pics side effects."""

    workspace: WorkspacePaths
    config: SlowpicsConfig
    slowpics_url: str
    metadata_title: str | None
    upload_title: str | None


async def run_slowpics_post_upload_actions(
    request: SlowpicsPostUploadRequest,
) -> PostUploadActionResults:
    actions: list[PostUploadActionResult] = []

    if request.config.create_url_shortcut:
        actions.extend(_create_shortcut_actions(request))
    if request.config.webhook_url is not None:
        actions.extend(await _deliver_webhook_actions(request))

    return tuple(actions)


def _create_shortcut_actions(
    request: SlowpicsPostUploadRequest,
) -> PostUploadActionResults:
    result = create_slowpics_url_shortcut(
        workspace=request.workspace,
        slowpics_url=request.slowpics_url,
        metadata_title=request.metadata_title,
        upload_title=request.upload_title,
    )
    if result.success:
        return (
            PostUploadActionResult(
                kind="shortcut",
                success=True,
                path=result.path,
                message="slow.pics URL shortcut written",
            ),
        )

    if result.warning is not None:
        log.warning(
            "slowpics_shortcut_create_failed",
            path=str(result.path) if result.path is not None else None,
            warning=result.warning,
        )
    return (
        PostUploadActionResult(
            kind="shortcut",
            success=False,
            path=result.path,
            warning=result.warning,
        ),
    )


async def _deliver_webhook_actions(
    request: SlowpicsPostUploadRequest,
) -> PostUploadActionResults:
    webhook_url = request.config.webhook_url
    if webhook_url is None:
        return ()

    result = await deliver_slowpics_webhook(
        webhook_url=webhook_url,
        slowpics_url=request.slowpics_url,
    )
    if result.success:
        return (
            PostUploadActionResult(
                kind="webhook",
                success=True,
                detail=result.detail,
                message="slow.pics webhook delivered",
            ),
        )

    if result.warning is not None:
        log.warning("slowpics_webhook_delivery_failed", warning=result.warning)
    return (
        PostUploadActionResult(
            kind="webhook",
            success=False,
            warning=result.warning,
        ),
    )
