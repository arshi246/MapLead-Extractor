"""Storage-safe CSV exporting for Place IDs."""

from __future__ import annotations

import csv
import os
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterable


def export_place_ids(place_ids: Iterable[str], output_path: Path) -> int:
    """Write unique Place IDs to CSV and return the number written.

    Google documents Place IDs as exempt from Places content caching restrictions.
    No place names, addresses, ratings, contacts, or other place content is saved.
    """
    unique_ids = sorted(set(place_ids))
    if any(not _is_safe_place_id(place_id) for place_id in unique_ids):
        raise ValueError("Refusing to export an invalid Place ID.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    exported_at = datetime.now(UTC).isoformat()
    temporary_path: Path | None = None
    try:
        # A securely created sibling file plus replace avoids leaving a partial CSV.
        with NamedTemporaryFile(
            mode="w", newline="", encoding="utf-8", dir=output_path.parent,
            prefix=f".{output_path.name}.", suffix=".tmp", delete=False,
        ) as csv_file:
            temporary_path = Path(csv_file.name)
            writer = csv.DictWriter(csv_file, fieldnames=["place_id", "source", "exported_at_utc"])
            writer.writeheader()
            for place_id in unique_ids:
                writer.writerow(
                    {"place_id": place_id, "source": "Google Maps", "exported_at_utc": exported_at}
                )
        os.replace(temporary_path, output_path)
    except OSError:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise
    return len(unique_ids)


def _is_safe_place_id(place_id: object) -> bool:
    """Reject spreadsheet-formula prefixes and non-URL-safe identifier text."""
    return (
        isinstance(place_id, str)
        and 1 <= len(place_id) <= 256
        and place_id.isascii()
        and all(character.isalnum() or character in "-_" for character in place_id)
    )
