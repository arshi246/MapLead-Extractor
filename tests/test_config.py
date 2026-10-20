"""Offline configuration-validation tests."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from config import ConfigurationError, load_settings


class ConfigurationTests(unittest.TestCase):
    def test_missing_key_fails_without_printing_configuration(self) -> None:
        with patch("config.load_dotenv"), patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": ""}):
            with self.assertRaisesRegex(ConfigurationError, "missing"):
                load_settings()

    def test_obviously_malformed_key_fails(self) -> None:
        with patch("config.load_dotenv"), patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "too short"}):
            with self.assertRaisesRegex(ConfigurationError, "unexpected format"):
                load_settings()
