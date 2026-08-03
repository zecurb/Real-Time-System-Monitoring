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

    def test_parser_defaults_to_valid_port(self) -> None:
        args = build_parser().parse_args([])

        self.assertEqual(args.port, 8765)
        self.assertFalse(args.no_browser)

    def test_parser_accepts_headless_mode(self) -> None:
        args = build_parser().parse_args(["--no-browser", "--port", "9000"])

        self.assertTrue(args.no_browser)
        self.assertEqual(args.port, 9000)


if __name__ == "__main__":
    unittest.main()
