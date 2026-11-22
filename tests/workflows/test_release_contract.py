from __future__ import annotations

import hashlib
import json
import subprocess
from email.message import Message
from pathlib import Path
from typing import Any, BinaryIO
from urllib.error import HTTPError

import pytest
from scripts.validate_release_contract import VERSION_FILES, ReleaseContractError, contract

from scripts import release_plan as release

VERSION = "0.7.1"
MAIN = "a" * 40
PRE_RELEASE = "b" * 40
OTHER_COMMIT = "c" * 40
STABLE = f"v{VERSION}"
RC = f"{STABLE}-rc.10"
ZIP_BYTES = b"raw ZIP fixture"
ZIP_DIGEST = hashlib.sha256(ZIP_BYTES).hexdigest()


def _files(version: str = VERSION) -> dict[str, str]:
    return dict(
        zip(
            VERSION_FILES,
            (
                json.dumps({".": version}),
                f'[project]\nname = "frame-compare"\nversion = "{version}"',
                f'__version__ = "{version}"  # x-release-please-version',
                f'[[package]]\nname = "frame-compare"\nversion = "{version}"\nsource = {{ editable = "." }}',
                f"# Changelog\n\n## Unreleased\n\nPending\n\n## [{version}]\n\n### Fixes\n\n- Adjusted output\n\n"
                "## [0.6.1]\n\nEarlier notes\n",
            ),
            strict=True,
        )
    )


class History(release.GitHistory):
    def __init__(self) -> None:
        self.ancestry = {(MAIN, PRE_RELEASE)}
        self.versions = {MAIN: VERSION, PRE_RELEASE: VERSION}
        self.tag_commits = {RC: PRE_RELEASE, STABLE: MAIN}
        self.trees = {MAIN: "same-tree", PRE_RELEASE: "same-tree", OTHER_COMMIT: "different-tree"}
        self.heads: list[str] = []

    def head(self, ref: str) -> str:
        self.heads.append(ref)
        return {release.MAIN: MAIN, release.PRE_RELEASE: PRE_RELEASE}[ref]

    def tag_commit(self, tag: str) -> str | None:
        return self.tag_commits.get(tag)

    def tags(self) -> list[str]:
        return [f"refs/tags/{tag}" for tag in self.tag_commits]

    def tree(self, commit: str) -> str:
        return self.trees[commit]

    def is_ancestor(self, ancestor: str, commit: str) -> bool:
        return (ancestor, commit) in self.ancestry

    def require_matching_definitions(self, event_sha: str, planned_sha: str) -> None:
        assert event_sha == planned_sha

    def prepared_version(self, commit: str) -> str:
        return self.versions[commit]

    def version_and_notes(self, commit: str) -> tuple[str, str]:
        return contract(_files(self.versions[commit]))


