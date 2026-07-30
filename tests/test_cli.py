from __future__ import annotations

import unittest
from unittest.mock import patch

from rtmonitor.cli import main


class CliTests(unittest.TestCase):
    def test_rejects_non_positive_interval(self) -> None:
        with patch("builtins.print") as print_mock:
            exit_code = main(["--interval", "0", "--once"])

        self.assertEqual(exit_code, 2)
        print_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()

