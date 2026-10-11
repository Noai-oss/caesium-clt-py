"""Check version parsing and independently decoded compression output."""

import tempfile
import unittest
from pathlib import Path

from packaging.version import Version
from PIL import Image, UnidentifiedImageError

from scripts.common import ROOT
from scripts.smoke import check_image, cli_version


class SmokeTests(unittest.TestCase):
    def test_full_upstream_version_is_preserved(self):
        """Keep post-release versions and reject unrelated CLI output."""
        self.assertEqual(
            cli_version("caesiumclt v1.5.0.post1\n"), Version("1.5.0.post1")
        )
        self.assertEqual(cli_version("caesiumclt 1.5.0\n"), Version("1.5.0"))
        for output in ("1.5.0", "unrelated 1.5.0", "caesiumclt 1.5.0\nerror"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                cli_version(output)

    def test_fixture_can_be_fully_decoded(self):
        """Verify that the checked-in fixture meets the smoke image contract."""
        check_image(ROOT / "tests/fixtures/smoke.png")

    def test_compression_output_must_be_nonempty_valid_png_with_expected_size(self):
        """Reject empty, corrupt, resized, or non-PNG compression results."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.png"
            for content in (b"", b"not an image"):
                path.write_bytes(content)
                with self.assertRaises((ValueError, UnidentifiedImageError)):
                    check_image(path)
            Image.new("RGB", (1, 1)).save(path)
            with self.assertRaises(ValueError):
                check_image(path)
            Image.new("RGB", (32, 24)).save(path, format="JPEG")
            with self.assertRaises(ValueError):
                check_image(path)
