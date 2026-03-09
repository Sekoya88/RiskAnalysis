"""
Domain Service — Pure business logic for RL weight computation and risk scoring.

No infrastructure dependency — operates on primitives only.
"""

from __future__ import annotations

from datetime import datetime


def compute_rl_weight(base_score: float, date_str: str) -> float:
    """Compute RL weight combining feedback score with time decay.

    Args:
        base_score: Base feedback score from repository (0.0-1.0).
        date_str: ISO date string of the source.

    Returns:
        Combined weight (higher = more trustworthy).
    """
    weight = base_score

    if date_str:
        try:
            article_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            days_old = (datetime.now() - article_date).days
            if days_old <= 1:
                weight += 0.2
            elif days_old <= 3:
                weight += 0.1
            elif days_old > 30:
                weight -= 0.1
        except Exception:
            pass

    return weight


def compute_feedback_score(total_votes: int, helpful_votes: int) -> float:
    """Compute RL feedback score from vote counts.

    Args:
        total_votes: Total number of votes.
        helpful_votes: Number of helpful votes.

    Returns:
        Score between 0.0 and 1.0 (0.5 = neutral).
    """
    if total_votes == 0:
        return 0.5

    ratio = helpful_votes / total_votes

    if total_votes < 2 and ratio == 0:
        return 0.4

    return ratio
