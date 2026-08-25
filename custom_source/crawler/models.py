"""Data models for adaptive custom-source crawling."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CrawlRequest:
    source_url: str
    keywords: List[str]
    max_pages: int = 3
    max_results: int = 30
    allow_javascript: bool = False


@dataclass
class CrawlPlan:
    source_url: str
    item_selector: str = "article"
    title_selector: str = "h1, h2, h3"
    link_selector: str = "a[href]"
    published_selector: str = "time, [datetime], .date, .published"
    summary_selector: str = ".summary, .excerpt, .description, [itemprop='description']"
    hot_selector: str = ".hot, .views, .score, .popular, [data-hot]"
    search_url_template: str = ""
    next_page_selector: str = "a[rel='next'], a.next, .pagination a.next"
    next_page_template: str = ""
    requires_javascript: bool = False
    sort_field: str = "published_at"
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CrawlerArticle:
    title: str
    published_at: Optional[str]
    summary: str
    url: str
    hot: Optional[int] = None
    hot_label: str = ""
    matched_keywords: List[str] = field(default_factory=list)
    hot_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CrawlResult:
    analysis_id: str
    source_url: str
    articles: List[CrawlerArticle]
    warnings: List[str] = field(default_factory=list)
    robots_allowed: bool = True
    json_file: str = ""
    generated_code: str = ""
    plan: Dict[str, Any] = field(default_factory=dict)
    status: str = "completed"

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["articles"] = [article.to_dict() for article in self.articles]
        return payload
