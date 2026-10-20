# MapLead Extractor

Professional business-lead discovery with the official **Google Places API (New)**. Search by keyword and location, enrich each discovered place with available business details, and download a clean Excel workbook.

> Google controls search ranking and which business fields are available. A blank phone number or website means that Google did not return that field for the place.

## Features

- Simple web interface with `Start Extraction`, processing feedback, and Excel download.
- Official Google Places Text Search for discovery and Place Details for enrichment.
- Excel export (`full_leads.xlsx`) with Place ID, business name, phone, website, address, Google Maps link, business status, and types.
- Deduplication, validated inputs, request timeouts, retries, and safe provider error messages.
- Atomic CSV export of the discovered Place IDs for traceability.
- Offline automated tests using mocked API requests—no live Google requests required.

## Project structure

```text
MapLead Extractor/
├── server.py          # FastAPI web application and download endpoint
├── main.py            # Optional command-line entry point
├── api_client.py      # Google Places search, details, retries, validation
├── enrich_leads.py    # Excel workbook creation from enriched place details
├── exporter.py        # Atomic Place ID CSV export
├── config.py          # Environment-based API configuration
├── tests/             # Offline unit tests
├── requirements.txt   # Python dependencies
├── .env.example       # API-key configuration template
└── output/            # Local generated files; never commit this directory
```

## Requirements

- Python 3.10+
- Google Cloud project with billing enabled
- **Places API (New)** enabled
- Restricted Google Maps Platform API key

## Installation

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set your real key:

```env
GOOGLE_MAPS_API_KEY=your_api_key_here
```

Never commit or share `.env`.

## Run the web app

```powershell
uvicorn server:app --reload
```

Open `http://127.0.0.1:8000` in your browser. Enter the business keyword, location, and target count, then select **Start Extraction**. When processing finishes, select **Download Excel** to save `full_leads.xlsx`.

## Excel output

The downloaded `full_leads.xlsx` includes a `Leads` worksheet with these columns:

| Column | Description |
| --- | --- |
| `place_id` | Google Place ID |
| `business_name` | Business name returned by Google |
| `phone` | International phone number when available |
| `website` | Business website when available |
| `address` | Formatted business address |
| `maps_link` | Direct Google Maps link |
| `business_status` | Current Google business status |
| `types` | Google place categories |

## Optional command line usage

```powershell
python main.py --keyword "builders" --location "London, UK" --target 25 --enrich
```

The command stores Place IDs in `output/place_ids.csv` and, with `--enrich`, creates `output/full_leads.xlsx`.

## Tests

```powershell
python -m unittest discover -s tests -v
python -m py_compile api_client.py config.py enrich_leads.py exporter.py main.py server.py
```

## Security and operational notes

- Keep targets focused: each search and place-details request can affect quota and billing.
- Restrict the API key in Google Cloud to Places API (New) and appropriate server/IP controls.
- `output/`, `.env`, virtual environments, and Python/test caches are excluded through `.gitignore`.
- Review current Google Maps Platform terms, data-retention requirements, and attribution policies before production use.

## Troubleshooting

| Symptom | Resolution |
| --- | --- |
| API key missing | Create `.env` from `.env.example` and set `GOOGLE_MAPS_API_KEY`. |
| HTTP 401/403 | Verify API enablement, billing, key restrictions, and quota. |
| Excel is not created | Run `pip install -r requirements.txt` to install `openpyxl`. |
| Fewer leads than target | Google may return fewer matching or unique results. |

