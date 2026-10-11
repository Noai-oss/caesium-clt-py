"""Propose the latest upstream release only after checking all assets."""

import argparse
import json
import os
import re
import urllib.request
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from scripts.common import ROOT, canonical_version, outputs


def upstream_repository(homepage: str) -> str:
    """Return owner/repo from a GitHub HTTPS URL, rejecting other URL shapes."""
    url = urlsplit(homepage)
    repository = url.path.strip("/")
    if (
        url.scheme != "https"
        or url.netloc != "github.com"
        or url.query
        or url.fragment
        or not re.fullmatch(r"[\w.-]+/[\w.-]+", repository)
    ):
        raise ValueError(f"Expected a GitHub repository homepage, got {homepage!r}")
    return repository


def asset_names(config: dict, tag: str) -> list[str]:
    """Derive one archive name per target from wheel.json's executable paths."""
    targets = {
        PurePosixPath(entries[0]["path"]).parent.name
        for entries in config["binaries"].values()
    }
    return [
        f"caesiumclt-{tag}-{target}" + (".zip" if "windows" in target else ".tar.gz")
        for target in sorted(targets)
    ]


def get_json(url: str, token: str | None = None) -> dict:
    """Fetch a JSON object once with an optional token and a 30-second timeout."""
    headers = {"User-Agent": "caesium-clt-py", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        value = json.load(response)
    if not isinstance(value, dict):
        raise TypeError(f"Expected a JSON object from {url}")
    return value


def candidate_release(config: dict, release: dict) -> str | None:
    """Return a newer version from /releases/latest after checking its assets.

    Validate the tag format and, for newer versions, require each configured
    asset exactly once, uploaded and nonempty. For an older or equal version,
    return None without inspecting assets.
    """
    tag = release["tag_name"]
    if not isinstance(tag, str) or not tag.startswith("v"):
        raise ValueError(f"Expected an upstream tag starting with 'v', got {tag!r}")
    version = tag[1:]
    if canonical_version(version) <= canonical_version(config["version"]):
        return None
    for name in asset_names(config, tag):
        matches = [asset for asset in release["assets"] if asset["name"] == name]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one upstream asset: {name}")
        asset = matches[0]
        if asset["state"] != "uploaded" or asset["size"] <= 0:
            raise ValueError(f"Upstream asset is not ready: {name}")
    return version


def update_version(
    config_path: Path, token: str | None = None, report_path: Path | None = None
) -> bool:
    """Update the configured version from upstream latest and report the change.

    Return False without rewriting files when the latest version is not newer.
    Otherwise validate its assets before writing an optional PR report and the
    updated configuration, emit Actions outputs, and return True. API, version,
    or asset validation errors propagate before any files are written.
    """
    config = json.loads(config_path.read_text(encoding="utf-8"))
    repository = upstream_repository(config["homepage"])
    release = get_json(
        f"https://api.github.com/repos/{repository}/releases/latest", token
    )
    version = candidate_release(config, release)
    previous = config["version"]
    if version is None:
        outputs(changed="false", version=previous)
        return False
    tag = "v" + version
    if report_path:
        report_path.write_text(
            f"Update caesium-clt from {previous} to {version}.\n\n"
            f"Upstream release: https://github.com/{repository}/releases/tag/{tag}\n\n"
            "Required assets are listed as uploaded and nonempty. "
            "CI will build and test the wheels.\n\n"
            "Approve this bot PR's workflows, review and merge, "
            f"then publish tag {tag} from main.\n",
            encoding="utf-8",
        )
    config["version"] = version
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    outputs(changed="true", previous_version=previous, version=version)
    return True


def main() -> None:
    """Update wheel.json using GITHUB_TOKEN and an optional CLI report path."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    update_version(ROOT / "wheel.json", os.environ.get("GITHUB_TOKEN"), args.report)


if __name__ == "__main__":
    main()
