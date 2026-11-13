"""SQLite storage repository for mapped editais."""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import Edital


class EditalStorage:
    """Manages persistence and querying of editais in SQLite."""

    def __init__(self, db_path: str | Path = "data/editais.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS editais (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    source_url TEXT,
                    organizer TEXT NOT NULL,
                    is_transversal INTEGER NOT NULL,
                    primary_area TEXT NOT NULL,
                    areas_json TEXT NOT NULL,
                    eligibility_json TEXT NOT NULL,
                    deadline_raw TEXT,
                    deadline_iso TEXT,
                    status TEXT NOT NULL,
                    value_raw TEXT,
                    relevance_score INTEGER NOT NULL,
                    journalism_fit_tips_json TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    published_at TEXT,
                    collected_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_editais_status ON editais(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_editais_area ON editais(primary_area)"
            )
            cols = {r[1] for r in conn.execute("PRAGMA table_info(editais)")}
            if "source_url" not in cols:
                conn.execute("ALTER TABLE editais ADD COLUMN source_url TEXT")

    def upsert_many(self, editais: List[Edital]) -> int:
        """Insert or update editais by unique ID/URL. Returns count of processed rows."""
        if not editais:
            return 0
        with self._connect() as conn:
            for e in editais:
                conn.execute(
                    """
                    INSERT INTO editais (
                        id, source_id, source_name, title, url, source_url, organizer,
                        is_transversal, primary_area, areas_json, eligibility_json,
                        deadline_raw, deadline_iso, status, value_raw,
                        relevance_score, journalism_fit_tips_json, summary,
                        published_at, collected_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        title=excluded.title,
                        url=excluded.url,
                        source_url=excluded.source_url,
                        organizer=excluded.organizer,
                        is_transversal=excluded.is_transversal,
                        primary_area=excluded.primary_area,
                        areas_json=excluded.areas_json,
                        eligibility_json=excluded.eligibility_json,
                        deadline_raw=excluded.deadline_raw,
                        deadline_iso=excluded.deadline_iso,
                        status=excluded.status,
                        value_raw=excluded.value_raw,
                        relevance_score=excluded.relevance_score,
                        journalism_fit_tips_json=excluded.journalism_fit_tips_json,
                        summary=excluded.summary,
                        published_at=excluded.published_at,
                        collected_at=excluded.collected_at
                    """,
                    (
                        e.id,
                        e.source_id,
                        e.source_name,
                        e.title,
                        e.url,
                        e.source_url,
                        e.organizer,
                        1 if e.is_transversal else 0,
                        e.primary_area,
                        json.dumps(e.areas, ensure_ascii=False),
                        json.dumps(e.eligibility, ensure_ascii=False),
                        e.deadline_raw,
                        e.deadline_iso,
                        e.status,
                        e.value_raw,
                        e.relevance_score,
                        json.dumps(e.journalism_fit_tips, ensure_ascii=False),
                        e.summary,
                        e.published_at,
                        e.collected_at,
                    ),
                )
        return len(editais)

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "source_id": row["source_id"],
            "source_name": row["source_name"],
            "title": row["title"],
            "url": row["url"],
            "source_url": row["source_url"] or row["url"],
            "organizer": row["organizer"],
            "is_transversal": bool(row["is_transversal"]),
            "primary_area": row["primary_area"],
            "areas": json.loads(row["areas_json"]),
            "eligibility": json.loads(row["eligibility_json"]),
            "deadline_raw": row["deadline_raw"],
            "deadline_iso": row["deadline_iso"],
            "status": row["status"],
            "value_raw": row["value_raw"],
            "relevance_score": row["relevance_score"],
            "journalism_fit_tips": json.loads(row["journalism_fit_tips_json"]),
            "summary": row["summary"],
            "published_at": row["published_at"],
            "collected_at": row["collected_at"],
        }

    def list_editais(
        self,
        status: Optional[str] = None,
        area: Optional[str] = None,
        source_id: Optional[str] = None,
        q: Optional[str] = None,
        exclude_closed: bool = False,
    ) -> List[Dict[str, Any]]:
        """Query editais with optional filters, ordered by relevance and publication date."""
        clauses: List[str] = []
        params: List[Any] = []

        if status:
            clauses.append("status = ?")
            params.append(status)
        elif exclude_closed:
            clauses.append("status != 'encerrado'")

        if area:
            clauses.append("(primary_area = ? OR areas_json LIKE ?)")
            params.extend([area, f'%"{area}"%'])

        if source_id:
            clauses.append("source_id = ?")
            params.append(source_id)

        if q:
            clauses.append("(LOWER(title) LIKE ? OR LOWER(summary) LIKE ? OR LOWER(organizer) LIKE ?)")
            term = f"%{q.lower()}%"
            params.extend([term, term, term])

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT * FROM editais
            {where_sql}
            ORDER BY
                CASE status
                    WHEN 'aberto' THEN 1
                    WHEN 'fluxo_continuo' THEN 2
                    WHEN 'verificar_prazo' THEN 3
                    ELSE 4
                END,
                relevance_score DESC,
                published_at DESC
        """
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_stats(self) -> Dict[str, Any]:
        """Return aggregated dashboard KPIs."""
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM editais").fetchone()[0]
            by_status = {
                r["status"]: r["cnt"]
                for r in conn.execute("SELECT status, COUNT(*) AS cnt FROM editais GROUP BY status")
            }
            by_area = {
                r["primary_area"]: r["cnt"]
                for r in conn.execute(
                    "SELECT primary_area, COUNT(*) AS cnt FROM editais GROUP BY primary_area ORDER BY cnt DESC"
                )
            }
            by_source = {
                r["source_name"]: r["cnt"]
                for r in conn.execute(
                    "SELECT source_name, COUNT(*) AS cnt FROM editais GROUP BY source_name ORDER BY cnt DESC"
                )
            }
            transversal = conn.execute("SELECT COUNT(*) FROM editais WHERE is_transversal = 1").fetchone()[0]
            direct = conn.execute("SELECT COUNT(*) FROM editais WHERE is_transversal = 0").fetchone()[0]

        return {
            "total": total,
            "open_or_rolling": by_status.get("aberto", 0) + by_status.get("fluxo_continuo", 0),
            "transversal_count": transversal,
            "journalism_direct_count": direct,
            "by_status": by_status,
            "by_area": by_area,
            "by_source": by_source,
        }
