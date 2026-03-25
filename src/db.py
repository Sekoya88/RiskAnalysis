"""
Backward-compatible shim — re-exports from new DDD locations.

app.py imports init_db, save_report, get_history_for_entity, save_feedback,
get_source_feedback_score, DB_PATH from here.

Automatically uses PostgreSQL if DATABASE_URL is set, otherwise SQLite.
"""

import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(_PROJECT_ROOT, "data", "risk_history.db")


def _use_postgres() -> bool:
    return bool(os.getenv("DATABASE_URL"))


def _get_repos():
    if _use_postgres():
        from src.infrastructure.persistence.postgres import PostgresReportRepository, PostgresFeedbackRepository
        return PostgresReportRepository(), PostgresFeedbackRepository()
    from src.infrastructure.persistence.sqlite import SQLiteReportRepository, SQLiteFeedbackRepository
    return SQLiteReportRepository(DB_PATH), SQLiteFeedbackRepository(DB_PATH)


_report_repo, _feedback_repo = _get_repos()


def init_db():
    """No-op — tables are created by repository __init__."""
    pass


def save_report(report_id, entity, scores, report_text, sources):
    _report_repo.save_report(report_id, entity, scores, report_text, sources)


def get_history_for_entity(entity):
    return _report_repo.get_history_for_entity(entity)


def save_feedback(report_id, news_url, is_helpful, comments=""):
    _feedback_repo.save_feedback(report_id, news_url, is_helpful, comments)


def get_source_feedback_score(url):
    return _feedback_repo.get_source_feedback_score(url)


def list_feedback_votes() -> list[tuple[str, bool]]:
    return _feedback_repo.list_feedback_votes()
