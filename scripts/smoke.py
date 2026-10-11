"""Install a local wheel and check its version and image compression."""

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

from packaging.version import Version
from PIL import Image

from scripts.common import ROOT, summary


def cli_version(output: str) -> Version:
    """Parse caesiumclt --version output, rejecting extra or unrelated text."""
    match = re.fullmatch(r"\s*caesiumclt\s+v?(\S+)\s*", output)
    if not match:
        raise ValueError(f"Unrecognized caesiumclt version output: {output!r}")
    return Version(match[1])


def check_image(path: Path) -> None:
    """Require a nonempty, fully decodable PNG with the fixture's 32x24 size."""
    if path.stat().st_size == 0:
        raise ValueError("Compression produced an empty image")
    with Image.open(path) as result:
        result.load()
        if result.format != "PNG" or result.size != (32, 24):
            raise ValueError(
                f"Unexpected compressed image: {result.format} {result.size}"
            )


def run_cli(arguments: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    """Run a command with a timeout in seconds and capture its text output.

    Include stdout and stderr in the Actions summary before raising for a
    nonzero exit status. Timeout errors propagate directly.
    """
    result = subprocess.run(
        arguments, check=False, capture_output=True, text=True, timeout=timeout
    )
    if result.returncode:
        summary(f"CLI failed:\n{result.stdout}\n{result.stderr}")
        result.check_returncode()
    return result


def run_smoke(wheel: Path, version: str) -> dict:
    """Install a local wheel, verify its CLI, and return a diagnostic report.

    Use a temporary venv without index or dependency resolution. Require the
    binary's version to match version and its compressed fixture to pass image
    validation. Clean up the environment and generated images on every exit.
    """
    with tempfile.TemporaryDirectory(prefix="caesium-smoke-") as temporary:
        work = Path(temporary)
        environment = work / "venv"
        venv.EnvBuilder(with_pip=False).create(environment)
        scripts = environment / ("Scripts" if os.name == "nt" else "bin")
        python = scripts / ("python.exe" if os.name == "nt" else "python")
        executable = scripts / ("caesiumclt.exe" if os.name == "nt" else "caesiumclt")
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--no-index",
                "--no-deps",
                str(wheel.resolve()),
            ],
            check=True,
            timeout=120,
        )
        result = run_cli(
            [str(executable), "--version"],
            timeout=30,
        )
        if cli_version(result.stdout) != Version(version):
            raise ValueError(
                f"Binary version differs from wheel.json: {result.stdout!r}"
            )
        output = work / "output"
        output.mkdir()
        compression = run_cli(
            [
                str(executable),
                "-q",
                "80",
                "-o",
                str(output),
                str(ROOT / "tests/fixtures/smoke.png"),
            ],
            timeout=120,
        )
        check_image(output / "smoke.png")
    return {
        "os": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version,
        "wheel": wheel.name,
        "version_output": result.stdout.strip(),
        "compression_output": compression.stdout + compression.stderr,
        "image": "PNG, 32x24, fully decoded",
    }


def main() -> None:
    """Test the CLI-selected wheel against wheel.json and summarize the result."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    config = json.loads((ROOT / "wheel.json").read_text(encoding="utf-8"))
    report = run_smoke(args.wheel, config["version"])
    summary("Installed and ran the local wheel:\n\n" + json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