class GitHub(release.GitHub):
    def __init__(self) -> None:
        super().__init__("local/repository", "fixture")
        self.releases: list[dict[str, Any]] = []
        self.pulls: list[dict[str, Any]] = []
        self.binary: dict[int, bytes] = {}
        self.mutations: list[tuple[str, str]] = []
        self.downloads: list[int] = []
        self.missing_status = 404
        self.existing_tags: set[str] = set()
        self.corrupt_download = False

    def api(self, path: str, *, method: str = "GET", body: Any = None) -> Any:
        if method != "GET":
            self.mutations.append((method, path))
        match method, path.split("?", 1)[0].split("/"):
            case "GET", ["releases"]:
                return self.releases.copy()
            case "GET", ["pulls"]:
                assert "state=closed" in path and "base=pre-release" in path
                return self.pulls
            case "GET", ["releases", "tags", tag]:
                existing = next(
                    (r for r in self.releases if r["tag_name"] == tag and not r["draft"]), None
                )
                if existing is not None:
                    return existing
                raise HTTPError(path, self.missing_status, "fixture response", Message(), None)
            case "GET", ["git", "ref", "tags", tag]:
                if tag in self.existing_tags:
                    return {"ref": f"refs/tags/{tag}"}
                raise HTTPError(path, self.missing_status, "fixture response", Message(), None)
            case "DELETE", ["releases", identifier]:
                self.releases = [r for r in self.releases if r["id"] != int(identifier)]
            case "POST", ["releases"]:
                draft = {"id": 99, "assets": [], **body}
                self.releases.append(draft)
                return draft
            case "GET", ["releases", identifier]:
                return next(r for r in self.releases if r["id"] == int(identifier))
            case "PATCH", ["releases", identifier]:
                result = next(r for r in self.releases if r["id"] == int(identifier))
                result.update(body)
                return result
            case "POST", ["issues", _number, "labels"]:
                assert body == {"labels": ["autorelease: tagged"]}
                self.pulls[0]["labels"].append({"name": "autorelease: tagged"})
                return self.pulls[0]["labels"]
            case "DELETE", ["issues", _number, "labels", "autorelease%3A%20pending"]:
                self.pulls[0]["labels"].remove({"name": "autorelease: pending"})
            case _:
                raise AssertionError(f"Unexpected GitHub request {method} {path}.")

    def asset_bytes(self, asset_id: int) -> bytes:
        self.downloads.append(asset_id)
        return self.binary[asset_id]

    def asset_digest(self, asset_id: int) -> str:
        self.downloads.append(asset_id)
        data = b"damaged" if self.corrupt_download else self.binary[asset_id]
        return hashlib.sha256(data).hexdigest()

    def add_release(self, tag: str, *, draft: bool = False) -> dict[str, Any]:
        identifier = len(self.releases) + 1
        asset_id = 10 * identifier
        name = release.zip_name(tag)
        self.binary.update({asset_id: ZIP_BYTES, asset_id + 1: f"{ZIP_DIGEST}  {name}\n".encode()})
        value = {
            "id": identifier,
            "tag_name": tag,
            "draft": draft,
            "prerelease": "-rc." in tag,
            "assets": [
                {"id": asset_id, "name": name, "digest": f"sha256:{ZIP_DIGEST}"},
                {"id": asset_id + 1, "name": f"{name}.sha256"},
            ],
        }
        self.releases.append(value)
        return value

    def upload(self, release_id: int, asset: Path) -> None:
        draft = self.api(f"releases/{release_id}")
        assert draft["draft"] is True
        self.mutations.append(("UPLOAD", asset.name))
        identifier = 1000 + len(draft["assets"])
        self.binary[identifier] = asset.read_bytes()
        draft["assets"].append(
            {
                "id": identifier,
                "name": asset.name,
                "digest": f"sha256:{hashlib.sha256(self.binary[identifier]).hexdigest()}",
            }
        )


def test_release_contract_uses_one_stable_version_and_only_matching_notes() -> None:
    assert contract(_files()) == (VERSION, "### Fixes\n\n- Adjusted output\n")


@pytest.mark.parametrize("source", VERSION_FILES[:4])
def test_release_contract_rejects_disagreeing_version_sources(source: str) -> None:
    files = _files()
    files[source] = files[source].replace(VERSION, "0.7.2")
    with pytest.raises(ReleaseContractError, match="version sources disagree"):
        contract(files)


def test_release_contract_rejects_rc_version_and_ambiguous_editable_lock() -> None:
    with pytest.raises(ReleaseContractError, match="must name a stable"):
        contract(_files(VERSION + "rc1"))
    files = _files()
    lock = files["uv.lock"]
    files["uv.lock"] = f"{lock}\n{lock}"
    with pytest.raises(ReleaseContractError, match="exactly one editable"):
        contract(files)


@pytest.mark.parametrize(
    ("changelog", "error"),
    [
        ("## Unreleased\n\nPending", "must contain a level-two"),
        (f"## [{VERSION}]\ntext\n## [{VERSION}]\ntext", "exactly one"),
        (f"## [{VERSION}]\n\n## [0.6.1]\ntext", "must contain release notes"),
        (
            f"## [{VERSION}]\nFrame Compare v{VERSION}. See CHANGELOG.md at the tagged commit.",
            "legacy release placeholder",
        ),
    ],
)
def test_release_contract_refuses_missing_or_incomplete_notes(changelog: str, error: str) -> None:
    with pytest.raises(ReleaseContractError, match=error):
        contract(_files() | {"CHANGELOG.md": changelog})


