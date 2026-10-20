from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

class ConfigurationError(ValueError):
    """Raised when required local configuration is unavailable or invalid."""


class Settings:
    def __init__(
        self, 
        api_key: str | None = None, 
        connect_timeout_seconds: float = 5.0, 
        read_timeout_seconds: float = 20.0, 
        max_retries: int = 3
    ) -> None:
        self.api_key = api_key or os.getenv("GOOGLE_MAPS_API_KEY")
        if not self.api_key:
            raise ConfigurationError("GOOGLE_MAPS_API_KEY is missing. Please configure it in your .env file.")
        if len(self.api_key) < 20:
            raise ConfigurationError("GOOGLE_MAPS_API_KEY has an unexpected format.")
        self.connect_timeout_seconds = connect_timeout_seconds
        self.read_timeout_seconds = read_timeout_seconds
        self.max_retries = max_retries


def load_settings() -> Settings:
    """Load the Places API configuration from the environment."""
    return Settings()
