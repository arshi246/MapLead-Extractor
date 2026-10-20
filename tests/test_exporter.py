"""Offline tests for atomic, UTF-8 CSV exports."""

from __future__ import annotations

import io
import unittest
from pathlib import Path
from unittest.mock import patch

from exporter import export_place_ids


class FakeTemporaryFile(io.StringIO):
    """In-memory context manager matching the part of NamedTemporaryFile we use."""

    name = "safe-temporary.csv"

    def __enter__(self) -> "FakeTemporaryFile":
        return self

    def __exit__(self, *args: object) -> None:
        return None


class ExporterTests(unittest.TestCase):
    def test_writes_utf8_deduplicated_csv_atomically(self) -> None:
        temporary_file = FakeTemporaryFile()
        output = Path("output/ids.csv")
        with (
            patch("exporter.NamedTemporaryFile", return_value=temporary_file) as create_temp,
            patch("exporter.os.replace") as replace,
            patch.object(Path, "mkdir") as mkdir,
        ):
            count = export_place_ids(["z", "a", "z"], output)

        self.assertEqual(count, 2)
        self.assertIn("place_id,source,exported_at_utc", temporary_file.getvalue())
        self.assertIn("a,Google Maps,", temporary_file.getvalue())
        self.assertNotIn("z,Google Maps,\nz,Google Maps,", temporary_file.getvalue())
        self.assertEqual(create_temp.call_args.kwargs["encoding"], "utf-8")
        replace.assert_called_once_with(Path("safe-temporary.csv"), output)
        mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_surfaces_file_write_failures(self) -> None:
        with patch("exporter.NamedTemporaryFile", side_effect=PermissionError("denied")):
            with self.assertRaises(OSError):
                export_place_ids(["a"], Path("output/ids.csv"))

    def test_rejects_spreadsheet_formula_ids(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid Place ID"):
            export_place_ids(["=HYPERLINK(\"https://example.test\")"], Path("output/ids.csv"))