def test_next_rc_uses_positive_decimal_tag_serials_in_numeric_order() -> None:
    assert (
        release.next_rc(
            VERSION,
            [
                f"refs/tags/{STABLE}-rc.{serial}"
                for serial in ("1", "9", "10", "00", "010", "0", "x")
            ]
            + ["refs/heads/v0.7.1-rc.99", "refs/tags/v1.0.0-rc.99"],
        )
        == 11
    )
    assert release.next_rc(VERSION, []) == 1


@pytest.mark.parametrize("defect", ["third asset", "wrong sidecar", "draft", "wrong channel"])
def test_complete_refuses_invalid_releases(defect: str) -> None:
    github = GitHub()
    candidate = github.add_release(RC)
    if defect == "third asset":
        candidate["assets"].append({"name": "unexpected"})
    elif defect == "wrong sidecar":
        github.binary[11] = f"{'a' * 64}  {release.zip_name(RC)}\n".encode()
    elif defect == "draft":
        candidate["draft"] = True
    else:
        candidate["prerelease"] = False
    assert not release.complete(github, candidate, RC)


def test_complete_uses_server_digest_or_downloads_when_absent() -> None:
    github = GitHub()
    candidate = github.add_release(RC)
    assert release.complete(github, candidate, RC)
    assert github.downloads == [11]
    candidate["assets"][0].pop("digest")
    github.downloads.clear()
    assert release.complete(github, candidate, RC)
    assert github.downloads == [10, 11]


def test_rc_published_stable_skips_before_ancestry_or_draft_cleanup() -> None:
    github, history = GitHub(), History()
    github.add_release(STABLE)
    github.add_release(f"{STABLE}-rc.1", draft=True)
    history.ancestry.clear()
    plan = release.plan_rc(github, history, PRE_RELEASE)
    assert plan.status == "skip" and "waiting for the next version" in plan.message
    assert history.heads == [release.PRE_RELEASE]
    assert not github.mutations


def test_rc_rejects_pre_release_without_main_ancestry() -> None:
    github, history = GitHub(), History()
    history.ancestry.clear()
    with pytest.raises(ReleaseContractError, match="merge main into the integration branch first"):
        release.plan_rc(github, history, PRE_RELEASE)
    assert not github.mutations


@pytest.mark.parametrize("complete", [True, False])
def test_rc_uses_existing_published_release_for_exact_head(complete: bool) -> None:
    github = GitHub()
    candidate = github.add_release(RC)
    github.add_release(f"{STABLE}-rc.1", draft=True)
    if complete:
        assert release.plan_rc(github, History(), PRE_RELEASE).status == "skip"
    else:
        candidate["assets"].clear()
        with pytest.raises(ReleaseContractError, match="published but incomplete"):
            release.plan_rc(github, History(), PRE_RELEASE)
    assert not github.mutations


def test_rc_missing_published_tag_blocks_before_draft_cleanup_or_serial_choice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    github, history = GitHub(), History()
    github.add_release(RC)
    missing = f"{STABLE}-rc.11"
    github.add_release(missing)
    github.add_release(f"{STABLE}-rc.12", draft=True)
    monkeypatch.setattr(history, "tags", lambda: pytest.fail("RC serial allocation started"))

    with pytest.raises(ReleaseContractError, match=f"Published RC {missing} is missing"):
        release.plan_rc(github, history, PRE_RELEASE)
    assert not github.mutations
    assert not github.downloads


def test_rc_discards_only_own_stale_drafts_then_allocates_next_existing_tag_serial() -> None:
    github, history = GitHub(), History()
    github.add_release(RC)
    history.tag_commits[RC] = OTHER_COMMIT
    stale = github.add_release(f"{STABLE}-rc.11", draft=True)
    earlier = github.add_release("v0.7.0-rc.9", draft=True)
    preview = github.add_release(f"{STABLE}-rc.preview", draft=True)
    github.add_release(STABLE, draft=True)
    assert release.plan_rc(github, history, PRE_RELEASE) == release.Plan(
        "rc", PRE_RELEASE, VERSION, f"{STABLE}-rc.11"
    )
    assert github.mutations == [("DELETE", f"releases/{stale['id']}")]
    assert earlier in github.releases
    assert preview in github.releases
    assert history.heads == [release.PRE_RELEASE, release.MAIN]


