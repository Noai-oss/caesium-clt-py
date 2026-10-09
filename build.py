"""Download upstream binaries, build wheels with bin2whl, and add documents."""

import argparse
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from postprocess import postprocess

ROOT = Path(__file__).resolve().parent
COMMAND = "caesiumclt"


def fetch(url: str) -> bytes:
    """Download once without a local cache."""
    request = urllib.request.Request(url, headers={"User-Agent": "caesium-clt-py"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def archive_files(data: bytes) -> dict[str, bytes]:
    """Read ZIP or tar.gz members without extracting paths to disk."""
    stream = io.BytesIO(data)
    if zipfile.is_zipfile(stream):
        with zipfile.ZipFile(stream) as archive:
            return {
                item.filename: archive.read(item)
                for item in archive.infolist()
                if not item.is_dir()
            }
    stream.seek(0)
    with tarfile.open(fileobj=stream, mode="r:gz") as archive:
        return {
            item.name: archive.extractfile(item).read()
            for item in archive
            if item.isfile()
        }


def prepare_target(upstream: str, tag: str, target: str, executable: Path) -> Path:
    """Save unmodified upstream files and return the documents directory."""
    stem = f"{COMMAND}-{tag}-{target}"
    suffix = ".zip" if "windows" in target else ".tar.gz"
    url = f"{upstream}/releases/download/{tag}/{stem}{suffix}"
    print(f"Preparing {target}...", flush=True)
    files = archive_files(fetch(url))
    binary = files[f"{stem}/{COMMAND}" + (".exe" if "windows" in target else "")]
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_bytes(binary)
    documents = executable.parent / "documents"
    (documents / "licenses").mkdir(parents=True, exist_ok=True)
    (documents / "licenses/LICENSE.md").write_bytes(files[f"{stem}/LICENSE.md"])
    (documents / "upstream").mkdir(exist_ok=True)
    (documents / "upstream/README.md").write_bytes(files[f"{stem}/README.md"])
    return documents


def main() -> None:
    config_path = ROOT / "wheel.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    # Each platform has one executable at build/<upstream-target>/<filename>.
    executables = {
        Path(entries[0]["path"]).parent.name: ROOT / entries[0]["path"]
        for entries in config["binaries"].values()
    }
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        action="append",
        choices=executables,
        help="Repeat to select targets; default: all",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Download binaries and prepare documents without building wheels",
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    # Download each target once, even when requested more than once.
    targets = dict.fromkeys(args.target or executables)
    binaries = {
        platform: entries
        for platform, entries in config["binaries"].items()
        if Path(entries[0]["path"]).parent.name in targets
    }
    documents = {}
    upstream = config["homepage"].rstrip("/")
    tag = "v" + config["version"]
    for target in targets:
        documents[target] = prepare_target(upstream, tag, target, executables[target])

    if args.prepare_only:
        print("Prepared binaries and documents in build/.")
        return

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme += (
        f"\nUpstream release: [{tag}]({upstream}/releases/tag/{tag}).\n"
        f"Source: [{tag}]({upstream}/tree/{tag}).\n"
    )

    # Keep raw wheels temporary; only finished wheels reach the output directory.
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        if args.target:
            # This filtered config lives in a temp directory, so use absolute paths.
            selected = {
                **config,
                "binaries": {
                    platform: [
                        {**entry, "path": str(ROOT / entry["path"])}
                        for entry in entries
                    ]
                    for platform, entries in binaries.items()
                },
            }
            config_path = work / "wheel.json"
            config_path.write_text(json.dumps(selected), encoding="utf-8")
        raw = work / "raw"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "bin2whl",
                "--config",
                str(config_path),
                "--output-dir",
                str(raw),
            ],
            check=True,
        )
        for platform, entries in binaries.items():
            wheel = next(raw.glob(f"*-{platform}.whl"))
            target = Path(entries[0]["path"]).parent.name
            print(postprocess(wheel, documents[target], readme, args.output_dir))


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        ValueError,
        tarfile.TarError,
        zipfile.BadZipFile,
        subprocess.CalledProcessError,
    ) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
