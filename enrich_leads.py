"""Enrich Google Place IDs with official Places API details and export Excel."""

from __future__ import annotations

import csv
from pathlib import Path

from api_client import PlacesApiClient
from config import load_settings

LEAD_COLUMNS = (
    "place_id",
    "business_name",
    "phone",
    "website",
    "address",
    "maps_link",
    "business_status",
    "types",
)

def enrich_from_place_ids(
    input_csv: str | Path = "output/place_ids.csv",
    output_xlsx: str | Path = "output/full_leads.xlsx",
    client: PlacesApiClient | None = None,
) -> Path:
    input_path = Path(input_csv)
    output_path = Path(output_xlsx)

    if not input_path.exists():
        raise FileNotFoundError(f"{input_path} not found!")

    with input_path.open(newline="", encoding="utf-8") as csv_file:
        place_ids = [row["place_id"] for row in csv.DictReader(csv_file) if row.get("place_id")]

    places_client = client or PlacesApiClient(load_settings())
    data_rows = [places_client.get_place_details(place_id) for place_id in place_ids]
    export_leads_to_excel(data_rows, output_path)
    return output_path


def export_leads_to_excel(data_rows: list[dict[str, str]], output_path: Path) -> Path:
    """Create a readable, consistently shaped Excel workbook for enriched leads."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError as exc:
        raise RuntimeError("Excel export requires openpyxl. Run: pip install -r requirements.txt") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Leads"
    sheet.append(LEAD_COLUMNS)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in data_rows:
        sheet.append([row.get(column, "") for column in LEAD_COLUMNS])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        letter = column[0].column_letter
        sheet.column_dimensions[letter].width = min(
            max(len(str(cell.value or "")) for cell in column) + 2, 50
        )
    workbook.save(output_path)
    return output_path

if __name__ == "__main__":
    enrich_from_place_ids()