@pytest.mark.parametrize("defect", ["draft", "tree mismatch", "incomplete", "wrong version"])
def test_stable_refuses_rc_without_complete_equal_tree(defect: str) -> None:
    github, history = GitHub(), History()
    candidate = github.add_release(RC)
    if defect == "draft":
        candidate["draft"] = True
    elif defect == "tree mismatch":
        history.tag_commits[RC] = OTHER_COMMIT
    elif defect == "wrong version":
        candidate["tag_name"] = "v0.6.1-rc.1"
    else:
        candidate["assets"].clear()
    assert release.tested_rc(github, history, VERSION, github.releases, history.tree(MAIN)) is None

    stale = github.add_release(STABLE, draft=True)
    with pytest.raises(ReleaseContractError, match="no complete RC of .* matches main's tree"):
        release.plan_stable(github, history, MAIN)
    assert github.mutations == [("DELETE", f"releases/{stale['id']}")]


def test_stable_plans_publication_from_equal_tree_at_different_commit() -> None:
    github, history = GitHub(), History()
    legacy = github.add_release("v0.6.1")
    legacy["assets"].clear()
    stale = github.add_release(STABLE, draft=True)
    github.add_release(RC)
    assert release.plan_stable(github, history, MAIN) == release.Plan(
        "stable", MAIN, VERSION, STABLE
    )
    assert history.heads == [release.MAIN]
    assert github.mutations == [("DELETE", f"releases/{stale['id']}")]


def test_stable_skips_rc_missing_from_snapshot_and_uses_complete_equal_tree_rc() -> None:
    github, history = GitHub(), History()
    github.add_release(f"{STABLE}-rc.11")
    candidate = github.add_release(RC)

    assert release.plan_stable(github, history, MAIN) == release.Plan(
        "stable", MAIN, VERSION, STABLE
    )
    assert github.downloads == [candidate["assets"][1]["id"]]
    assert not github.mutations


@pytest.mark.parametrize("complete", [True, False])
def test_stable_never_replaces_published_release(complete: bool) -> None:
    github = GitHub()
    existing = github.add_release(STABLE)
    if complete:
        plan = release.plan_stable(github, History(), MAIN)
        assert plan.status == "complete"
        assert plan.tag == STABLE and plan.version == VERSION
    else:
        existing["assets"].clear()
        with pytest.raises(
            ReleaseContractError, match="published but incomplete; repair it by hand"
        ):
            release.plan_stable(github, History(), MAIN)
    assert not github.mutations


@pytest.mark.parametrize(
    ("operation", "args"),
    [
        (release.plan_stable, (MAIN,)),
        (release.plan_rc, (PRE_RELEASE,)),
        (release.release_please_enabled, ()),
    ],
)
@pytest.mark.parametrize("status", [403, 500])
def test_non_404_release_lookup_is_fatal(operation, args: tuple[str, ...], status: int) -> None:
    github = GitHub()
    github.missing_status = status
    with pytest.raises(HTTPError) as error:
        operation(github, History(), *args)
    assert error.value.code == status
    assert not github.mutations


def test_release_please_waits_for_stable_and_its_commit_after_dependabot_merge() -> None:
    github, history = GitHub(), History()
    assert not release.release_please_enabled(github, history)
    stable = github.add_release(STABLE)
    history.ancestry.clear()
    assert not release.release_please_enabled(github, history)
    history.ancestry.add((MAIN, PRE_RELEASE))
    assert release.release_please_enabled(github, history)
    stable["prerelease"] = True
    assert not release.release_please_enabled(github, history)
    assert history.heads == [release.PRE_RELEASE] * 4


def test_release_please_waits_if_published_stable_tag_is_missing_from_snapshot() -> None:
    github, history = GitHub(), History()
    github.add_release(STABLE)
    del history.tag_commits[STABLE]

    assert not release.release_please_enabled(github, history)
    assert not github.mutations

    history.tag_commits[STABLE] = MAIN
    assert release.release_please_enabled(github, history)


def test_git_history_uses_remote_heads(monkeypatch: pytest.MonkeyPatch) -> None:
    def git(*args: str) -> str:
        assert args == ("rev-parse", "--verify", "refs/remotes/origin/pre-release^{commit}")
        return PRE_RELEASE

    history = release.GitHistory()
    monkeypatch.setattr(history, "_git", git)
    assert history.head(release.PRE_RELEASE) == PRE_RELEASE


