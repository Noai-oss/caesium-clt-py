"""Check version ordering, API failures, and GitHub Actions outputs."""

import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import check_version

CONFIG = {
    "name": "caesium-clt-py",
    "version": "1.6.0",
}


class CheckVersionTests(unittest.TestCase):
    def test_version_ordering_uses_config_and_only_queries_pypi(self):
        for configured, published, expected in (
            ("1.10.0", "1.9.0", "true"),
            ("1.5.0", "1.5.0", "false"),
            ("1.5.0", "1.6.0", "false"),
            ("1.5.0.post1", "1.5.0", "true"),
        ):
            with self.subTest(configured=configured, published=published):
                with patch(
                    "check_version.get_json",
                    return_value={"info": {"version": published}},
                ) as get_json:
                    result = check_version.check_version(
                        {**CONFIG, "version": configured}
                    )
                self.assertEqual(result["version"], configured)
                self.assertEqual(result["needs_publish"], expected)
                get_json.assert_called_once_with(
                    "https://pypi.org/pypi/caesium-clt-py/json"
                )

    def test_only_pypi_404_is_treated_as_an_unpublished_project(self):
        url = "https://pypi.org/pypi/caesium-clt-py/json"
        with patch(
            "check_version.get_json",
            side_effect=urllib.error.HTTPError(url, 404, "Not Found", {}, io.BytesIO()),
        ):
            result = check_version.check_version(CONFIG)
        self.assertEqual(result["published_version"], "")
        self.assertEqual(result["needs_publish"], "true")

        for code in (403, 503):
            with (
                self.subTest(code=code),
                urllib.error.HTTPError(url, code, "Error", {}, io.BytesIO()) as error,
                patch(
                    "check_version.get_json",
                    side_effect=error,
                ),
                self.assertRaises(urllib.error.HTTPError),
            ):
                check_version.check_version(CONFIG)

    def test_main_appends_github_outputs_without_changing_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = root / "wheel.json"
            contents = json.dumps(CONFIG)
            config_path.write_text(contents, encoding="utf-8")
            output = root / "output"
            output.write_text("existing=value\n", encoding="utf-8")
            with (
                patch("check_version.ROOT", root),
                patch.dict(os.environ, {"GITHUB_OUTPUT": str(output)}),
                patch(
                    "check_version.get_json",
                    return_value={"info": {"version": "1.5.0"}},
                ),
            ):
                check_version.main()
            self.assertEqual(config_path.read_text(encoding="utf-8"), contents)
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                "existing=value\nversion=1.6.0\npublished_version=1.5.0\nneeds_publish=true\n",
            )


if __name__ == "__main__":
    unittest.main()
