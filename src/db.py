import sqlite3
import os
import json
from datetime import datetime
from typing import Dict, List, Any

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "risk_history.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Reports table
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
    
    # News used in reports
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
    
    # User feedback for RL loop
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

def save_report(report_id: str, entity: str, scores: Dict[str, int], report_text: str, sources: Dict[str, List[Any]]):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Insert report
    cursor.execute("""
        INSERT INTO reports (id, entity, overall_score, geo_score, credit_score, market_score, esg_score, report_text)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        report_id,
        entity.upper(),
        scores.get('overall'),
        scores.get('geopolitical'),
        scores.get('credit'),
        scores.get('market'),
        scores.get('esg'),
        report_text
    ))
    
    # Insert news
    if sources and "news" in sources:
        for news in sources["news"]:
            cursor.execute("""
                INSERT INTO report_news (report_id, entity, url, title, source, date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                report_id,
                entity.upper(),
                news.get("url"),
                news.get("title"),
                news.get("source"),
                news.get("date")
            ))
            
    conn.commit()
    conn.close()

def get_history_for_entity(entity: str) -> List[Dict[str, Any]]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM reports WHERE entity = ? ORDER BY timestamp ASC
    """, (entity.upper(),))
    
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def save_feedback(report_id: str, news_url: str, is_helpful: bool, comments: str = ""):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO feedback (report_id, news_url, is_helpful, comments)
        VALUES (?, ?, ?, ?)
    """, (report_id, news_url, is_helpful, comments))
    conn.commit()
    conn.close()

def get_source_feedback_score(url: str) -> float:
    """Simple RL feedback mechanism to weight sources based on past helpfulness."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*), SUM(CASE WHEN is_helpful THEN 1 ELSE 0 END)
        FROM feedback WHERE news_url = ?
    """, (url,))
    total, helpful = cursor.fetchone()
    conn.close()
    
    if total == 0 or total is None:
        return 0.5 # Neutral initial weight
        
    ratio = (helpful or 0) / total
    
    # Don't penalize heavily if we only have 1 vote
    if total < 2 and ratio == 0:
        return 0.4
        
    # Recency decay (bonus for newer articles, penalty for older ones)
    time_bonus = 0.0
    
    # We could theoretically calculate time decay based on the current date vs article date, 
    # but for simplicity, we provide a base score here and let the sorting logic handle recency.
    
    # Final combined score: Base RL Weight + Time Decay (to be added)
    return ratio

# Initialize DB on load
init_db()
