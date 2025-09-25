from __future__ import annotations

"""Slow.pics upload orchestration."""

from collections import defaultdict
from pathlib import Path
from typing import Callable, Dict, List, Optional, TYPE_CHECKING
from urllib.parse import urlsplit, unquote
import logging
import time
import uuid

import requests

if TYPE_CHECKING:  # pragma: no cover - typing only
    from requests_toolbelt.multipart.encoder import MultipartEncoder
else:  # pragma: no cover - optional dependency in tests
    try:
        from requests_toolbelt import MultipartEncoder  # type: ignore
    except Exception:
        MultipartEncoder = None  # type: ignore

from .datatypes import SlowpicsConfig


class SlowpicsAPIError(RuntimeError):
    """Raised when slow.pics API interactions fail."""


logger = logging.getLogger(__name__)


def _raise_for_status(response: requests.Response, context: str) -> None:
    if response.status_code >= 400:
        try:
            detail = response.json()
        except Exception:
            detail = response.text
        error = SlowpicsAPIError(f"{context} failed ({response.status_code}): {detail}")
        setattr(error, "status_code", response.status_code)
        raise error


def _redact_webhook(url: str) -> str:
    try:
        parsed = urlsplit(url)
    except Exception:
        return "webhook"
    if parsed.netloc:
        return parsed.netloc
    return parsed.path or "webhook"


def _post_direct_webhook(session: requests.Session, webhook_url: str, canonical_url: str) -> None:
    redacted = _redact_webhook(webhook_url)
    payload = {"content": canonical_url}
    backoff = 1.0
    for attempt in range(1, 4):
        try:
            resp = session.post(webhook_url, json=payload, timeout=10)
            if resp.status_code < 300:
                logger.info("Posted slow.pics URL to webhook host %s", redacted)
                return
            message = f"HTTP {resp.status_code}"
        except requests.RequestException as exc:
            message = exc.__class__.__name__
        logger.warning(
            "Webhook post attempt %s to %s failed: %s",
            attempt,
            redacted,
            message,
        )
        if attempt < 3:
            time.sleep(backoff)
            backoff = min(backoff * 2, 4.0)
    logger.error("Giving up on webhook delivery to %s after %s attempts", redacted, 3)


def _build_legacy_headers(session: requests.Session, encoder: "MultipartEncoder") -> Dict[str, str]:
    xsrf = session.cookies.get_dict().get("XSRF-TOKEN")
    if not xsrf:
        raise SlowpicsAPIError("Missing XSRF token; cannot complete slow.pics upload")
    return {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "en-US,en;q=0.9",
        "Access-Control-Allow-Origin": "*",
        "Content-Length": str(getattr(encoder, "len", 0)),
        "Content-Type": encoder.content_type,
        "Origin": "https://slow.pics/",
        "Referer": "https://slow.pics/comparison",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
        "X-XSRF-TOKEN": unquote(xsrf),
    }


def _format_tmdb_identifier(tmdb_id: str, category: str | None) -> str:
    """Normalize TMDB identifiers for slow.pics legacy form fields."""

    text = (tmdb_id or "").strip()
    if not text:
        return ""

    lowered = text.lower()
    if lowered.startswith(("movie/", "tv/", "movie_", "tv_")):
        return text

    normalized_category = (category or "").strip().lower()
    if normalized_category in {"movie", "tv"}:
        return f"{normalized_category}/{text}"

    return text


def _prepare_legacy_plan(image_files: List[str]) -> tuple[List[int], List[List[tuple[str, Path]]]]:
    groups: dict[int, List[tuple[str, Path]]] = defaultdict(list)
    for file_path in image_files:
        path = Path(file_path)
        if not path.is_file():
            raise SlowpicsAPIError(f"Image file not found: {file_path}")
        name = path.name
        if " - " not in name or not name.lower().endswith(".png"):
            raise SlowpicsAPIError(
                f"Screenshot '{name}' does not follow '<frame> - <label>.png' naming"
            )
        frame_part, label_part = name[:-4].split(" - ", 1)
        try:
            frame_idx = int(frame_part.strip())
        except ValueError as exc:
            raise SlowpicsAPIError(f"Unable to parse frame index from '{name}'") from exc
        label = label_part.strip() or "comparison"
        groups.setdefault(frame_idx, []).append((label, path))

    if not groups:
        raise SlowpicsAPIError("No screenshots available for slow.pics upload")

    frame_order = sorted(groups.keys())
    expected = len(groups[frame_order[0]])
    for frame, entries in groups.items():
        if len(entries) != expected:
            raise SlowpicsAPIError(
                f"Inconsistent screenshot count for frame {frame}; expected {expected}, found {len(entries)}"
            )
    ordered_groups = [groups[frame] for frame in frame_order]
    return frame_order, ordered_groups


