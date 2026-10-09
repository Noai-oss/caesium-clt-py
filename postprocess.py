"""Add documents and a PyPI description using the wheel unpack/pack CLI."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def postprocess(wheel: Path, documents: Path, readme: str, output: Path) -> Path:
    """Process a bin2whl wheel with no README body and return the output path."""
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output) as temporary:
        work = Path(temporary)
        # wheel unpack preserves executable permissions from bin2whl.
        subprocess.run(
            [sys.executable, "-m", "wheel", "unpack", str(wheel), "--dest", str(work)],
            check=True,
        )
        unpacked = next(work.iterdir())
        dist_info = next(unpacked.glob("*.dist-info"))
        # Document paths are relative to .dist-info/, e.g. licenses/LICENSE.md.
        shutil.copytree(documents, dist_info, dirs_exist_ok=True)
        # Add the README here: bin2whl 1.0.2 omits the header/body separator.
        metadata = dist_info / "METADATA"
        metadata.write_bytes(
            metadata.read_bytes().rstrip(b"\n")
            + b"\nDescription-Content-Type: text/markdown\n\n"
            + readme.encode("utf-8")
        )
        # wheel pack rebuilds RECORD to include the new and modified files.
        subprocess.run(
            [
                sys.executable,
                "-m",
                "wheel",
                "pack",
                str(unpacked),
                "--dest-dir",
                str(work),
            ],
            check=True,
        )
        result = next(work.glob("*.whl"))
        destination = output / result.name
        # Replace the existing wheel only after packing succeeds.
        result.replace(destination)
    return destination
