"""One-time approved GitHub secret migration; never print secret data or API errors."""

from __future__ import annotations

import base64
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

REPOSITORY = "TJZine/frame-compare"
ENVIRONMENTS = ("production", "release-candidate")
SECRET_NAME = "WINDOWS_UPDATE_SIGNING_KEY_XML"
PUBLIC_KEY = Path(__file__).resolve().parents[1] / "tools/windows_portable/update_public_key.xml"


class MigrationError(RuntimeError):
    """A sanitized migration failure suitable for workflow logs."""


def validate_key(private_xml: str, public_xml: str) -> None:
    if not private_xml.strip() or len(private_xml) > 32768:
        raise MigrationError("Source signing key is missing or oversized.")
    if "<!DOCTYPE" in private_xml.upper() or "<!ENTITY" in private_xml.upper():
        raise MigrationError("Source signing key must not contain XML declarations of entities.")
    try:
        # Bounded input with DTD/entity declarations rejected above cannot expand entities.
        private = ElementTree.fromstring(private_xml)  # nosec B314
        # This is the checked-in public key, not an external XML input.
        public = ElementTree.fromstring(public_xml)  # nosec B314
        names = ("Modulus", "Exponent", "P", "Q", "DP", "DQ", "InverseQ", "D")
        if private.tag != "RSAKeyValue" or {child.tag for child in private} != set(names):
            raise ValueError
        if len(private) != len(names):
            raise ValueError
        values = {
            name: int.from_bytes(base64.b64decode(private.findtext(name, ""), validate=True))
            for name in names
        }
        for name in ("Modulus", "Exponent"):
            expected = int.from_bytes(base64.b64decode(public.findtext(name, ""), validate=True))
            if values[name] != expected:
                raise MigrationError("Source signing key does not match the committed public key.")
        n, e, p, q, d = (values[name] for name in ("Modulus", "Exponent", "P", "Q", "D"))
        if (
            p <= 1
            or q <= 1
            or p * q != n
            or values["DP"] != d % (p - 1)
            or values["DQ"] != d % (q - 1)
            or (q * values["InverseQ"]) % p != 1
            or (e * d) % math.lcm(p - 1, q - 1) != 1
        ):
            raise ValueError
    except (ElementTree.ParseError, ValueError, OverflowError):
        raise MigrationError("Source signing key has invalid RSA private-key parameters.") from None


def run_gh(arguments: list[str], *, secret_input: str | None = None) -> str:
    environment = os.environ.copy()
    for name in ("SOURCE_SIGNING_KEY", "GH_DEBUG", "DEBUG", "GH_HOST", "GH_ENTERPRISE_TOKEN"):
        environment.pop(name, None)
    environment["GH_PROMPT_DISABLED"] = "1"
    try:
        result = subprocess.run(
            ["gh", *arguments],
            input=secret_input,
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise MigrationError("GitHub CLI could not complete the migration operation.") from None
    if result.returncode != 0:
        raise MigrationError("GitHub rejected a migration operation; check token permissions.")
    return result.stdout if secret_input is None else ""


def migrate() -> None:
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY:
        raise MigrationError("Migration is restricted to the Frame Compare repository.")
    if not os.environ.get("GH_TOKEN", "").strip():
        raise MigrationError("Configure SIGNING_KEY_MIGRATION_TOKEN in production before approval.")
    key = os.environ.pop("SOURCE_SIGNING_KEY", "")
    validate_key(key, PUBLIC_KEY.read_text(encoding="utf-8"))

    # Check both destinations before writing; never create environments or alter protection rules.
    for name in ENVIRONMENTS:
        try:
            state = json.loads(run_gh(["api", f"repos/{REPOSITORY}/environments/{name}"]))
            rules = state["protection_rules"]
            approved = any(
                rule.get("type") == "required_reviewers" and rule.get("reviewers") for rule in rules
            )
        except (KeyError, TypeError, ValueError, AttributeError):
            raise MigrationError(
                "GitHub returned invalid environment protection metadata."
            ) from None
        if not approved:
            raise MigrationError(f"Environment {name} must retain required reviewer approval.")

    for name in ENVIRONMENTS:
        run_gh(
            ["secret", "set", SECRET_NAME, "--repo", REPOSITORY, "--env", name], secret_input=key
        )
        metadata = run_gh(["api", f"repos/{REPOSITORY}/environments/{name}/secrets/{SECRET_NAME}"])
        try:
            if json.loads(metadata)["name"] != SECRET_NAME:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise MigrationError(f"Could not confirm the destination secret in {name}.") from None
        print(f"Signing secret configured in {name}; value not displayed.")
    print("Repository source secret retained. Verify signed release before removing it.")


def main() -> int:
    try:
        migrate()
    except MigrationError as exc:
        print(f"Signing-key migration failed: {exc}", file=sys.stderr)
        return 1
    except OSError:
        # Do not print exception detail: runtime errors may embed sensitive input.
        print(
            "Signing-key migration failed. Check source key, token, and protected environments.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
