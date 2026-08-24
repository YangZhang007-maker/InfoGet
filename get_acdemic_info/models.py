"""Domain models for academic search."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AcademicSearchRequest:
    source_url: str
    keywords: List[str]
    time_range_days: Optional[int] = None
    min_citations: Optional[int] = None
    recent_days: Optional[int] = None
    max_results: int = 20
    render_javascript: bool = False
    output_format: str = "json"
    selectors: Optional[Dict[str, Any]] = None


@dataclass
class AcademicArticle:
    title: str
    url: str
    authors: List[str] = field(default_factory=list)
    published_at: Optional[str] = None
    abstract: str = ""
    citations: Optional[int] = None
    downloads: Optional[int] = None
    rating: Optional[float] = None
    hot_label: str = ""
    hot_score: float = 0.0
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AcademicSearchResult:
    source_url: str
    source_name: str
    strategy: str
    articles: List[AcademicArticle]
    generated_code: str
    selector_config: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    markdown: str = ""
    generated_file: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_url": self.source_url,
            "source_name": self.source_name,
            "strategy": self.strategy,
            "articles": [article.to_dict() for article in self.articles],
            "generated_code": self.generated_code,
            "selector_config": self.selector_config,
            "warnings": self.warnings,
            "markdown": self.markdown,
            "generated_file": self.generated_file,
        }
