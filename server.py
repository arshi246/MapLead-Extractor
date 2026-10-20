from __future__ import annotations

import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field

from api_client import PlacesApiClient, PlacesApiError
from config import Settings
from exporter import export_place_ids
from enrich_leads import enrich_from_place_ids

app = FastAPI(title="MapLead Extractor", version="6.0.0")

class SearchRequest(BaseModel):
    keyword: str = Field(..., min_length=2)
    location: str = Field(..., min_length=2)
    target: int = Field(10, ge=1, le=100)

@app.get("/", response_class=HTMLResponse)
def render_frontend():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MapLead Extractor</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-50 text-slate-800 min-h-screen flex flex-col justify-between font-sans">
        
        <header class="border-b border-slate-200 bg-white sticky top-0 z-50 shadow-sm">
            <div class="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
                <span class="font-extrabold text-xl text-slate-900">MapLead <span class="text-blue-600">Extractor</span></span>
                <span class="text-xs font-semibold text-emerald-700 bg-emerald-100 px-3 py-1 rounded-full">Full Enrichment Ready</span>
            </div>
        </header>

        <main class="max-w-3xl mx-auto px-6 py-10 w-full flex-grow">
            <div class="bg-white border border-slate-200 rounded-2xl p-8 shadow-xl shadow-blue-500/5">
                <h1 class="text-2xl font-extrabold text-slate-900 mb-2">Business Lead Discovery & Enrichment</h1>
                <p class="text-slate-500 text-sm mb-6">Extracts leads and saves complete details (Name, Phone, Address, Website) into Excel.</p>

                <div class="space-y-4">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label class="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1.5">Business Keyword</label>
                            <input type="text" id="keyword" placeholder="e.g. builders" class="w-full bg-slate-50 border border-slate-300 rounded-xl px-4 py-3 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:bg-white transition-all">
                        </div>
                        <div>
                            <label class="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1.5">Target Location</label>
                            <input type="text" id="location" placeholder="e.g. London, UK" class="w-full bg-slate-50 border border-slate-300 rounded-xl px-4 py-3 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:bg-white transition-all">
                        </div>
                    </div>

                    <div>
                        <label class="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1.5">Target Count</label>
                        <input type="number" id="target" value="10" min="1" max="100" class="w-full bg-slate-50 border border-slate-300 rounded-xl px-4 py-3 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:bg-white transition-all">
                    </div>

                    <button onclick="runSearch()" id="submitBtn" class="w-full mt-2 bg-blue-600 hover:bg-blue-700 text-white font-bold py-3.5 px-6 rounded-xl transition-all shadow-lg shadow-blue-600/30 flex items-center justify-center space-x-2 cursor-pointer">
                        Start Extraction
                    </button>
                </div>

                <div id="resultsContainer" class="hidden mt-8 pt-6 border-t border-slate-100">
                    <div class="flex items-center justify-between mb-4">
                        <h3 id="resultTitle" class="text-sm font-bold text-slate-800">Extraction Complete</h3>
                        <a id="downloadBtn" href="#" class="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold px-4 py-2.5 rounded-xl transition-colors shadow-md flex items-center space-x-1.5">
                            <span>Download Excel</span>
                        </a>
                    </div>
                    <div id="resultBox" class="bg-slate-900 text-emerald-400 border border-slate-800 rounded-xl p-4 font-mono text-xs h-40 overflow-y-auto whitespace-pre-wrap shadow-inner"></div>
                </div>

                <div id="errorBox" class="hidden mt-6 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-xs font-medium"></div>
            </div>
        </main>

        <footer class="border-t border-slate-200 py-6 text-center text-xs text-slate-500 bg-white">
            MapLead Extractor Pro
        </footer>

        <script>
            async function runSearch() {
                const keyword = document.getElementById('keyword').value.trim();
                const location = document.getElementById('location').value.trim();
                const target = parseInt(document.getElementById('target').value) || 10;
                
                const btn = document.getElementById('submitBtn');
                const resultsContainer = document.getElementById('resultsContainer');
                const resultBox = document.getElementById('resultBox');
                const errorBox = document.getElementById('errorBox');
                
                errorBox.classList.add('hidden');
                resultsContainer.classList.add('hidden');

                if (!keyword || !location) {
                    errorBox.innerText = "Please enter both keyword and location.";
                    errorBox.classList.remove('hidden');
                    return;
                }

                btn.disabled = true;
                btn.innerText = "Processing...";

                try {
                    const response = await fetch('/api/search', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ keyword, location, target })
                    });
                    const data = await response.json();
                    if (!response.ok) throw new Error(data.detail);

                    document.getElementById('resultTitle').innerText = `Success! Enriched ${data.count} Leads.`;
                    resultBox.innerText = "Excel file is ready with business name, phone, website, address, Maps link, status, and types.\\n\\nProcessed Place IDs:\\n" + JSON.stringify(data.place_ids, null, 2);
                    document.getElementById('downloadBtn').href = data.download_url;
                    resultsContainer.classList.remove('hidden');
                } catch (err) {
                    errorBox.innerText = "Error: " + err.message;
                    errorBox.classList.remove('hidden');
                } finally {
                    btn.disabled = false;
                    btn.innerText = "Start Extraction";
                }
            }
        </script>
    </body>
    </html>
    """

@app.post("/api/search")
def execute_search(payload: SearchRequest):
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="API key is missing in server environment.")
    try:
        settings = Settings(api_key=api_key)
        client = PlacesApiClient(settings)
        queries = [f"{payload.keyword} in {payload.location}"]
        
        result = client.discover_place_ids(queries, target=payload.target)
        
        output_dir = Path("output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        csv_path = output_dir / "place_ids.csv"
        export_place_ids(result.place_ids, csv_path)
        
        excel_path = output_dir / "full_leads.xlsx"
        enrich_from_place_ids(input_csv=csv_path, output_xlsx=excel_path, client=client)
        
        return {
            "success": True,
            "count": len(result.place_ids),
            "place_ids": result.place_ids,
            "download_url": "/api/download"
        }
    except PlacesApiError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/api/download")
def download_excel():
    file_path = Path("output/full_leads.xlsx")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Excel file not found.")
    return FileResponse(file_path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename="full_leads.xlsx")
