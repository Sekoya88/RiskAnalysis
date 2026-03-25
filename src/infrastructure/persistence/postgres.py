"""Infrastructure — PostgreSQL persistence adapters (reports + RL feedback).

Replaces SQLite for production use. Requires psycopg[binary] and a running
PostgreSQL instance (see docker-compose.yml).
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.domain.services.risk_scoring import compute_feedback_score


def _get_dsn() -> str:
    return os.getenv("DATABASE_URL", "postgresql://risk:riskpass@localhost:5432/riskanalysis")


def _ensure_tables(dsn: str) -> None:
    """Create tables if they don't exist."""
    with psycopg.connect(dsn) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                entity TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                overall_score INTEGER,
                geo_score INTEGER,
                credit_score INTEGER,
                market_score INTEGER,
                esg_score INTEGER,
                report_text TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS report_news (
                id SERIAL PRIMARY KEY,
                report_id TEXT REFERENCES reports(id),
                entity TEXT,
                url TEXT,
                title TEXT,
                source TEXT,
                date TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id SERIAL PRIMARY KEY,
                report_id TEXT REFERENCES reports(id),
                news_url TEXT,
                is_helpful BOOLEAN,
                comments TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        conn.commit()


class PostgresReportRepository:
    """ReportRepositoryPort implementation backed by PostgreSQL."""

    def __init__(self, dsn: str | None = None):
        self._dsn = dsn or _get_dsn()
        _ensure_tables(self._dsn)

    def save_report(
        self,
        report_id: str,
        entity: str,
        scores: dict,
        report_text: str,
        sources: dict,
    ) -> None:
        with psycopg.connect(self._dsn) as conn:
            conn.execute(
                """INSERT INTO reports (id, entity, overall_score, geo_score, credit_score, market_score, esg_score, report_text)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (id) DO NOTHING""",
                (
                    report_id,
                    entity.upper(),
                    scores.get("overall"),
                    scores.get("geopolitical"),
                    scores.get("credit"),
                    scores.get("market"),
                    scores.get("esg"),
                    report_text,
                ),
            )
            if sources and "news" in sources:
                for news in sources["news"]:
                    conn.execute(
                        """INSERT INTO report_news (report_id, entity, url, title, source, date)
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        (report_id, entity.upper(), news.get("url"), news.get("title"), news.get("source"), news.get("date")),
                    )
            conn.commit()

    def get_history_for_entity(self, entity: str) -> list[dict[str, Any]]:
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            rows = conn.execute(
                "SELECT * FROM reports WHERE entity = %s ORDER BY created_at ASC",
                (entity.upper(),),
            ).fetchall()
            # Remap created_at → timestamp for backward compat with app.py
            for row in rows:
                if "created_at" in row:
                    row["timestamp"] = row.pop("created_at").isoformat() if row["created_at"] else None
            return rows


class PostgresFeedbackRepository:
    """FeedbackRepositoryPort implementation backed by PostgreSQL."""

    def __init__(self, dsn: str | None = None):
        self._dsn = dsn or _get_dsn()

    def save_feedback(self, report_id: str, news_url: str, is_helpful: bool, comments: str = "") -> None:
        with psycopg.connect(self._dsn) as conn:
            conn.execute(
                "INSERT INTO feedback (report_id, news_url, is_helpful, comments) VALUES (%s, %s, %s, %s)",
                (report_id, news_url, is_helpful, comments),
            )
            conn.commit()

    def get_source_feedback_score(self, url: str) -> float:
        with psycopg.connect(self._dsn) as conn:
            row = conn.execute(
                "SELECT COUNT(*), SUM(CASE WHEN is_helpful THEN 1 ELSE 0 END) FROM feedback WHERE news_url = %s",
                (url,),
            ).fetchone()
            total, helpful = row if row else (0, 0)
            return compute_feedback_score(total or 0, helpful or 0)

    def list_feedback_votes(self) -> list[tuple[str, bool]]:
        with psycopg.connect(self._dsn) as conn:
            rows = conn.execute(
                "SELECT news_url, is_helpful FROM feedback WHERE news_url IS NOT NULL AND news_url != ''",
            ).fetchall()
            return [(str(r[0]), bool(r[1])) for r in rows]
