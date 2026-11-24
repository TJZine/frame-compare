"""Plan releases from fetched branch heads and publish the scanned Windows ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from scripts.validate_release_contract import (
    SHA_RE,
    VERSION_FILES,
    ReleaseContractError,
    contract,
    manifest_version,
)

PRE_RELEASE = "refs/heads/pre-release"
MAIN = "refs/heads/main"
ZIP_STEM = "frame-compare-portable-win-x64"
DIGEST = re.compile(r"[0-9a-f]{64}")
FIRST_RELEASE = "0.7.0"


class GitHistory:
    def _git(self, *args: str) -> str:
        return subprocess.check_output(["git", *args], encoding="utf-8", timeout=30).strip()

    def head(self, ref: str) -> str:
        # checkout fetches all heads into remote-tracking refs and fetches all tags.
        return self._git(
            "rev-parse",
            "--verify",
            f"refs/remotes/origin/{ref.removeprefix('refs/heads/')}^{{commit}}",
        )

    def tag_commit(self, tag: str) -> str | None:
        ref = f"refs/tags/{tag}"
        result = subprocess.run(
            ["git", "show-ref", "--exists", ref], capture_output=True, timeout=30, check=False
        )
        # show-ref --exists reserves exit 2 for an absent exact ref.
        if result.returncode == 2:
            return None
        result.check_returncode()
        return self._git("rev-parse", "--verify", f"{ref}^{{commit}}")

    def tags(self) -> list[str]:
        return self._git("for-each-ref", "--format=%(refname)", "refs/tags").splitlines()

    def tree(self, commit: str) -> str:
        return self._git("rev-parse", "--verify", f"{commit}^{{tree}}")

    def is_ancestor(self, ancestor: str, commit: str) -> bool:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, commit], timeout=30, check=False
        )
        if result.returncode not in (0, 1):
            result.check_returncode()
        return result.returncode == 0

    def require_matching_definitions(self, event_sha: str, planned_sha: str) -> None:
        if not SHA_RE.fullmatch(event_sha):
            raise ReleaseContractError("Release planning requires the exact event commit SHA.")
        result = subprocess.run(
            [
                "git",
                "diff",
                "--quiet",
                event_sha,
                planned_sha,
                "--",
                ".github/workflows/",
                ".github/actions/",
                "scripts/release_plan.py",
                "scripts/validate_release_contract.py",
                "tools/windows_portable/artifact_security.py",
            ],
            timeout=30,
            check=False,
        )
        if result.returncode == 1:
            raise ReleaseContractError(
                "Release definitions changed since this run's commit; "
                "re-run the push run for the current head instead."
            )
        result.check_returncode()

    def prepared_version(self, commit: str) -> str:
        return manifest_version(self._git("show", f"{commit}:.release-please-manifest.json"))

    def version_and_notes(self, commit: str) -> tuple[str, str]:
        return contract({name: self._git("show", f"{commit}:{name}") for name in VERSION_FILES})


class _HTTPSRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme != "https":
            raise ReleaseContractError("GitHub redirected the request outside HTTPS.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class GitHub:
    def __init__(self, repository: str, token: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise ReleaseContractError("Expected a GitHub repository in owner/name form.")
        self.repository = repository
        self.token = token
        self._opener = build_opener(_HTTPSRedirects())

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        data: bytes | BinaryIO | None = None,
        content_type: str = "application/json",
        accept: str = "application/vnd.github+json",
        host: Literal["api.github.com", "uploads.github.com"] = "api.github.com",
        size: int | None = None,
    ):
        request = Request(
            f"https://{host}/repos/{self.repository}/{path}",
            data=data,
            method=method,
            headers={
                "Accept": accept,
                "Content-Type": content_type,
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        # Asset downloads may redirect to a signed CDN URL.
        request.add_unredirected_header("Authorization", f"Bearer {self.token}")
        if size is not None:
            request.add_header("Content-Length", str(size))
        # The request has a fixed HTTPS origin and redirects must stay on HTTPS.
        return self._opener.open(request, timeout=60)  # nosec B310

    def api(self, path: str, *, method: str = "GET", body: Any = None) -> Any:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        with self._request(path, method=method, data=payload) as response:
            return None if response.status == 204 else json.load(response)

    def pages(self, path: str, **query: str) -> Iterator[dict[str, Any]]:
        page = 1
        while True:
            params = urlencode({**query, "per_page": 100, "page": page})
            rows = self.api(f"{path}?{params}")
            if not isinstance(rows, list):
                raise ReleaseContractError(f"GitHub did not return a list for {path}.")
            yield from rows
            if len(rows) < 100:
                return
            page += 1

    def _optional(self, path: str) -> Any:
        try:
            return self.api(path)
        except HTTPError as error:
            if error.code != 404:
                raise
            error.close()
            return None

    def release(self, tag: str) -> dict[str, Any] | None:
        return self._optional(f"releases/tags/{quote(tag, safe='')}")

    def _tag_ref(self, tag: str) -> dict[str, Any] | None:
        return self._optional(f"git/ref/tags/{quote(tag, safe='')}")

    def tag_exists(self, tag: str) -> bool:
        return self._tag_ref(tag) is not None

    def tag_commit(self, tag: str) -> str | None:
        ref = self._tag_ref(tag)
        target = ref.get("object") if ref is not None else None
        # Annotated tags can refer to other tags. Bound the chain of API reads.
        for remaining in range(8, -1, -1):
            if not isinstance(target, dict):
                return None
            sha = target.get("sha")
            if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
                return None
            if target.get("type") == "commit":
                return sha
            if target.get("type") != "tag" or remaining == 0:
                return None
            annotation = self._optional(f"git/tags/{sha}")
            target = annotation.get("object") if annotation is not None else None
        return None

    def asset_bytes(self, asset_id: int) -> bytes:
        with self._request(
            f"releases/assets/{asset_id}", accept="application/octet-stream"
        ) as response:
            return response.read(1024)

    def asset_digest(self, asset_id: int) -> str:
        with self._request(
            f"releases/assets/{asset_id}", accept="application/octet-stream"
        ) as response:
            return hashlib.file_digest(response, "sha256").hexdigest()

    def upload(self, release_id: int, asset: Path) -> None:
        with (
            asset.open("rb") as stream,
            self._request(
                f"releases/{release_id}/assets?{urlencode({'name': asset.name})}",
                method="POST",
                data=stream,
                content_type="application/octet-stream",
                host="uploads.github.com",
                size=asset.stat().st_size,
            ) as response,
        ):
            if response.status != 201:
                raise ReleaseContractError(f"GitHub did not create the asset {asset.name}.")


def zip_name(tag: str) -> str:
    return f"{ZIP_STEM}-{tag}.zip"


def _assets_match(
    github: GitHub,
    release: Mapping[str, Any],
    tag: str,
    *,
    expected_digest: str | None = None,
) -> bool:
    name = zip_name(tag)
    sidecar = f"{name}.sha256"
    assets = release["assets"]
    if len(assets) != 2 or {asset["name"] for asset in assets} != {name, sidecar}:
        return False
    by_name = {asset["name"]: asset for asset in assets}
    zipped = by_name[name]
    server_digest = zipped.get("digest")
    digest = server_digest
    if digest is None:
        digest = f"sha256:{github.asset_digest(zipped['id'])}"
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        return False
    checksum = digest.removeprefix("sha256:")
    if DIGEST.fullmatch(checksum) is None:
        return False
    if expected_digest is not None and checksum != expected_digest:
        return False
    expected_sidecar = f"{checksum}  {name}\n".encode("ascii")
    if github.asset_bytes(by_name[sidecar]["id"]) != expected_sidecar:
        return False
    # A freshly uploaded draft has to serve the exact bytes we are about to publish.
    return (
        expected_digest is None
        or server_digest is None
        or github.asset_digest(zipped["id"]) == expected_digest
    )


def _right_channel(release: Mapping[str, Any], tag: str) -> bool:
    return release["tag_name"] == tag and release["prerelease"] is ("-rc." in tag)


def complete(github: GitHub, release: Mapping[str, Any], tag: str) -> bool:
    return (
        release["draft"] is False
        and _right_channel(release, tag)
        and _assets_match(github, release, tag)
    )


def _rc_serial(version: str, tag: str) -> int | None:
    match = re.fullmatch(rf"v{re.escape(version)}-rc\.([1-9][0-9]*)", tag)
    return int(match[1]) if match else None


def next_rc(version: str, refs: Iterable[str]) -> int:
    serials = (
        _rc_serial(version, ref.removeprefix("refs/tags/"))
        for ref in refs
        if ref.startswith("refs/tags/")
    )
    return max((serial for serial in serials if serial is not None), default=0) + 1


def tested_rc(
    github: GitHub,
    history: GitHistory,
    version: str,
    releases: Iterable[dict[str, Any]],
    tree: str,
) -> str | None:
    for release in releases:
        tag = release["tag_name"]
        if (
            _rc_serial(version, tag) is None
            or release["draft"] is not False
            or release["prerelease"] is not True
        ):
            continue
        commit = history.tag_commit(tag)
        if commit is not None and history.tree(commit) == tree and complete(github, release, tag):
            return tag
    return None


@dataclass(frozen=True)
class Plan:
    sha: str
    version: str
    tag: str
    status: str = "publish"
    message: str = ""


def plan_rc(github: GitHub, history: GitHistory, event_sha: str) -> Plan:
    sha = history.head(PRE_RELEASE)
    history.require_matching_definitions(event_sha, sha)
    version, _ = history.version_and_notes(sha)
    stable_tag = f"v{version}"
    stable = github.release(stable_tag)
    if stable is not None and stable["draft"] is False and _right_channel(stable, stable_tag):
        return Plan(
            sha,
            version,
            stable_tag,
            "skip",
            "Stable is published, waiting for the next version.",
        )
    if not history.is_ancestor(history.head(MAIN), sha):
        raise ReleaseContractError(
            "RC cannot proceed: merge main into the integration branch first."
        )

    releases = [
        release
        for release in github.pages("releases")
        if _rc_serial(version, release["tag_name"]) is not None
    ]
    matching_rcs = []
    for release in releases:
        tag = release["tag_name"]
        if release["draft"] is not False:
            continue
        commit = history.tag_commit(tag)
        if commit is None:
            raise ReleaseContractError(
                f"Published RC {tag} is missing from the fetched Git tags. Re-run all jobs."
            )
        if commit == sha:
            matching_rcs.append(release)
    if matching_rcs:
        for release in matching_rcs:
            if not complete(github, release, release["tag_name"]):
                raise ReleaseContractError(
                    "The RC for this head is published but incomplete; repair it by hand."
                )
        return Plan(
            sha,
            version,
            matching_rcs[0]["tag_name"],
            "skip",
            "This head already has a complete RC.",
        )

    for release in releases:
        if release["draft"] is True:
            github.api(f"releases/{release['id']}", method="DELETE")
    return Plan(sha, version, f"{stable_tag}-rc.{next_rc(version, history.tags())}")


def plan_stable(github: GitHub, history: GitHistory, event_sha: str) -> Plan:
    sha = history.head(MAIN)
    history.require_matching_definitions(event_sha, sha)
    version, _ = history.version_and_notes(sha)
    tag = f"v{version}"
    stable = github.release(tag)
    if stable is not None and stable["draft"] is False:
        if not complete(github, stable, tag):
            raise ReleaseContractError(f"{tag} is published but incomplete; repair it by hand.")
        return Plan(sha, version, tag, "complete", f"{tag} is already published.")
    # The by-tag endpoint does not expose unpublished drafts.
    releases = list(github.pages("releases"))
    for release in releases:
        if release["tag_name"] == tag and release["draft"] is True:
            github.api(f"releases/{release['id']}", method="DELETE")
    if tested_rc(github, history, version, releases, history.tree(sha)) is None:
        raise ReleaseContractError(
            f"Promote a tested RC: no complete RC of {version} matches main's tree."
        )
    return Plan(sha, version, tag)


def release_please_enabled(github: GitHub, history: GitHistory) -> bool:
    sha = history.head(PRE_RELEASE)
    version = history.prepared_version(sha)
    tag = f"v{version}"
    stable = github.release(tag)
    if stable is None or stable["draft"] is not False or not _right_channel(stable, tag):
        return False
    commit = history.tag_commit(tag)
    return commit is not None and history.is_ancestor(commit, sha)


def _require_unpublished(github: GitHub, tag: str) -> None:
    release = github.release(tag)
    if release is not None and release["draft"] is False:
        raise ReleaseContractError(f"{tag} is already published.")
    if github.tag_exists(tag):
        raise ReleaseContractError(
            f"An existing refs/tags/{tag} prevents exact-target publication."
        )


def publish(
    github: GitHub,
    history: GitHistory,
    sha: str,
    tag: str,
    archive: Path,
    digest: str,
    *,
    rc_writer: GitHub | None = None,
) -> None:
    if not SHA_RE.fullmatch(sha):
        raise ReleaseContractError("Publication requires an exact source commit SHA.")
    version, notes = history.version_and_notes(sha)
    if tag != f"v{version}":
        if _rc_serial(version, tag) is None:
            raise ReleaseContractError(f"Tag {tag} does not match the source version {version}.")
        if rc_writer is None:
            raise ReleaseContractError("RC publication requires the RELEASE_PUBLISH_TOKEN secret.")
        writer = rc_writer
    else:
        writer = github
    if not DIGEST.fullmatch(digest):
        raise ReleaseContractError("Publication requires the raw ZIP's SHA-256.")
    with archive.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
            raise ReleaseContractError("Downloaded raw ZIP does not match the producer SHA-256.")

    target = archive.with_name(zip_name(tag))
    sidecar = target.with_suffix(".zip.sha256")
    archive.rename(target)
    with sidecar.open("xb") as stream:
        subprocess.run(
            ["sha256sum", target.name], cwd=target.parent, stdout=stream, check=True, timeout=60
        )
    subprocess.run(
        ["sha256sum", "--check", sidecar.name], cwd=target.parent, check=True, timeout=60
    )

    _require_unpublished(github, tag)
    draft = writer.api(
        "releases",
        method="POST",
        body={
            "tag_name": tag,
            "target_commitish": sha,
            "name": f"Frame Compare {tag}",
            "body": notes,
            "draft": True,
            "prerelease": "-rc." in tag,
        },
    )
    endpoint = f"releases/{draft['id']}"
    if (
        draft["draft"] is not True
        or not _right_channel(draft, tag)
        or draft["target_commitish"] != sha
    ):
        raise ReleaseContractError(f"GitHub did not create the requested draft for {tag} at {sha}.")
    github.upload(draft["id"], target)
    github.upload(draft["id"], sidecar)
    remote = github.api(endpoint)
    if (
        remote["draft"] is not True
        or not _right_channel(remote, tag)
        or remote["target_commitish"] != sha
        or remote["body"] != notes
        or not _assets_match(github, remote, tag, expected_digest=digest)
    ):
        raise ReleaseContractError(f"GitHub draft assets did not verify for {tag}.")
    _require_unpublished(github, tag)
    result = writer.api(endpoint, method="PATCH", body={"draft": False})
    if result["draft"] is not False or not _right_channel(result, tag):
        raise ReleaseContractError(f"GitHub did not publish {tag} on the requested channel.")
    actual = github.tag_commit(tag)
    if actual != sha:
        raise ReleaseContractError(
            f"Repair required: published tag {tag} resolves to {actual or 'no commit'}, "
            f"expected {sha}."
        )


def label_release_pr(github: GitHub, version: str) -> None:
    tagged, pending = "autorelease: tagged", "autorelease: pending"
    matching = []
    for pr in github.pages("pulls", state="closed", base="pre-release"):
        if pr["title"] == f"chore(release): {version}" and pr["merged_at"] is not None:
            labels = {label["name"] for label in pr["labels"]}
            if (
                pr["head"]["repo"]
                and pr["head"]["repo"]["full_name"] == github.repository
                and (pending in labels or tagged in labels)
            ):
                matching.append((pr["number"], labels))
    if not matching and version == FIRST_RELEASE:
        return
    if len(matching) != 1:
        raise ReleaseContractError(f"Expected one merged Release Please PR for {version}.")
    number, labels = matching[0]
    endpoint = f"issues/{number}/labels"
    # Add first so an interrupted run can still find and finish the same PR.
    if tagged not in labels:
        updated = github.api(endpoint, method="POST", body={"labels": [tagged]})
        if tagged not in {label["name"] for label in updated}:
            raise ReleaseContractError(f"GitHub did not apply {tagged!r} to PR #{number}.")
    if pending in labels:
        github.api(f"{endpoint}/{quote(pending, safe='')}", method="DELETE")


def _outputs(**values: str) -> None:
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
        for key, value in values.items():
            stream.write(f"{key}={value}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("plan-rc")
    commands.add_parser("plan-stable")
    commands.add_parser("release-please-guard")
    publisher = commands.add_parser("publish")
    publisher.add_argument("--sha", required=True)
    publisher.add_argument("--tag", required=True)
    publisher.add_argument("--archive", type=Path, required=True)
    publisher.add_argument("--digest", required=True)
    label = commands.add_parser("label")
    label.add_argument("--version", required=True)
    args = parser.parse_args()
    github = GitHub(os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"])
    history = GitHistory()
    try:
        if args.command == "publish":
            # Creating a tag at an RC commit can require GitHub's Workflows write permission.
            rc_writer = None
            if "-rc." in args.tag:
                token = os.environ.pop("RELEASE_PUBLISH_TOKEN", "").strip()
                if token:
                    rc_writer = GitHub(github.repository, token)
            publish(
                github, history, args.sha, args.tag, args.archive, args.digest, rc_writer=rc_writer
            )
        elif args.command == "label":
            label_release_pr(github, args.version)
        elif args.command == "release-please-guard":
            enabled = release_please_enabled(github, history)
            if not enabled:
                print("Release Please waits for the stable release and its commit on pre-release.")
            _outputs(enabled=str(enabled).lower())
        else:
            event_sha = os.environ["GITHUB_SHA"]
            plan = (
                plan_rc(github, history, event_sha)
                if args.command == "plan-rc"
                else plan_stable(github, history, event_sha)
            )
            print(plan.message or f"Build {plan.tag} from {plan.sha}")
            outputs = {"sha": plan.sha, "tag": plan.tag, "status": plan.status}
            if args.command == "plan-stable":
                outputs["version"] = plan.version
            _outputs(**outputs)
    except (
        ReleaseContractError,
        OSError,
        URLError,
        ValueError,
        KeyError,
        subprocess.SubprocessError,
    ) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
