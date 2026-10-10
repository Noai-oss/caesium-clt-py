"""Check upstream updates without publishing or changing unrelated settings."""

import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import update_version

CONFIG = {
    "name": "caesium-clt-py",
    "version": "1.9.0",
    "homepage": "https://github.com/Lymphatus/caesium-clt",
    "binaries": {"win_amd64": [{"name": "caesiumclt", "path": "build/test.exe"}]},
}


class UpdateVersionTests(unittest.TestCase):
    def test_updates_only_for_newer_versions(self):
        for version, changed in (
            ("1.10.0", True),
            ("1.9.0.post1", True),
            ("1.9.0", False),
            ("1.8.0", False),
        ):
            with (
                self.subTest(version=version),
                tempfile.TemporaryDirectory() as directory,
            ):
                path = Path(directory) / "wheel.json"
                original = json.dumps(CONFIG, indent=2) + "\n"
                path.write_text(original, encoding="utf-8")
                response = io.BytesIO(json.dumps({"tag_name": f"v{version}"}).encode())
                with patch(
                    "update_version.urllib.request.urlopen", return_value=response
                ) as fetch:
                    self.assertEqual(
                        update_version.update_version(path, token="test-token"), changed
                    )
                fetch.assert_called_once()
                request = fetch.call_args.args[0]
                self.assertEqual(
                    request.full_url,
                    "https://api.github.com/repos/Lymphatus/caesium-clt/releases/latest",
                )
                self.assertEqual(
                    request.get_header("Authorization"), "Bearer test-token"
                )
                expected = {**CONFIG, "version": version} if changed else CONFIG
                self.assertEqual(json.loads(path.read_text(encoding="utf-8")), expected)
                if not changed:
                    self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_invalid_tags_leave_config_unchanged(self):
        for tag in ("release-1.10.0", "vnot-a-version"):
            with self.subTest(tag=tag), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "wheel.json"
                original = json.dumps(CONFIG)
                path.write_text(original, encoding="utf-8")
                response = io.BytesIO(json.dumps({"tag_name": tag}).encode())
                with (
                    patch(
                        "update_version.urllib.request.urlopen", return_value=response
                    ),
                    self.assertRaises(ValueError),
                ):
                    update_version.update_version(path)
                self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_api_error_leaves_config_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wheel.json"
            original = json.dumps(CONFIG)
            path.write_text(original, encoding="utf-8")
            with (
                urllib.error.HTTPError(
                    "https://api.github.com", 503, "Unavailable", {}, io.BytesIO()
                ) as error,
                patch("update_version.urllib.request.urlopen", side_effect=error),
                self.assertRaises(urllib.error.HTTPError),
            ):
                update_version.update_version(path)
            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
