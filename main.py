"""Command-line entry point for MapLead Extractor."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from api_client import PlacesApiClient, PlacesApiError
from config import ConfigurationError, load_settings
from exporter import export_place_ids
from enrich_leads import enrich_from_place_ids

DEFAULT_OUTPUT = Path("output/place_ids.csv")


def parse_args() -> argparse.Namespace:
    """Parse and validate user-controlled search options."""
    parser = argparse.ArgumentParser(
        description="Discover unique Google Places IDs with Places API (New) and auto-enrich full details."
    )
    parser.add_argument("--keyword", required=True, help="Business category or keyword, e.g. builders")
    parser.add_argument("--location", required=True, help="Location, e.g. London, UK")
    parser.add_argument("--target", required=True, type=int, help="Desired unique Place IDs (1-500)")
    parser.add_argument(
        "--phrase",
        action="append",
        default=[],
        help="Optional extra phrase. Repeat the option for multiple phrases.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="CSV output path")
    parser.add_argument(
        "--enrich",
        action="store_true",
        help="Automatically fetch full business details (Name, Phone, Website) using free scraper.",
    )
    args = parser.parse_args()
    if not args.keyword.strip() or not args.location.strip():
        parser.error("--keyword and --location cannot be blank.")
    if not 1 <= args.target <= 500:
        parser.error("--target must be between 1 and 500 to limit cost and request volume.")
    if any(not phrase.strip() for phrase in args.phrase):
        parser.error("--phrase values cannot be blank.")
    return args


def build_queries(keyword: str, location: str, phrases: list[str]) -> list[str]:
    """Build de-duplicated Text Search queries without embedded defaults."""
    variants = [keyword, *phrases]
    queries: list[str] = []
    for variant in variants:
        query = f"{variant.strip()} in {location.strip()}"
        if query not in queries:
            queries.append(query)
    return queries


def extract_leads(
    keyword: str,
    location: str,
    target: int = 10,
    phrases: list[str] | None = None,
    output_path: str | Path = DEFAULT_OUTPUT,
    enrich: bool = False,
) -> Path:
    """
    1-Line Wrapper Function: Import and call directly in any other Python file.
    """
    settings = load_settings()
    queries = build_queries(keyword, location, phrases or [])
    summary = PlacesApiClient(settings).discover_place_ids(queries, target)
    out_file = Path(output_path)
    export_place_ids(summary.place_ids, out_file)
    
    if enrich and summary.place_ids:
        output_full = out_file.parent / "full_leads.xlsx"
        enrich_from_place_ids(input_csv=out_file, output_xlsx=output_full)
        return output_full
        
    return out_file


def main() -> int:
    """Run a compliant search and export deduplicated Place IDs with optional auto-enrichment."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()
    try:
        settings = load_settings()
        queries = build_queries(args.keyword, args.location, args.phrase)
        summary = PlacesApiClient(settings).discover_place_ids(queries, args.target)
        written = export_place_ids(summary.place_ids, args.output)
    except (ConfigurationError, PlacesApiError, OSError, ValueError) as exc:
        logging.error("%s", exc)
        return 1

    print(f"Exported {written} unique Place ID(s) to {args.output}.")
    print("Source: Google Maps. Review Google Maps attribution and Places API policies before displaying results.")
    
    if args.enrich and written > 0:
        print("\n[Auto-Enrich] Starting free scraper to fetch full business details...")
        output_full = args.output.parent / "full_leads.xlsx"
        enrich_from_place_ids(input_csv=args.output, output_xlsx=output_full)
        print(f"[Auto-Enrich] All data successfully saved to Excel file: '{output_full}'!")

    if written < args.target:
        print(
            f"Target not reached: requested {args.target}, found {written}. "
            "Available API results, query relevance, pagination, and deduplication can limit totals."
        )
    print(f"Requests: {summary.pages_requested} page(s) across {summary.queries_attempted} query variant(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

    
