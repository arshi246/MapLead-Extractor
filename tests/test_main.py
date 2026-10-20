"""Tests for input/query helpers that do not call external services."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from main import build_queries, parse_args


class QueryBuilderTests(unittest.TestCase):
    def test_builds_unique_dynamic_queries(self) -> None:
        self.assertEqual(
            build_queries("builders", "London", ["renovation builders", "builders"]),
            ["builders in London", "renovation builders in London"],
        )

    def test_rejects_empty_command_line_values(self) -> None:
        for arguments in (
            ["--keyword", "", "--location", "London", "--target", "1"],
            ["--keyword", "builders", "--location", " ", "--target", "1"],
            ["--keyword", "builders", "--location", "London", "--target", "0"],
            ["--keyword", "builders", "--location", "London", "--target", "501"],
        ):
            with self.subTest(arguments=arguments), patch("sys.argv", ["main.py", *arguments]):
                with self.assertRaises(SystemExit):
                    parse_args()
