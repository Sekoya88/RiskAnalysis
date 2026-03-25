"""Feature vectors for PPO policy over news URLs (no labels in obs at inference)."""

from __future__ import annotations


def source_obs_vector(base_score: float, url: str) -> list[float]:
    """4-D observation: aggregate feedback prior, URL hash bucket, length, bias."""
    u = url or ""
    h = (hash(u) % 1000) / 1000.0
    ln = min(len(u) / 400.0, 1.0)
    return [float(base_score), float(h), float(ln), 1.0]
