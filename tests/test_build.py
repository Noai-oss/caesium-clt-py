"""Check downloads, version mapping, HTTP errors, wheel contents, and RECORD."""

import base64
import csv
import email
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import patch

import build


class BuildTests(unittest.TestCase):
    def test_prepare_only_redownloads_and_preserves_upstream_version(self):
        target = "x86_64-pc-windows-msvc"
        stem = f"caesiumclt-v1.5.0.post1-{target}"
        blob = io.BytesIO()
        with zipfile.ZipFile(blob, "w") as archive:
            archive.writestr(f"{stem}/caesiumclt.exe", b"original binary")
            archive.writestr(f"{stem}/LICENSE.md", b"original license\r\n")
            archive.writestr(f"{stem}/README.md", b"original readme")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = {
                "version": "1.5.0.post1",
                "homepage": "https://github.com/Lymphatus/caesium-clt",
                "binaries": {
                    "win_amd64": [
                        {"name": "caesiumclt", "path": f"build/{target}/caesiumclt.exe"}
                    ],
                },
            }
            (root / "wheel.json").write_text(json.dumps(config), encoding="utf-8")
            (root / "README.md").write_text("# Test\n", encoding="utf-8")
            with (
                patch("build.ROOT", root),
                patch("sys.argv", ["build.py", "--prepare-only"]),
                patch("build.fetch", return_value=blob.getvalue()) as fetch,
            ):
                build.main()
                build.main()
            self.assertEqual(fetch.call_count, 2)
            fetch.assert_called_with(
                "https://github.com/Lymphatus/caesium-clt/releases/download/"
                f"v1.5.0.post1/{stem}.zip"
            )
            self.assertEqual(
                (root / f"build/{target}/caesiumclt.exe").read_bytes(),
                b"original binary",
            )
            self.assertEqual(
                (root / f"build/{target}/documents/licenses/LICENSE.md").read_bytes(),
                b"original license\r\n",
            )

    def test_selected_target_builds_both_linux_wheels_with_one_download(self):
        target = "x86_64-unknown-linux-musl"
        stem = f"caesiumclt-v1.10.0-{target}"
        blob = io.BytesIO()
        with tarfile.open(fileobj=blob, mode="w:gz") as archive:
            for name in ("caesiumclt", "LICENSE.md", "README.md"):
                content = name.encode()
                member = tarfile.TarInfo(f"{stem}/{name}")
                member.size = len(content)
                archive.addfile(member, io.BytesIO(content))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = json.loads((build.ROOT / "wheel.json").read_text())
            config["version"] = "1.10.0"
            (root / "wheel.json").write_text(json.dumps(config), encoding="utf-8")
            (root / "README.md").write_text("# Test\n", encoding="utf-8")
            output = root / "dist"
            with (
                patch("build.ROOT", root),
                patch(
                    "sys.argv",
                    [
                        "build.py",
                        "--target",
                        target,
                        "--target",
                        target,
                        "--output-dir",
                        str(output),
                    ],
                ),
                patch("build.fetch", return_value=blob.getvalue()) as fetch,
            ):
                build.main()
            fetch.assert_called_once_with(
                "https://github.com/Lymphatus/caesium-clt/releases/download/"
                f"v1.10.0/{stem}.tar.gz"
            )
            self.assertEqual(
                {wheel.name.rsplit("-", 1)[1] for wheel in output.glob("*.whl")},
                {"manylinux_2_17_x86_64.whl", "musllinux_1_2_x86_64.whl"},
            )
            with zipfile.ZipFile(next(output.glob("*.whl"))) as archive:
                metadata = archive.read(
                    next(
                        name
                        for name in archive.namelist()
                        if name.endswith("/METADATA")
                    )
                ).decode()
                self.assertIn("# Test\n", metadata)
                self.assertIn("Version: 1.10.0\n", metadata)
                self.assertIn("/tree/v1.10.0)", metadata)

    def test_fetch_returns_bytes_and_does_not_retry_http_errors(self):
        data = b"original upstream bytes"
        with patch("build.urllib.request.urlopen", return_value=io.BytesIO(data)):
            self.assertEqual(build.fetch("https://example.org/file.tar.gz"), data)
        url = "https://example.org/file.tar.gz"
        with (
            urllib.error.HTTPError(
                url, 503, "Service Unavailable", {}, io.BytesIO()
            ) as error,
            patch(
                "build.urllib.request.urlopen",
                side_effect=error,
            ) as request,
            self.assertRaises(urllib.error.HTTPError),
        ):
            build.fetch(url)
        request.assert_called_once()

    def test_pipeline_preserves_documents_binary_and_valid_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = b"original binary bytes\x00\xff"
            executable = root / "upstream-platform-name"
            executable.write_bytes(binary)
            config = {
                "name": "caesium-clt-py",
                "version": "1.5.0.post1",
                "binaries": {
                    platform: [{"name": "caesiumclt", "path": str(executable)}]
                    for platform in ["manylinux_2_17_x86_64", "win_amd64"]
                },
            }
            config_path = root / "wheel.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            raw = root / "raw"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bin2whl",
                    "--config",
                    str(config_path),
                    "-o",
                    str(raw),
                ],
                check=True,
                capture_output=True,
            )
            documents = root / "documents"
            (documents / "licenses").mkdir(parents=True)
            license_text = b"UPSTREAM LICENSE\r\nunchanged\r\n"
            (documents / "licenses/LICENSE.md").write_bytes(license_text)
            readme_text = "# README\n\nText: not a metadata header.\n"
            output = root / "dist"
            for raw_wheel in raw.glob("*.whl"):
                build.postprocess(raw_wheel, documents, readme_text, output)
            wheels = list(output.glob("*.whl"))
            self.assertEqual(len(wheels), 2)
            for wheel in wheels:
                with self.subTest(wheel=wheel.name), zipfile.ZipFile(wheel) as archive:
                    names = archive.namelist()
                    command = next(name for name in names if ".data/scripts/" in name)
                    suffix = (
                        "/caesiumclt.exe"
                        if "win_amd64" in wheel.name
                        else "/caesiumclt"
                    )
                    self.assertTrue(command.endswith(suffix))
                    self.assertEqual(archive.read(command), binary)
                    self.assertEqual(
                        (archive.getinfo(command).external_attr >> 16) & 0o777, 0o755
                    )
                    license_path = next(
                        name for name in names if name.endswith("/licenses/LICENSE.md")
                    )
                    self.assertEqual(archive.read(license_path), license_text)
                    metadata = email.message_from_bytes(
                        archive.read(
                            next(name for name in names if name.endswith("/METADATA"))
                        )
                    )
                    self.assertEqual(metadata.defects, [])
                    self.assertEqual(metadata.get_payload(), readme_text)
                    self.assertIsNone(metadata.get_all("Requires-Dist"))
                    record_path = next(
                        name for name in names if name.endswith("/RECORD")
                    )
                    rows = list(
                        csv.reader(io.StringIO(archive.read(record_path).decode()))
                    )
                    self.assertEqual({row[0] for row in rows}, set(names))
                    # Every file has a hash and size except RECORD itself.
                    for name, digest, size in rows:
                        if name == record_path:
                            self.assertEqual((digest, size), ("", ""))
                        else:
                            content = archive.read(name)
                            expected = (
                                base64.urlsafe_b64encode(
                                    hashlib.sha256(content).digest()
                                )
                                .rstrip(b"=")
                                .decode()
                            )
                            self.assertEqual(digest, "sha256=" + expected)
                            self.assertEqual(int(size), len(content))


if __name__ == "__main__":
    unittest.main()
