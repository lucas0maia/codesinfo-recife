"""Collection pipeline orchestrating connectors, programmatic analysis, and storage."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

from .analyzer import analyze_raw_edital
from .connectors import build_default_connectors
from .connectors.base import BaseConnector
from .models import Edital
from .storage import EditalStorage


def run_collection(
    storage: EditalStorage,
    connectors: List[BaseConnector] | None = None,
    max_workers: int = 6,
) -> Dict[str, Any]:
    """Run all connectors in parallel, analyze results programmatically, and persist."""
    active_connectors = connectors or build_default_connectors()
    report: Dict[str, Any] = {
        "sources": {},
        "raw_total": 0,
        "accepted_total": 0,
        "filtered_noise": 0,
    }

    analyzed_by_id: Dict[str, Edital] = {}

    def _run_one(conn: BaseConnector):
        items = conn.fetch()
        return conn.source_id, conn.source_name, items

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_run_one, c): c for c in active_connectors}
        for fut in as_completed(futures):
            conn = futures[fut]
            try:
                src_id, src_name, raw_items = fut.result()
                accepted = 0
                noise = 0
                for raw in raw_items:
                    edital = analyze_raw_edital(raw)
                    if edital is None:
                        noise += 1
                        continue
                    analyzed_by_id[edital.id] = edital
                    accepted += 1

                report["raw_total"] += len(raw_items)
                report["accepted_total"] += accepted
                report["filtered_noise"] += noise
                report["sources"][src_id] = {
                    "name": src_name,
                    "status": "ok",
                    "raw": len(raw_items),
                    "accepted": accepted,
                    "filtered_noise": noise,
                }
            except Exception as exc:
                report["sources"][conn.source_id] = {
                    "name": conn.source_name,
                    "status": "error",
                    "error": str(exc),
                }

    storage.upsert_many(list(analyzed_by_id.values()))
    report["stored_unique"] = len(analyzed_by_id)
    return report