@pytest.mark.parametrize("channel", ["rc", "stable"])
@pytest.mark.parametrize(
    "changed_path",
    [
        "src/frame_compare/feature.py",
        ".github/workflows/windows-portable.yml",
        ".github/actions/windows-portable-build/action.yml",
        "scripts/release_plan.py",
        "scripts/validate_release_contract.py",
        "tools/windows_portable/artifact_security.py",
    ],
)
def test_release_plan_checks_event_definitions_against_live_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, channel: str, changed_path: str
) -> None:
    def git(*args: str) -> str:
        return subprocess.check_output(
            [
                "git",
                "-c",
                "user.name=Release test",
                "-c",
                "user.email=release@example.invalid",
                "-c",
                "commit.gpgsign=false",
                *args,
            ],
            cwd=tmp_path,
            text=True,
            timeout=30,
        ).strip()

    git("init", "--quiet")
    for name, data in _files().items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
    git("add", ".")
    git("commit", "--quiet", "-m", "Event commit")
    event = git("rev-parse", "HEAD")
    path = tmp_path / changed_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("updated", encoding="utf-8")
    git("add", changed_path)
    git("commit", "--quiet", "-m", "Live commit")
    planned = git("rev-parse", "HEAD")
    git("update-ref", "refs/remotes/origin/main", planned)
    git("update-ref", "refs/remotes/origin/pre-release", planned)
    github = GitHub()
    if channel == "stable":
        git("tag", RC, planned)
        github.add_release(RC)
    source_only = changed_path.startswith("src/")
    if not source_only:
        github.add_release(STABLE if channel == "stable" else f"{STABLE}-rc.9", draft=True)
    plan = release.plan_rc if channel == "rc" else release.plan_stable
    monkeypatch.chdir(tmp_path)
    if source_only:
        result = plan(github, release.GitHistory(), event)
        assert result.status == "publish"
        assert result.sha == planned
    else:
        with pytest.raises(
            ReleaseContractError,
            match=(
                "Release definitions changed since this run's commit; "
                "re-run the push run for the current head instead."
            ),
        ):
            plan(github, release.GitHistory(), event)
    assert not github.mutations


def test_git_history_looks_up_exact_tags_and_peels_only_to_commits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def git(*args: str) -> str:
        return subprocess.check_output(
            [
                "git",
                "-c",
                "user.name=Release test",
                "-c",
                "user.email=release@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "-c",
                "tag.gpgSign=false",
                *args,
            ],
            cwd=tmp_path,
            text=True,
            timeout=30,
        ).strip()

    git("-c", "init.defaultRefFormat=files", "init", "--quiet")
    git("commit", "--quiet", "--allow-empty", "-m", "Tag fixture")
    commit = git("rev-parse", "HEAD")
    git("branch", STABLE)
    git("tag", f"prefix/{STABLE}")
    git("tag", "non-commit", "HEAD^{tree}")
    (tmp_path / ".git/refs/tags/malformed").write_text("invalid ref\n", encoding="ascii")
    monkeypatch.chdir(tmp_path)
    history = release.GitHistory()

    assert history.tag_commit(STABLE) is None
    with pytest.raises(subprocess.CalledProcessError) as malformed:
        history.tag_commit("malformed")
    assert malformed.value.returncode == 1
    assert malformed.value.cmd == ["git", "show-ref", "--exists", "refs/tags/malformed"]

    with pytest.raises(subprocess.CalledProcessError) as unpeelable:
        history.tag_commit("non-commit")
    assert unpeelable.value.cmd == [
        "git",
        "rev-parse",
        "--verify",
        "refs/tags/non-commit^{commit}",
    ]

    git("tag", "--annotate", "-m", "Release fixture", STABLE)
    assert git("cat-file", "-t", f"refs/tags/{STABLE}") == "tag"
    assert history.tag_commit(STABLE) == commit


def test_git_history_propagates_ref_lookup_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "unavailable.git"))

    with pytest.raises(subprocess.CalledProcessError) as lookup_error:
        release.GitHistory().tag_commit(STABLE)
    assert lookup_error.value.returncode == 128
    assert lookup_error.value.cmd == ["git", "show-ref", "--exists", f"refs/tags/{STABLE}"]


