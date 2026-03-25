"""Infrastructure — DuckDuckGo news & web search adapter."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from src.domain.ports.persistence import FeedbackRepositoryPort
from src.domain.services.risk_scoring import compute_rl_weight


# ── Output schemas ──────────────────────────────────────────────────

class NewsArticleOutput(BaseModel):
    title: str = ""
    body: str = ""
    source: str = ""
    url: str = ""
    date: str = ""
    rl_weight: float = 0.5


class NewsSearchOutput(BaseModel):
    query: str = ""
    num_results: int = 0
    articles: list[NewsArticleOutput] = Field(default_factory=list)
    error: Optional[str] = None


class WebResultOutput(BaseModel):
    title: str = ""
    body: str = ""
    href: str = ""
    rl_weight: float = 0.5


class WebSearchOutput(BaseModel):
    query: str = ""
    num_results: int = 0
    results: list[WebResultOutput] = Field(default_factory=list)
    error: Optional[str] = None


class DuckDuckGoAdapter:
    """NewsPort implementation backed by DuckDuckGo Search (ddgs)."""

    def __init__(self, feedback_repo: FeedbackRepositoryPort | None = None):
        self._feedback_repo = feedback_repo

    def _get_rl_weight(self, url: str, date_str: str) -> float:
        base_score = 0.5
        if self._feedback_repo and url:
            base_score = self._feedback_repo.get_source_feedback_score(url)
        w = compute_rl_weight(base_score, date_str)
        try:
            from src.rl.inference import ppo_weight_delta_optional

            w += ppo_weight_delta_optional(base_score, url)
            w = max(0.01, min(2.5, w))
        except Exception:
            pass
        return w

    def search_news(self, query: str, region: str = "wt-wt", max_results: int = 8) -> str:
        try:
            from ddgs import DDGS

            with DDGS() as ddgs:
                results = list(ddgs.news(query, region=region, max_results=min(max_results, 15)))

            articles: list[dict] = []
            for r in results:
                url = r.get("url", "")
                date_str = r.get("date", "")
                weight = self._get_rl_weight(url, date_str)

                if weight < 0.2:
                    continue

                articles.append({
                    "title": r.get("title", ""),
                    "body": r.get("body", ""),
                    "source": r.get("source", ""),
                    "url": url,
                    "date": date_str,
                    "rl_weight": weight,
                })

            articles.sort(key=lambda x: x["rl_weight"], reverse=True)

            output = NewsSearchOutput(
                query=query,
                num_results=len(articles),
                articles=[NewsArticleOutput(**a) for a in articles],
            )
            return output.model_dump_json()

        except Exception as e:
            return NewsSearchOutput(query=query, error=f"News search failed: {str(e)}").model_dump_json()

    def search_web(self, query: str, max_results: int = 5) -> str:
        try:
            from ddgs import DDGS

            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=min(max_results, 10)))

            items: list[dict] = []
            for r in results:
                url = r.get("href", "")
                date_str = r.get("date", "")
                weight = self._get_rl_weight(url, date_str)

                if weight < 0.2:
                    continue

                items.append({
                    "title": r.get("title", ""),
                    "body": r.get("body", ""),
                    "href": url,
                    "rl_weight": weight,
                })

            items.sort(key=lambda x: x["rl_weight"], reverse=True)

            output = WebSearchOutput(
                query=query,
                num_results=len(items),
                results=[WebResultOutput(**i) for i in items],
            )
            return output.model_dump_json()

        except Exception as e:
            return WebSearchOutput(query=query, error=f"Web search failed: {str(e)}").model_dump_json()
