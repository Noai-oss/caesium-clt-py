"""Update wheel.json when a newer upstream release is available."""

import json
import os
import urllib.request
from pathlib import Path

from packaging.version import Version

ROOT = Path(__file__).resolve().parent


def update_version(config_path: Path, token: str | None = None) -> bool:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    repository = config["homepage"].removeprefix("https://github.com/").rstrip("/")
    headers = {"User-Agent": "caesium-clt-py"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/releases/latest", headers=headers
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        tag = json.load(response)["tag_name"]
    if not tag.startswith("v"):
        raise ValueError(f"Expected an upstream tag starting with 'v', got {tag!r}")
    version = tag[1:]
    if Version(version) <= Version(config["version"]):
        return False

    config["version"] = version
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return True


def main() -> None:
    changed = update_version(ROOT / "wheel.json", token=os.environ.get("GITHUB_TOKEN"))
    print("Updated wheel.json." if changed else "wheel.json is up to date.")


if __name__ == "__main__":
    main()