def _upload_comparison_legacy(
    session: requests.Session,
    image_files: List[str],
    screen_dir: Path,
    cfg: SlowpicsConfig,
    *,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> str:
    if MultipartEncoder is None:
        raise SlowpicsAPIError(
            "requests-toolbelt is required for slow.pics uploads. Install it to enable auto-upload."
        )

    frame_order, grouped = _prepare_legacy_plan(image_files)
    browser_id = str(uuid.uuid4())

    fields: dict[str, str] = {
        "collectionName": cfg.collection_name or "Frame Comparison",
        "hentai": str(bool(cfg.is_hentai)).lower(),
        "optimize-images": "true",
        "browserId": browser_id,
        "public": str(bool(cfg.is_public)).lower(),
    }
    if cfg.tmdb_id:
        fields["tmdbId"] = _format_tmdb_identifier(cfg.tmdb_id, getattr(cfg, "tmdb_category", ""))
    if cfg.remove_after_days:
        fields["removeAfter"] = str(int(cfg.remove_after_days))

    upload_plan: List[List[Path]] = []
    for comp_index, frame in enumerate(frame_order):
        entries = grouped[comp_index]
        fields[f"comparisons[{comp_index}].name"] = str(frame)
        per_frame_paths: List[Path] = []
        for image_index, (label, path) in enumerate(entries):
            fields[f"comparisons[{comp_index}].imageNames[{image_index}]"] = label
            per_frame_paths.append(path)
        upload_plan.append(per_frame_paths)

    encoder = MultipartEncoder(fields, str(uuid.uuid4()))
    headers = _build_legacy_headers(session, encoder)
    response = session.post(
        "https://slow.pics/upload/comparison",
        data=encoder.to_string(),
        headers=headers,
        timeout=30,
    )
    _raise_for_status(response, "Legacy collection creation")
    try:
        comp_json = response.json()
    except ValueError as exc:
        raise SlowpicsAPIError("Invalid JSON response returned by slow.pics") from exc

    collection_uuid = comp_json.get("collectionUuid")
    key = comp_json.get("key")
    if not key:
        raise SlowpicsAPIError("Missing collection key in slow.pics response")
    canonical_url = f"https://slow.pics/c/{key}"
    images = comp_json.get("images")
    if not isinstance(images, list):
        raise SlowpicsAPIError("Slow.pics response missing image identifiers")
    if len(images) != len(upload_plan):
        raise SlowpicsAPIError("Unexpected slow.pics response structure for comparisons")

    for per_frame_paths, image_ids in zip(upload_plan, images):
        if not isinstance(image_ids, list) or len(image_ids) != len(per_frame_paths):
            raise SlowpicsAPIError("Slow.pics returned mismatched image identifiers")
        for path, image_uuid in zip(per_frame_paths, image_ids):
            upload_fields = {
                "collectionUuid": collection_uuid,
                "imageUuid": image_uuid,
                "file": (path.name, path.read_bytes(), "image/png"),
                "browserId": browser_id,
            }
            upload_encoder = MultipartEncoder(upload_fields, str(uuid.uuid4()))
            upload_headers = _build_legacy_headers(session, upload_encoder)
            upload_resp = session.post(
                "https://slow.pics/upload/image",
                data=upload_encoder.to_string(),
                headers=upload_headers,
                timeout=60,
            )
            _raise_for_status(upload_resp, f"Upload frame {path.name}")
            if getattr(upload_resp, "content", b""):
                text = upload_resp.content.decode("utf-8", "ignore").strip()
                if text and text.upper() != "OK":
                    raise SlowpicsAPIError(f"Unexpected slow.pics response: {text}")
            if progress_callback is not None:
                progress_callback(1)

    if cfg.webhook_url:
        _post_direct_webhook(session, cfg.webhook_url, canonical_url)
    if cfg.create_url_shortcut:
        shortcut_path = screen_dir / f"slowpics_{key}.url"
        shortcut_path.write_text(f"[InternetShortcut]\nURL={canonical_url}\n", encoding="utf-8")
    return canonical_url


def upload_comparison(
    image_files: List[str],
    screen_dir: Path,
    cfg: SlowpicsConfig,
    *,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> str:
    """Upload screenshots to slow.pics and return the collection URL."""

    if not image_files:
        raise SlowpicsAPIError("No image files provided for upload")

    session = requests.Session()
    try:
        session.get("https://slow.pics/comparison", timeout=10)
    except requests.RequestException as exc:
        raise SlowpicsAPIError(f"Failed to establish slow.pics session: {exc}") from exc

    xsrf_token = session.cookies.get("XSRF-TOKEN")
    if not xsrf_token:
        raise SlowpicsAPIError("Missing XSRF token from slow.pics response")

    logger.info("Using slow.pics legacy upload endpoints")
    url = _upload_comparison_legacy(
        session,
        image_files,
        screen_dir,
        cfg,
        progress_callback=progress_callback,
    )
    logger.info("Slow.pics: %s", url)
    return url
