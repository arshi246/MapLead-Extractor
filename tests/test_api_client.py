"""Offline unit tests for the API client."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

import requests

from api_client import (
    FIELD_MASK,
    PLACE_DETAILS_FIELD_MASK,
    PLACE_DETAILS_URL,
    PlacesApiClient,
    PlacesApiError,
    TEXT_SEARCH_URL,
)
from config import Settings


def fake_response(
    status_code: int, payload: object, headers: dict[str, str] | None = None
) -> Mock:
    response = Mock()
    response.status_code = status_code
    response.json.return_value = payload
    response.headers = headers or {}
    return response


class PlacesApiClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = Mock()
        self.client = PlacesApiClient(
            Settings(api_key="x" * 25), session=self.session, sleep=Mock(), random_value=lambda: 0
        )

    def test_follows_page_tokens_and_deduplicates_ids(self) -> None:
        self.session.post.side_effect = [
            fake_response(200, {"places": [{"id": "a"}, {"id": "b"}], "nextPageToken": "next"}),
            fake_response(200, {"places": [{"id": "b"}, {"id": "c"}]}),
        ]
        result = self.client.discover_place_ids(["builders in London"], target=5)
        self.assertEqual(result.place_ids, ["a", "b", "c"])
        self.assertEqual(result.pages_requested, 2)
        first_call = self.session.post.call_args_list[0]
        self.assertEqual(first_call.args[0], TEXT_SEARCH_URL)
        self.assertEqual(first_call.kwargs["headers"]["X-Goog-FieldMask"], FIELD_MASK)
        self.assertEqual(first_call.kwargs["timeout"], (5.0, 20.0))

    def test_retries_rate_limits_with_bounded_backoff(self) -> None:
        sleep = Mock()
        self.client = PlacesApiClient(
            Settings(api_key="x" * 25), session=self.session, sleep=sleep, random_value=lambda: 0
        )
        self.session.post.side_effect = [
            fake_response(429, {}, {"Retry-After": "2"}),
            fake_response(200, {"places": [{"id": "a"}]}),
        ]
        result = self.client.discover_place_ids(["builders in London"], target=1)
        self.assertEqual(result.place_ids, ["a"])
        self.assertEqual(self.session.post.call_count, 2)
        sleep.assert_called_once_with(2.0)

    def test_does_not_retry_permanent_client_errors(self) -> None:
        for status in (400, 401, 403):
            with self.subTest(status=status):
                self.session.post.reset_mock()
                self.session.post.return_value = fake_response(status, {})
                with self.assertRaises(PlacesApiError):
                    self.client.discover_place_ids(["builders in London"], target=1)
                self.assertEqual(self.session.post.call_count, 1)

    def test_retries_5xx_a_bounded_number_of_times(self) -> None:
        sleep = Mock()
        self.client = PlacesApiClient(
            Settings(api_key="x" * 25, max_retries=2),
            session=self.session,
            sleep=sleep,
            random_value=lambda: 0,
        )
        self.session.post.return_value = fake_response(503, {})
        with self.assertRaisesRegex(PlacesApiError, "temporarily unavailable"):
            self.client.discover_place_ids(["builders in London"], target=1)
        self.assertEqual(self.session.post.call_count, 3)
        self.assertEqual(sleep.call_args_list, [unittest.mock.call(0.5), unittest.mock.call(1.0)])

    def test_rejects_malformed_successful_payloads_safely(self) -> None:
        for payload in ([], {"places": "not-a-list"}):
            with self.subTest(payload=payload):
                self.session.post.return_value = fake_response(200, payload)
                with self.assertRaisesRegex(PlacesApiError, "unexpected response"):
                    self.client.discover_place_ids(["builders in London"], target=1)

    def test_ignores_missing_or_unsafe_place_fields(self) -> None:
        self.session.post.return_value = fake_response(
            200,
            {"places": [{}, None, {"id": "=formula"}, {"id": "valid_Id-1"}]},
        )
        result = self.client.discover_place_ids(["builders in London"], target=2)
        self.assertEqual(result.place_ids, ["valid_Id-1"])

    def test_stops_when_next_page_token_is_missing(self) -> None:
        self.session.post.return_value = fake_response(200, {"places": [{"id": "a"}]})
        result = self.client.discover_place_ids(["builders in London"], target=5)
        self.assertEqual(result.pages_requested, 1)
        self.assertEqual(self.session.post.call_count, 1)

    def test_caps_supported_pagination_at_three_pages_per_query(self) -> None:
        self.session.post.side_effect = [
            fake_response(200, {"places": [{"id": "a"}], "nextPageToken": "one"}),
            fake_response(200, {"places": [{"id": "b"}], "nextPageToken": "two"}),
            fake_response(200, {"places": [{"id": "c"}], "nextPageToken": "three"}),
        ]
        result = self.client.discover_place_ids(["builders in London"], target=10)
        self.assertEqual(result.place_ids, ["a", "b", "c"])
        self.assertEqual(result.pages_requested, 3)
        self.assertEqual(self.session.post.call_count, 3)

    def test_does_not_expose_provider_error_body(self) -> None:
        self.session.post.return_value = fake_response(403, {"error": {"message": "secret detail"}})
        with self.assertRaisesRegex(PlacesApiError, "access was denied") as caught:
            self.client.discover_place_ids(["builders in London"], target=1)
        self.assertNotIn("secret detail", str(caught.exception))

    def test_network_failure_after_retries_is_safe(self) -> None:
        self.session.post.side_effect = requests.ConnectionError("credential=do-not-show")
        with self.assertRaisesRegex(PlacesApiError, "Network error") as caught:
            self.client.discover_place_ids(["builders in London"], target=1)
        self.assertNotIn("credential", str(caught.exception))

    def test_timeout_is_retried_and_sanitized(self) -> None:
        self.session.post.side_effect = requests.Timeout("internal details")
        with self.assertRaisesRegex(PlacesApiError, "Network error") as caught:
            self.client.discover_place_ids(["builders in London"], target=1)
        self.assertNotIn("internal details", str(caught.exception))

    def test_invalid_programmatic_target_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive integer"):
            self.client.discover_place_ids(["builders in London"], target=0)

    def test_fetches_and_normalises_place_details(self) -> None:
        self.session.get.return_value = fake_response(
            200,
            {
                "displayName": {"text": "Acme Builders"},
                "internationalPhoneNumber": "+44 20 1234 5678",
                "websiteUri": "https://acme.example",
                "formattedAddress": "1 High Street, London",
                "googleMapsUri": "https://maps.google.com/?cid=1",
                "businessStatus": "OPERATIONAL",
                "types": ["general_contractor", "point_of_interest"],
            },
        )

        result = self.client.get_place_details("valid_Id-1")

        self.assertEqual(result["business_name"], "Acme Builders")
        self.assertEqual(result["phone"], "+44 20 1234 5678")
        self.assertEqual(result["types"], "general_contractor, point_of_interest")
        self.assertEqual(self.session.get.call_args.args[0], PLACE_DETAILS_URL.format("valid_Id-1"))
        self.assertEqual(
            self.session.get.call_args.kwargs["headers"]["X-Goog-FieldMask"],
            PLACE_DETAILS_FIELD_MASK,
        )
