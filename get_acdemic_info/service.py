"""Orchestration for API-first and adaptive academic crawling."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from .adapters import OpenAlexAdapter, select_adapter
from .analyzer import SelectorConfig
from .code_generator import CrawlerCodeGenerator
from .generic_crawler import GenericAcademicCrawler
from .http_client import PoliteHttpClient
from .models import AcademicSearchRequest, AcademicSearchResult
from .security import validate_public_url
from .utils import filter_and_rank, to_markdown

logger = logging.getLogger(__name__)


class AcademicCrawlerService:
    def __init__(
        self,
        client: PoliteHttpClient | None = None,
        code_generator: CrawlerCodeGenerator | None = None,
    ) -> None:
        self.client = client or PoliteHttpClient()
        self.code_generator = code_generator or CrawlerCodeGenerator()

    def search(self, request: AcademicSearchRequest) -> AcademicSearchResult:
        request.source_url = validate_public_url(request.source_url)
        request.keywords = [keyword.strip() for keyword in request.keywords if keyword.strip()]
        if not request.keywords:
            raise ValueError("请至少提供一个有效关键词")
        request.max_results = min(max(request.max_results, 1), 50)

        adapter = select_adapter(request.source_url, self.client)
        warnings: list[str] = []
        selector_config = None

        if adapter:
            articles = adapter.search(request)
            strategy = adapter.strategy
            source_name = adapter.name
            if isinstance(adapter, OpenAlexAdapter) and "scholar.google." in (
                urlparse(request.source_url).hostname or ""
            ):
                warnings.append(
                    "Google Scholar 没有适合直接批量抓取的公开 API，且频繁自动访问容易触发验证码；本次已改用 OpenAlex API 获取可验证的引用数据。"
                )
        else:
            crawler = GenericAcademicCrawler(self.client)
            override = self._selector_override(request.selectors)
            articles, selector_config, crawl_warnings = crawler.crawl(request, override)
            warnings.extend(crawl_warnings)
            strategy = "adaptive_html"
            source_name = urlparse(request.source_url).hostname or "Academic source"

        ranked = filter_and_rank(articles, request)
        if not ranked and articles:
            warnings.append("抓取到了内容，但没有条目同时满足关键词、时间范围和热度阈值。")

        generated_code, generated_file = self.code_generator.generate(
            source_url=request.source_url,
            strategy=strategy,
            selector_config=selector_config,
        )
        return AcademicSearchResult(
            source_url=request.source_url,
            source_name=source_name,
            strategy=strategy,
            articles=ranked,
            generated_code=generated_code,
            selector_config=selector_config.to_dict() if selector_config else {},
            warnings=warnings,
            markdown=to_markdown(ranked),
            generated_file=generated_file,
        )

    @staticmethod
    def _selector_override(data: dict | None) -> SelectorConfig | None:
        if not data:
            return None
        allowed = SelectorConfig.__dataclass_fields__.keys()
        sanitized = {key: value for key, value in data.items() if key in allowed}
        return SelectorConfig(**sanitized)
