from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rtmonitor.desktop import _database_url, build_parser


class DesktopLauncherTests(unittest.TestCase):
    def test_database_url_targets_data_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_directory = Path(temporary_directory)
            database_url = _database_url(data_directory)

        self.assertTrue(database_url.startswith("sqlite+aiosqlite:///"))
        self.assertTrue(database_url.endswith("/rtmonitor.db"))

    def test_parser_defaults_to_valid_runtime_settings(self) -> None:
        args = build_parser().parse_args([])

        self.assertEqual(args.port, 8765)
        self.assertEqual(args.collection_interval, 5.0)
        self.assertFalse(args.no_browser)
        self.assertFalse(args.no_collector)

    def test_parser_accepts_headless_collection_settings(self) -> None:
        args = build_parser().parse_args(
            [
                "--no-browser",
                "--no-collector",
                "--port",
                "9000",
                "--collection-interval",
                "10",
            ]
        )

        self.assertTrue(args.no_browser)
        self.assertTrue(args.no_collector)
        self.assertEqual(args.port, 9000)
        self.assertEqual(args.collection_interval, 10.0)


if __name__ == "__main__":
    unittest.main()