@pytest.fixture
def portable_checksum(monkeypatch: pytest.MonkeyPatch) -> None:
    def sha256sum(
        command: list[str],
        *,
        cwd: Path,
        stdout: BinaryIO | None = None,
        check: bool,
        timeout: int,
    ) -> subprocess.CompletedProcess[bytes]:
        assert command[0] == "sha256sum" and check and timeout == 60
        leaf = command[-1]
        assert Path(leaf).name == leaf
        if len(command) == 2:
            assert stdout is not None
            digest = hashlib.sha256((cwd / leaf).read_bytes()).hexdigest()
            stdout.write(f"{digest}  {leaf}\n".encode())
        else:
            assert command[1] == "--check"
            assert stdout is None
            digest, name = (cwd / leaf).read_text(encoding="ascii").strip().split("  ")
            assert digest == hashlib.sha256((cwd / name).read_bytes()).hexdigest()
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(release.subprocess, "run", sha256sum)


@pytest.mark.usefixtures("portable_checksum")
@pytest.mark.parametrize("tag", [STABLE, RC])
def test_publisher_creates_draft_uploads_pair_verifies_remote_then_publishes(
    tmp_path: Path, tag: str
) -> None:
    github, history = GitHub(), History()
    raw = tmp_path / f"{release.ZIP_STEM}.zip"
    raw.write_bytes(ZIP_BYTES)
    release.publish(github, history, MAIN, tag, raw, ZIP_DIGEST)
    name = release.zip_name(tag)
    assert github.mutations == [
        ("POST", "releases"),
        ("UPLOAD", name),
        ("UPLOAD", f"{name}.sha256"),
        ("PATCH", "releases/99"),
    ]
    assert github.downloads == [1001, 1000]
    result = github.releases[0]
    assert result["target_commitish"] == MAIN
    assert result["body"] == "### Fixes\n\n- Adjusted output\n"
    assert result["prerelease"] is ("-rc." in tag)
    assert result["draft"] is False
    assert github.binary[1001] == f"{ZIP_DIGEST}  {name}\n".encode()


@pytest.mark.usefixtures("portable_checksum")
@pytest.mark.parametrize(
    ("failure", "error"),
    [
        ("digest", "does not match the producer SHA-256"),
        ("remote", "draft assets did not verify"),
        ("published", "already published"),
        ("tag", "existing refs/tags/"),
    ],
)
def test_publisher_never_publishes_on_mismatch_or_collision(
    tmp_path: Path, failure: str, error: str
) -> None:
    github = GitHub()
    raw = tmp_path / "raw.zip"
    raw.write_bytes(b"wrong ZIP" if failure == "digest" else ZIP_BYTES)
    github.corrupt_download = failure == "remote"
    if failure == "published":
        github.add_release(STABLE)
    if failure == "tag":
        github.existing_tags.add(STABLE)
    with pytest.raises(ReleaseContractError, match=error):
        release.publish(github, History(), MAIN, STABLE, raw, ZIP_DIGEST)
    if failure == "remote":
        assert [method for method, _ in github.mutations] == ["POST", "UPLOAD", "UPLOAD"]
        assert github.releases[0]["draft"] is True
    else:
        assert not github.mutations


def test_label_repair_is_idempotent_with_first_cut_exception_only() -> None:
    github = GitHub()
    release.label_release_pr(github, "0.7.0")
    with pytest.raises(ReleaseContractError, match="Expected one merged"):
        release.label_release_pr(github, VERSION)
    github.pulls.append(
        {
            "title": f"chore(release): {VERSION}",
            "merged_at": "2026-01-01T00:00:00Z",
            "head": {"repo": {"full_name": github.repository}},
            "number": 12,
            "labels": [{"name": "autorelease: pending"}],
        }
    )
    release.label_release_pr(github, VERSION)
    release.label_release_pr(github, VERSION)
    assert github.mutations == [
        ("POST", "issues/12/labels"),
        ("DELETE", "issues/12/labels/autorelease%3A%20pending"),
    ]
    assert github.pulls[0]["labels"] == [{"name": "autorelease: tagged"}]
