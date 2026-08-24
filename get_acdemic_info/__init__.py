"""Academic information discovery and adaptive crawling."""

from .service import AcademicCrawlerService
from .models import AcademicArticle, AcademicSearchRequest, AcademicSearchResult

__all__ = [
    "AcademicArticle",
    "AcademicCrawlerService",
    "AcademicSearchRequest",
    "AcademicSearchResult",
]
