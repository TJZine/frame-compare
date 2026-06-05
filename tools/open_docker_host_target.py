#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
ALLOWED_CONTAINER_ROOTS: tuple[tuple[PurePosixPath, str], ...] = (
    (PurePosixPath("/workspace/screenshots"), "screenshots"),
    (PurePosixPath("/workspace/generated"), "generated"),
)
DISALLOWED_CONTAINER_ROOTS: tuple[PurePosixPath, ...] = (
    PurePosixPath("/workspace/config"),
    PurePosixPath("/workspace/comparison_videos"),
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Open a Docker-mounted report/output path on the host, or open an "
            "explicit slow.pics URL."
        )
    )
    parser.add_argument(
        "target",
        help=(
            "Container path under /workspace/screenshots or /workspace/generated, "
            "or an https://slow.pics/... URL."
        ),
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print the translated host path or validated URL without opening it.",
    )
    return parser


def validate_slowpics_url(target: str) -> str:
    parsed = urlparse(target)
    if parsed.scheme != "https":
        raise ValueError("only https slow.pics URLs are allowed")
    if parsed.hostname != "slow.pics":
        raise ValueError("only https://slow.pics/... URLs are allowed")
    if parsed.username is not None or parsed.password is not None or parsed.port is not None:
        raise ValueError("slow.pics URL must not include credentials or a port")
    if not parsed.path.startswith("/"):
        raise ValueError("slow.pics URL must include an absolute path")
    return target


def translate_container_path(target: str, *, repo_root: Path | None = None) -> Path:
    resolved_repo_root = REPO_ROOT if repo_root is None else repo_root
    container_path = PurePosixPath(target)
    if not container_path.is_absolute():
        raise ValueError("container path must be absolute")
    if any(part in {".", ".."} for part in container_path.parts[1:]):
        raise ValueError("container path must not contain '.' or '..' segments")

    for disallowed_root in DISALLOWED_CONTAINER_ROOTS:
        try:
            container_path.relative_to(disallowed_root)
        except ValueError:
            continue
        raise ValueError(f"container path is not openable from the host helper: {disallowed_root}")

    for container_root, host_dir_name in ALLOWED_CONTAINER_ROOTS:
        try:
            relative_path = container_path.relative_to(container_root)
        except ValueError:
            continue

        host_root = (resolved_repo_root / host_dir_name).resolve()
        translated = (host_root / Path(*relative_path.parts)).resolve(strict=False)
        if not translated.is_relative_to(host_root):
            raise ValueError("translated host path escapes the allowed host root")
        if not translated.exists():
            raise ValueError(f"translated host path does not exist: {translated}")
        return translated

    raise ValueError(
        "unsupported container path; only /workspace/screenshots and /workspace/generated "
        "may be opened from the host"
    )


def normalize_target(target: str, *, repo_root: Path | None = None) -> str | Path:
    parsed = urlparse(target)
    if parsed.scheme:
        return validate_slowpics_url(target)
    return translate_container_path(target, repo_root=repo_root)


def open_target(target: str | Path) -> None:
    open_arg = target.as_uri() if isinstance(target, Path) else target

    try:
        opened = webbrowser.open(open_arg)
    except webbrowser.Error as exc:
        raise RuntimeError(f"failed to open target in the host browser: {exc}") from exc
    if not opened:
        raise RuntimeError("failed to open target in the host browser")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        normalized = normalize_target(args.target)
    except ValueError as exc:
        parser.error(str(exc))

    if isinstance(normalized, Path):
        print(normalized)
    else:
        print(normalized)

    if args.print_only:
        return 0

    try:
        open_target(normalized)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
