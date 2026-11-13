"""Tests for SQLite storage and HTTP API endpoints."""

import json
import threading
import urllib.request
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path

from src.analyzer import analyze_raw_edital
from src.models import RawEdital
from src.server import create_handler
from src.storage import EditalStorage


def test_storage_and_api_roundtrip(tmp_path: Path):
    db_path = tmp_path / "test.db"
    storage = EditalStorage(db_path)

    raw = RawEdital(
        source_id="pulitzer",
        source_name="Pulitzer Center",
        title="Global Reporting Grants",
        url="https://pulitzercenter.org/grants-fellowships/opportunities-journalists/global-reporting-grants",
        raw_text="Grants for journalists and newsrooms on a rolling basis. Typical award is $5,000.",
    )
    ed = analyze_raw_edital(raw, today=date(2026, 11, 13))
    assert ed is not None
    storage.upsert_many([ed])

    stats = storage.get_stats()
    assert stats["total"] == 1
    assert stats["open_or_rolling"] == 1

    web_dir = Path(__file__).resolve().parent.parent / "web"
    server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(storage, web_dir))
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/editais") as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["count"] == 1
            assert data["items"][0]["title"] == "Global Reporting Grants"

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
            assert resp.status == 200
            html = resp.read().decode("utf-8")
            assert "Radar de Editais" in html
    finally:
        server.shutdown()
        server.server_close()

