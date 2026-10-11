"""Check candidate validation and failure atomicity of upstream updates."""

import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from scripts import update_version
from scripts.common import ROOT

CONFIG = json.loads((ROOT / "wheel.json").read_text())
CONFIG["version"] = "1.9.0"


def release(version="1.10.0"):
    """Create a latest-release response with every configured asset ready."""
    tag = "v" + version
    return {
        "tag_name": tag,
        "assets": [
            {"name": name, "size": 1024, "state": "uploaded"}
            for name in update_version.asset_names(CONFIG, tag)
        ],
    }


class UpstreamAPITests(unittest.TestCase):
    def test_json_request_uses_timeout_and_optional_token(self):
        """Fetch one JSON object with a timeout and optional authentication."""
        for token in (None, "secret"):
            with (
                self.subTest(token=token),
                patch(
                    "scripts.update_version.urllib.request.urlopen",
                    return_value=io.BytesIO(b'{"ok":true}'),
                ) as request,
            ):
                self.assertEqual(
                    update_version.get_json("https://example.org", token), {"ok": True}
                )
            request.assert_called_once()
            self.assertEqual(request.call_args.kwargs, {"timeout": 30})
            self.assertEqual(
                request.call_args.args[0].get_header("Authorization"),
                f"Bearer {token}" if token else None,
            )

    def test_http_errors_propagate_without_retry(self):
        """Report missing resources, rate limits, and server failures directly."""
        for code in (401, 403, 404, 429, 503):
            with (
                self.subTest(code=code),
                urllib.error.HTTPError(
                    "https://example.org", code, "error", {}, io.BytesIO()
                ) as error,
                patch(
                    "scripts.update_version.urllib.request.urlopen",
                    side_effect=error,
                ) as request,
                self.assertRaises(urllib.error.HTTPError),
            ):
                update_version.get_json("https://example.org")
            request.assert_called_once()

    def test_invalid_response_is_rejected(self):
        """Require valid JSON with an object at the response root."""
        for body, error in ((b"error", json.JSONDecodeError), (b"[]", TypeError)):
            with (
                self.subTest(body=body),
                patch(
                    "scripts.update_version.urllib.request.urlopen",
                    return_value=io.BytesIO(body),
                ),
                self.assertRaises(error),
            ):
                update_version.get_json("https://example.org")

    def test_repository_parsing_requires_github_homepage(self):
        """Extract owner/repo while rejecting unrelated hosts and URL shapes."""
        self.assertEqual(
            update_version.upstream_repository("https://github.com/owner/repo/"),
            "owner/repo",
        )
        for url in (
            "https://github.com.example/owner/repo",
            "http://github.com/owner/repo",
            "https://github.com/owner/repo?query=1",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                update_version.upstream_repository(url)

    def test_targets_are_deduplicated_and_assets_use_archive_suffixes(self):
        """Share one Linux archive across wheels and use ZIP for Windows."""
        linux = [
            {"name": "caesiumclt", "path": "build/x86_64-unknown-linux-musl/caesiumclt"}
        ]
        config = {
            "binaries": {
                "manylinux_2_17_x86_64": linux,
                "musllinux_1_2_x86_64": linux,
                "win_amd64": [
                    {
                        "name": "caesiumclt",
                        "path": "build/x86_64-pc-windows-msvc/caesiumclt.exe",
                    }
                ],
            }
        }
        self.assertEqual(
            update_version.asset_names(config, "v1.9.0"),
            [
                "caesiumclt-v1.9.0-x86_64-pc-windows-msvc.zip",
                "caesiumclt-v1.9.0-x86_64-unknown-linux-musl.tar.gz",
            ],
        )


class UpdateVersionTests(unittest.TestCase):
    def run_update(self, response, expected=None):
        """Check update results against a fake API response and temporary files.

        With expected=None, require a validation error and unchanged files.
        Otherwise check the returned change flag, configuration, and PR report.
        """
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "wheel.json"
            original = json.dumps(CONFIG, indent=2) + "\n"
            path.write_text(original, encoding="utf-8")
            report = Path(temporary) / "report.md"
            with (
                patch.object(update_version, "get_json", return_value=response) as get,
                patch.object(update_version, "outputs"),
            ):
                if expected is None:
                    with self.assertRaises((ValueError, KeyError)):
                        update_version.update_version(path, "test-token", report)
                    self.assertEqual(path.read_text(), original)
                    self.assertFalse(report.exists())
                    return
                changed = update_version.update_version(path, "test-token", report)
            self.assertEqual(changed, expected)
            get.assert_called_once_with(
                "https://api.github.com/repos/Lymphatus/caesium-clt/releases/latest",
                "test-token",
            )
            if expected:
                version = response["tag_name"][1:]
                self.assertEqual(
                    json.loads(path.read_text()), {**CONFIG, "version": version}
                )
                self.assertEqual(
                    path.read_text(),
                    original.replace('"version": "1.9.0"', f'"version": "{version}"'),
                )
                body = report.read_text()
                self.assertIn(f"releases/tag/v{version}", body)
            else:
                self.assertEqual(path.read_text(), original)
                self.assertFalse(report.exists())

    def test_complete_new_release_changes_only_version(self):
        """Accept newer releases, including post releases, without other config edits."""
        for version in ("1.10.0", "1.9.0.post1"):
            with self.subTest(version=version):
                self.run_update(release(version), True)

    def test_older_or_equal_release_does_not_need_assets(self):
        """Skip unchanged or older releases before inspecting their asset lists."""
        for version in ("1.9.0", "1.8.0"):
            candidate = release(version)
            candidate.pop("assets")
            with self.subTest(version=version):
                self.run_update(candidate, False)

    def test_invalid_or_noncanonical_tags_leave_config_unchanged(self):
        """Reject malformed tags without normalizing or persisting their versions."""
        for tag in (
            "release-1.10.0",
            "vv1.10.0",
            "vno-version",
            "v01.10.0",
            "v1.10.0-1",
            "v1.10.0\n",
        ):
            candidate = release()
            candidate["tag_name"] = tag
            with self.subTest(tag=tag):
                self.run_update(candidate)

    def test_missing_duplicate_empty_or_pending_asset_leaves_config_unchanged(self):
        """Prevent an update unless all required assets are uniquely ready."""
        for fault in ("missing", "duplicate", "empty", "pending"):
            candidate = release()
            if fault == "missing":
                candidate["assets"].pop()
            elif fault == "duplicate":
                candidate["assets"].append(candidate["assets"][0])
            elif fault == "empty":
                candidate["assets"][0]["size"] = 0
            else:
                candidate["assets"][0]["state"] = "starter"
            with self.subTest(fault=fault):
                self.run_update(candidate)

    def test_unrelated_assets_are_allowed(self):
        """Allow extra release assets that are not needed to build the wheels."""
        candidate = release()
        candidate["assets"].append(
            {"name": "checksums.txt", "size": 100, "state": "uploaded"}
        )
        self.run_update(candidate, True)

    def test_api_failure_leaves_config_unchanged(self):
        """Propagate an upstream timeout without rewriting the configuration."""
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "wheel.json"
            original = json.dumps(CONFIG)
            path.write_text(original)
            with (
                patch.object(update_version, "get_json", side_effect=TimeoutError),
                self.assertRaises(TimeoutError),
            ):
                update_version.update_version(path)
            self.assertEqual(path.read_text(), original)


if __name__ == "__main__":
    unittest.main()
