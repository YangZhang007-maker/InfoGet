"""Execute validated CrawlPlans with bounded keyword concurrency."""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import BoundedSemaphore
from typing import List
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup, Tag

from .browser import render_page
from .detector import assess_access
from .http import CrawlerHttpClient
from .models import CrawlPlan, CrawlerArticle
from .ranking import match_keywords, rank_articles
from .robots import inspect_robots
try:
    from ...get_acdemic_info.security import validate_public_url
except (ImportError, ValueError):
    from get_acdemic_info.security import validate_public_url

logger = logging.getLogger(__name__)


class CrawlBlockedError(RuntimeError):
    pass


class CrawlerEngine:
    def __init__(self, max_workers: int = 3, per_host: int = 2) -> None:
        self.max_workers = min(max(max_workers, 1), 3)
        self.host_slots = BoundedSemaphore(min(max(per_host, 1), 2))

    def execute(
        self,
        plan: CrawlPlan,
        keywords: list[str],
        *,
        max_pages: int = 3,
        max_results: int = 30,
        allow_javascript: bool = False,
        crawl_delay: float = 0.0,
    ) -> tuple[List[CrawlerArticle], List[str]]:
        max_pages = min(max(max_pages, 1), 5)
        keywords = [str(k).strip() for k in keywords if str(k).strip()]
        if not keywords:
            raise ValueError("请至少提供一个有效关键词")
        warnings: List[str] = []
        if plan.search_url_template:
            articles: List[CrawlerArticle] = []
            with ThreadPoolExecutor(max_workers=min(self.max_workers, len(keywords))) as pool:
                futures = [
                    pool.submit(
                        self._crawl_keyword, plan, keyword, keywords, max_pages,
                        allow_javascript, crawl_delay,
                    )
                    for keyword in keywords
                ]
                for future in as_completed(futures):
                    try:
                        batch, batch_warnings = future.result()
                        articles.extend(batch)
                        warnings.extend(batch_warnings)
                    except CrawlBlockedError:
                        raise
                    except Exception as exc:
                        logger.warning("Keyword crawl failed: %s", exc)
                        warnings.append(f"部分关键词抓取失败：{exc}")
        else:
            articles, warnings = self._crawl_url(
                plan, plan.source_url, keywords, max_pages, allow_javascript, crawl_delay
            )
        return rank_articles(articles, max_results), list(dict.fromkeys(warnings))

    def _crawl_keyword(
        self,
        plan: CrawlPlan,
        keyword: str,
        all_keywords: list[str],
        max_pages: int,
        allow_javascript: bool,
        crawl_delay: float,
    ) -> tuple[List[CrawlerArticle], List[str]]:
        url = urljoin(plan.source_url, plan.search_url_template.replace("{query}", quote_plus(keyword)))
        self._validate_same_origin(plan.source_url, url)
        with self.host_slots:
            return self._crawl_url(plan, url, all_keywords, max_pages, allow_javascript, crawl_delay)

    def _crawl_url(
        self,
        plan: CrawlPlan,
        start_url: str,
        keywords: list[str],
        max_pages: int,
        allow_javascript: bool,
        crawl_delay: float,
    ) -> tuple[List[CrawlerArticle], List[str]]:
        client = CrawlerHttpClient(delay=1.0, crawl_delay=crawl_delay)
        policy = inspect_robots(start_url, client)
        warnings = list(policy.warnings)
        if not policy.allowed:
            raise CrawlBlockedError("robots.txt 不允许抓取该搜索路径")
        current_url = start_url
        articles: List[CrawlerArticle] = []
        seen_pages = set()

        for page_number in range(1, max_pages + 1):
            if current_url in seen_pages:
                break
            seen_pages.add(current_url)
            response = client.get(current_url)
            self._validate_same_origin(plan.source_url, response.url)
            assessment = assess_access(response.status_code, response.text)
            warnings.extend(assessment.warnings)
            if assessment.blocked:
                raise CrawlBlockedError("目标网站要求登录、授权或验证码，已终止抓取")
            response.raise_for_status()
            html = response.text
            if allow_javascript and (plan.requires_javascript or len(html) < 800):
                rendered, render_warning = render_page(response.url)
                if rendered:
                    html = rendered
                elif render_warning:
                    warnings.append(render_warning)

            soup = BeautifulSoup(html, "html.parser")
            articles.extend(self._parse(soup, response.url, plan, keywords))
            next_url = self._next_url(soup, response.url, plan, page_number + 1)
            if not next_url:
                break
            self._validate_same_origin(plan.source_url, next_url)
            current_url = next_url
        return articles, warnings

    def _parse(
        self, soup: BeautifulSoup, base_url: str, plan: CrawlPlan, keywords: list[str]
    ) -> List[CrawlerArticle]:
        results = []
        for item in soup.select(plan.item_selector)[:100]:
            title_node = _one(item, plan.title_selector)
            link_node = _one(item, plan.link_selector)
            title = _text(title_node)
            if not title and link_node:
                title = _text(link_node)
            href = link_node.get("href", "") if link_node else ""
            if not title or not href:
                continue
            summary = _text(_one(item, plan.summary_selector))
            published_node = _one(item, plan.published_selector)
            published = _attribute_or_text(published_node, ("datetime", "content"))
            hot_text = _text(_one(item, plan.hot_selector))
            hot = _parse_number(hot_text)
            matched = match_keywords(title, summary, keywords)
            results.append(CrawlerArticle(
                title=title,
                published_at=published or None,
                summary=summary,
                url=urljoin(base_url, href),
                hot=hot,
                hot_label=hot_text if hot is None else "",
                matched_keywords=matched,
            ))
        return results

    def _next_url(self, soup: BeautifulSoup, base_url: str, plan: CrawlPlan, page: int) -> str:
        if plan.next_page_template:
            return urljoin(base_url, plan.next_page_template.replace("{page}", str(page)))
        node = soup.select_one(plan.next_page_selector) if plan.next_page_selector else None
        return urljoin(base_url, node.get("href", "")) if node and node.get("href") else ""

    @staticmethod
    def _validate_same_origin(source_url: str, candidate: str) -> str:
        safe = validate_public_url(candidate)
        from urllib.parse import urlparse
        if (urlparse(safe).hostname or "").lower() != (urlparse(source_url).hostname or "").lower():
            raise CrawlBlockedError("分页或搜索链接跳转到不同域名，已终止抓取")
        return safe


def _one(item: Tag, selector: str) -> Tag | None:
    return item.select_one(selector) if selector else None


def _text(node: Tag | None) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip() if node else ""


def _attribute_or_text(node: Tag | None, attributes: tuple[str, ...]) -> str:
    if not node:
        return ""
    for attribute in attributes:
        value = node.get(attribute)
        if value:
            return str(value).strip()
    return _text(node)


def _parse_number(value: str) -> int | None:
    match = re.search(r"([\d,.]+)\s*([kKmM万亿]?)", value.replace(" ", ""))
    if not match:
        return None
    number = float(match.group(1).replace(",", ""))
    multiplier = {"k": 1_000, "m": 1_000_000, "万": 10_000, "亿": 100_000_000}.get(match.group(2).lower(), 1)
    return int(number * multiplier)
