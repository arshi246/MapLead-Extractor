"""A minimal, defensive client for Google Places API (New) Text Search."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from math import isfinite
from typing import Any

import requests

from config import Settings

LOGGER = logging.getLogger(__name__)
TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
PLACE_DETAILS_URL = "https://places.googleapis.com/v1/places/{}"
# A Place ID is the only Places response content this program persistently exports.
FIELD_MASK = "places.id,nextPageToken"
PLACE_DETAILS_FIELD_MASK = (
    "id,displayName,formattedAddress,nationalPhoneNumber,internationalPhoneNumber,"
    "websiteUri,googleMapsUri,businessStatus,types"
)
MAX_PAGE_SIZE = 20
MAX_PAGES_PER_QUERY = 3  # Google documents up to 60 Text Search results per query.
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_RETRY_AFTER_SECONDS = 60.0


class PlacesApiError(RuntimeError):
    """A user-safe description of a failed Google Places API request."""


@dataclass(frozen=True)
class SearchSummary:
    """Outcome information useful for the command-line interface."""

    place_ids: list[str]
    queries_attempted: int
    pages_requested: int


class PlacesApiClient:
    """Call Text Search (New) with supported pagination and bounded retries."""

    def __init__(
        self,
        settings: Settings,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        random_value: Callable[[], float] = random.random,
    ) -> None:
        if settings.max_retries < 0:
            raise ValueError("max_retries cannot be negative.")
        if (
            not isfinite(settings.connect_timeout_seconds)
            or not isfinite(settings.read_timeout_seconds)
            or settings.connect_timeout_seconds <= 0
            or settings.read_timeout_seconds <= 0
        ):
            raise ValueError("Timeout values must be finite positive numbers.")
        self._settings = settings
        self._session = session or requests.Session()
        self._sleep = sleep
        self._random_value = random_value

    def discover_place_ids(
        self, queries: Iterable[str], target: int
    ) -> SearchSummary:
        """Search each query until ``target`` distinct Place IDs are found.

        A target is a ceiling, not a promise: the API may return fewer results.
        """
        if not isinstance(target, int) or isinstance(target, bool) or target < 1:
            raise ValueError("target must be a positive integer.")
        seen: set[str] = set()
        pages_requested = 0
        queries_attempted = 0
        for query in queries:
            if len(seen) >= target:
                break
            queries_attempted += 1
            page_token: str | None = None
            for _ in range(MAX_PAGES_PER_QUERY):
                response = self._search_page(query, page_token)
                pages_requested += 1
                places = response.get("places", [])
                if not isinstance(places, list):
                    raise PlacesApiError("Google Places API returned an unexpected response.")
                for place in places:
                    if not isinstance(place, dict):
                        continue
                    place_id = place.get("id")
                    if self._is_safe_place_id(place_id):
                        seen.add(place_id)
                        if len(seen) >= target:
                            break
                if len(seen) >= target:
                    break
                next_token = response.get("nextPageToken")
                if not isinstance(next_token, str) or not next_token:
                    break
                page_token = next_token
        return SearchSummary(sorted(seen), queries_attempted, pages_requested)

    def _search_page(self, query: str, page_token: str | None) -> dict[str, Any]:
        """Request one documented result page, retrying transient failures only."""
        payload: dict[str, Any] = {"textQuery": query, "pageSize": MAX_PAGE_SIZE}
        if page_token:
            payload["pageToken"] = page_token
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self._settings.api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        }
        for attempt in range(self._settings.max_retries + 1):
            try:
                response = self._session.post(
                    TEXT_SEARCH_URL,
                    json=payload,
                    headers=headers,
                    timeout=(
                        self._settings.connect_timeout_seconds,
                        self._settings.read_timeout_seconds,
                    ),
                )
            except requests.RequestException as exc:
                if attempt == self._settings.max_retries:
                    raise PlacesApiError("Network error while contacting Google Places API.") from exc
                self._backoff(attempt)
                continue

            if response.status_code in RETRYABLE_STATUS_CODES:
                if attempt == self._settings.max_retries:
                    raise PlacesApiError(
                        "Google Places API is temporarily unavailable or rate-limited. Try again later."
                    )
                self._backoff(attempt, self._retry_after_seconds(response))
                continue
            if response.status_code >= 400:
                raise PlacesApiError(self._safe_http_error(response.status_code))
            try:
                body = response.json()
            except ValueError as exc:
                raise PlacesApiError("Google Places API returned an unreadable response.") from exc
            if not isinstance(body, dict):
                raise PlacesApiError("Google Places API returned an unexpected response.")
            return body
        raise AssertionError("Retry loop should either return or raise.")

    def get_place_details(self, place_id: str) -> dict[str, str]:
        """Fetch the exportable business details for one known Google Place ID."""
        if not self._is_safe_place_id(place_id):
            raise ValueError("place_id must be a valid Google Place ID.")
        headers = {
            "X-Goog-Api-Key": self._settings.api_key,
            "X-Goog-FieldMask": PLACE_DETAILS_FIELD_MASK,
        }
        url = PLACE_DETAILS_URL.format(place_id)
        for attempt in range(self._settings.max_retries + 1):
            try:
                response = self._session.get(
                    url,
                    headers=headers,
                    timeout=(
                        self._settings.connect_timeout_seconds,
                        self._settings.read_timeout_seconds,
                    ),
                )
            except requests.RequestException as exc:
                if attempt == self._settings.max_retries:
                    raise PlacesApiError("Network error while contacting Google Places API.") from exc
                self._backoff(attempt)
                continue

            if response.status_code in RETRYABLE_STATUS_CODES:
                if attempt == self._settings.max_retries:
                    raise PlacesApiError(
                        "Google Places API is temporarily unavailable or rate-limited. Try again later."
                    )
                self._backoff(attempt, self._retry_after_seconds(response))
                continue
            if response.status_code >= 400:
                raise PlacesApiError(self._safe_http_error(response.status_code))
            try:
                body = response.json()
            except ValueError as exc:
                raise PlacesApiError("Google Places API returned an unreadable response.") from exc
            if not isinstance(body, dict):
                raise PlacesApiError("Google Places API returned an unexpected response.")
            return self._normalise_place_details(place_id, body)
        raise AssertionError("Retry loop should either return or raise.")

    def _backoff(self, attempt: int, retry_after_seconds: float | None = None) -> None:
        """Sleep using capped exponential backoff, jitter, and Retry-After when supplied."""
        calculated_delay = min(8.0, 0.5 * (2**attempt)) + (self._random_value() * 0.25)
        delay = max(calculated_delay, retry_after_seconds or 0.0)
        LOGGER.warning("Transient Places API failure; retrying request (%s/%s).", attempt + 1, self._settings.max_retries)
        self._sleep(delay)

    @staticmethod
    def _is_safe_place_id(place_id: object) -> bool:
        """Allow URL-safe IDs only, preventing spreadsheet-formula CSV injection."""
        return (
            isinstance(place_id, str)
            and 1 <= len(place_id) <= 256
            and place_id.isascii()
            and all(character.isalnum() or character in "-_" for character in place_id)
        )

    @staticmethod
    def _normalise_place_details(place_id: str, place: dict[str, Any]) -> dict[str, str]:
        """Return stable spreadsheet columns even when Google omits optional fields."""
        display_name = place.get("displayName")
        types = place.get("types")
        return {
            "place_id": place_id,
            "business_name": display_name.get("text", "") if isinstance(display_name, dict) else "",
            "phone": str(place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber") or ""),
            "website": str(place.get("websiteUri") or ""),
            "address": str(place.get("formattedAddress") or ""),
            "maps_link": str(place.get("googleMapsUri") or f"https://www.google.com/maps/place/?q=place_id:{place_id}"),
            "business_status": str(place.get("businessStatus") or ""),
            "types": ", ".join(item for item in types if isinstance(item, str)) if isinstance(types, list) else "",
        }

    @staticmethod
    def _retry_after_seconds(response: requests.Response) -> float | None:
        """Parse a bounded Retry-After header without logging provider headers."""
        retry_after = response.headers.get("Retry-After")
        if not retry_after:
            return None
        try:
            seconds = float(retry_after)
        except (TypeError, ValueError):
            try:
                retry_at = parsedate_to_datetime(retry_after)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=UTC)
                seconds = (retry_at - datetime.now(UTC)).total_seconds()
            except (TypeError, ValueError, IndexError, OverflowError):
                return None
        if not isfinite(seconds) or seconds <= 0:
            return None
        return min(seconds, MAX_RETRY_AFTER_SECONDS)

    @staticmethod
    def _safe_http_error(status_code: int) -> str:
        """Map statuses to safe messages without exposing provider response bodies."""
        messages = {
            400: "Google Places API rejected the request. Check the search input.",
            401: "Google Places API authentication failed. Check local API-key configuration.",
            403: "Google Places API access was denied. Check API enablement, restrictions, and billing.",
            404: "Google Places API endpoint was not found.",
        }
        return messages.get(status_code, f"Google Places API request failed (HTTP {status_code}).")
