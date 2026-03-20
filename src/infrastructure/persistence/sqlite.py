"""Infrastructure — SQLite persistence adapters (reports + RL feedback)."""

from __future__ import annotations

import os
import sqlite3
from typing import Any

from src.domain.services.risk_scoring import compute_feedback_score


class SQLiteReportRepository:
    """ReportRepositoryPort implementation backed by SQLite."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._ensure_tables()

    def _connect(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        return sqlite3.connect(self._db_path)

    def _ensure_tables(self) -> None:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                entity TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                overall_score INTEGER,
                geo_score INTEGER,
                credit_score INTEGER,
                market_score INTEGER,
                esg_score INTEGER,
                report_text TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS report_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id TEXT,
                entity TEXT,
                url TEXT,
                title TEXT,
                source TEXT,
                date TEXT,
                FOREIGN KEY (report_id) REFERENCES reports (id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id TEXT,
                news_url TEXT,
                is_helpful BOOLEAN,
                comments TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (report_id) REFERENCES reports (id)
            )
        """)
        conn.commit()
        conn.close()

    def save_report(
        self,
        report_id: str,
        entity: str,
        scores: dict,
        report_text: str,
        sources: dict,
    ) -> None:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO reports (id, entity, overall_score, geo_score, credit_score, market_score, esg_score, report_text)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
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
                cursor.execute(
                    """INSERT INTO report_news (report_id, entity, url, title, source, date)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (report_id, entity.upper(), news.get("url"), news.get("title"), news.get("source"), news.get("date")),
                )
        conn.commit()
        conn.close()

    def get_history_for_entity(self, entity: str) -> list[dict[str, Any]]:
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reports WHERE entity = ? ORDER BY timestamp ASC", (entity.upper(),))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]


class SQLiteFeedbackRepository:
    """FeedbackRepositoryPort implementation backed by SQLite."""

    def __init__(self, db_path: str):
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def save_feedback(self, report_id: str, news_url: str, is_helpful: bool, comments: str = "") -> None:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO feedback (report_id, news_url, is_helpful, comments) VALUES (?, ?, ?, ?)",
            (report_id, news_url, is_helpful, comments),
        )
        conn.commit()
        conn.close()

    def get_source_feedback_score(self, url: str) -> float:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*), SUM(CASE WHEN is_helpful THEN 1 ELSE 0 END) FROM feedback WHERE news_url = ?",
            (url,),
        )
        total, helpful = cursor.fetchone()
        conn.close()
        return compute_feedback_score(total or 0, helpful or 0)
