"""
Backward-compatible shim — re-exports from new DDD locations.

app.py imports init_db, save_report, get_history_for_entity, save_feedback,
get_source_feedback_score from here.
"""

import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
_DB_PATH = os.path.join(_PROJECT_ROOT, "data", "risk_history.db")

from src.infrastructure.persistence.sqlite import SQLiteReportRepository, SQLiteFeedbackRepository

_report_repo = SQLiteReportRepository(_DB_PATH)
_feedback_repo = SQLiteFeedbackRepository(_DB_PATH)


def init_db():
    """No-op — tables are created by SQLiteReportRepository.__init__."""
    pass


def save_report(report_id, entity, scores, report_text, sources):
    _report_repo.save_report(report_id, entity, scores, report_text, sources)


def get_history_for_entity(entity):
    return _report_repo.get_history_for_entity(entity)


def save_feedback(report_id, news_url, is_helpful, comments=""):
    _feedback_repo.save_feedback(report_id, news_url, is_helpful, comments)


def get_source_feedback_score(url):
    return _feedback_repo.get_source_feedback_score(url)
