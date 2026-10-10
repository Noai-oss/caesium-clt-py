"""Compare the version in wheel.json with the version published on PyPI."""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from packaging.version import Version

ROOT = Path(__file__).resolve().parent


def get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "caesium-clt-py"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def check_version(config: dict) -> dict[str, str]:
    version = config["version"]
    candidate = Version(version)

    try:
        published = get_json(f"https://pypi.org/pypi/{config['name']}/json")["info"][
            "version"
        ]
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        error.close()
        published = None

    return {
        "version": version,
        "published_version": published or "",
        "needs_publish": str(
            published is None or candidate > Version(published)
        ).lower(),
    }


def main() -> None:
    config = json.loads((ROOT / "wheel.json").read_text(encoding="utf-8"))
    result = check_version(config)
    output = "".join(f"{key}={value}\n" for key, value in result.items())
    print(output, end="")
    if destination := os.environ.get("GITHUB_OUTPUT"):
        with Path(destination).open("a", encoding="utf-8") as file:
            file.write(output)


if __name__ == "__main__":
    main()
