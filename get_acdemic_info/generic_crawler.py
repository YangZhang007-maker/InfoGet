"""Constrained generic crawler driven by validated CSS selectors."""

from __future__ import annotations

import logging
import re
from typing import List, Tuple
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup, Tag

from .analyzer import SelectorConfig, SiteAnalyzer
from .http_client import PoliteHttpClient
from .models import AcademicArticle, AcademicSearchRequest
from .security import validate_public_url
from .utils import clean_text, parse_number

logger = logging.getLogger(__name__)


class GenericAcademicCrawler:
    def __init__(self, client: PoliteHttpClient | None = None) -> None:
        self.client = client or PoliteHttpClient()
        self.analyzer = SiteAnalyzer()

    def crawl(
        self,
        request: AcademicSearchRequest,
        selector_override: SelectorConfig | None = None,
    ) -> Tuple[List[AcademicArticle], SelectorConfig, List[str]]:
        warnings: List[str] = []
        response = self.client.get(request.source_url)
        html = response.text
        config = selector_override or self.analyzer.analyze(
            html, response.url, request.keywords
        )

        target_url = response.url
        if config.search_url_template:
            target_url = config.search_url_template.replace(
                "{query}", quote_plus(" ".join(request.keywords))
            )
            target_url = validate_public_url(target_url)
            response = self.client.get(target_url)
            html = response.text

        should_render = request.render_javascript or config.requires_javascript
        if should_render:
            rendered, render_warning = self._render_with_playwright(target_url)
            if rendered:
                html = rendered
            elif render_warning:
                warnings.append(render_warning)

        articles = self._parse_articles(html, response.url, config)
        if not articles:
            warnings.append(
                "当前页面未识别到论文列表。可启用 JavaScript 渲染，或通过 selectors 参数覆盖 CSS 选择器。"
            )
        return articles, config, warnings

    def _parse_articles(
        self, html: str, base_url: str, config: SelectorConfig
    ) -> List[AcademicArticle]:
        soup = BeautifulSoup(html, "html.parser")
        articles = []
        for item in soup.select(config.item)[:100]:
            title_node = _select_one(item, config.title)
            link_node = _select_one(item, config.link)
            title = clean_text(title_node.get_text(" ", strip=True) if title_node else "")
            if not title and link_node:
                title = clean_text(link_node.get_text(" ", strip=True))
            href = link_node.get("href", "") if link_node else ""
            if not title or not href:
                continue

            full_text = clean_text(item.get_text(" ", strip=True))
            authors = _split_authors(_node_text(item, config.authors))
            citations = parse_number(_node_text(item, config.citations))
            downloads = parse_number(_node_text(item, config.downloads))
            if citations is None:
                citations = _metric_from_text(full_text, r"(?:cited by|citations?|被引|引用)\s*[:：]?\s*([\d,.]+\s*[km万亿]?)")
            if downloads is None:
                downloads = _metric_from_text(full_text, r"(?:downloads?|views?|下载|浏览)\s*[:：]?\s*([\d,.]+\s*[km万亿]?)")

            articles.append(
                AcademicArticle(
                    title=title,
                    url=urljoin(base_url, href),
                    authors=authors,
                    published_at=_node_date(item, config.date),
                    abstract=_node_text(item, config.abstract),
                    citations=citations,
                    downloads=downloads,
                    hot_label=_node_text(item, config.hot_label),
                    source=base_url,
                )
            )
            if config.detail_abstract and not articles[-1].abstract:
                self._fill_detail_abstract(articles[-1], base_url, config.detail_abstract)
        return articles

    def _fill_detail_abstract(
        self, article: AcademicArticle, base_url: str, selector: str
    ) -> None:
        """Fetch a public detail page only when the list page lacks an abstract."""
        try:
            detail = self.client.get(article.url)
            node = BeautifulSoup(detail.text, "html.parser").select_one(selector)
            if node:
                article.abstract = clean_text(node.get("content") or node.get_text(" ", strip=True))
        except Exception as exc:
            logger.info("Detail abstract fetch skipped for %s: %s", article.url, exc)

    def _render_with_playwright(self, url: str) -> tuple[str, str]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return "", "页面可能依赖 JavaScript；安装 playwright 并执行 `playwright install chromium` 后可启用浏览器渲染。"

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page()
                safe_url = validate_public_url(url)
                page.route("**/*", lambda route: _guard_playwright_request(route))
                page.goto(safe_url, wait_until="networkidle", timeout=35_000)
                validate_public_url(page.url)
                content = page.content()
                browser.close()
                return content, ""
        except Exception as exc:
            logger.warning("Playwright rendering failed: %s", exc)
            return "", f"JavaScript 渲染失败，已使用原始 HTML: {exc}"


def _select_one(item: Tag, selector: str) -> Tag | None:
    return item.select_one(selector) if selector else None


def _node_text(item: Tag, selector: str) -> str:
    node = _select_one(item, selector)
    if not node:
        return ""
    return clean_text(node.get("content") or node.get_text(" ", strip=True))


def _node_date(item: Tag, selector: str) -> str | None:
    node = _select_one(item, selector)
    if not node:
        return None
    return clean_text(node.get("datetime") or node.get("content") or node.get_text(" ", strip=True))


def _split_authors(value: str) -> List[str]:
    if not value:
        return []
    normalized = re.sub(r"^(authors?|作者)\s*[:：]?\s*", "", value, flags=re.IGNORECASE)
    return [part.strip() for part in re.split(r"[,;；、]|\s+and\s+", normalized) if part.strip()][:20]


def _metric_from_text(value: str, pattern: str) -> int | None:
    match = re.search(pattern, value, re.IGNORECASE)
    return parse_number(match.group(1)) if match else None


def _guard_playwright_request(route) -> None:
    """Allow only public HTTP(S) subresources in browser rendering."""
    from .security import validate_public_url

    try:
        validate_public_url(route.request.url)
    except Exception:
        route.abort()
        return
    route.continue_()
