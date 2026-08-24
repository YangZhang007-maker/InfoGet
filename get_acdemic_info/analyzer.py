"""DOM analysis that produces a constrained selector configuration."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from typing import Dict, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from soupsieve.util import SelectorSyntaxError

try:
    from ..codex_llm import call_codex_responses
except (ImportError, ValueError):
    from codex_llm import call_codex_responses

from .examples import EXAMPLE_CONFIGS
from .security import validate_public_url

logger = logging.getLogger(__name__)


@dataclass
class SelectorConfig:
    item: str = "article"
    title: str = "h1, h2, h3"
    link: str = "a[href]"
    authors: str = ".authors, .author, [itemprop='author']"
    abstract: str = ".abstract, .summary, [itemprop='abstract']"
    date: str = "time, .date, .published, [itemprop='datePublished']"
    citations: str = ".citation-count, .cited-by"
    downloads: str = ".download-count, .downloads"
    hot_label: str = ".popular, .trending, .badge"
    search_url_template: str = ""
    detail_abstract: str = ""
    requires_javascript: bool = False
    notes: str = ""

    def to_dict(self) -> Dict[str, str | bool]:
        return asdict(self)


class SiteAnalyzer:
    def analyze(self, html: str, source_url: str, keywords: list[str]) -> SelectorConfig:
        soup = BeautifulSoup(html, "html.parser")
        fallback = self._heuristic_config(soup)
        sample = self._dom_sample(soup)
        if not sample:
            fallback.requires_javascript = True
            fallback.notes = "初始 HTML 内容不足，建议启用 JavaScript 渲染。"
            return fallback

        system_prompt = (
            "你是学术网站 DOM 分析器。根据提供的 HTML，返回严格 JSON，不要返回代码块。"
            "只允许输出 CSS 选择器配置，禁止 JavaScript、Python、XPath 和解释性文本。"
            "字段必须为 item,title,link,authors,abstract,date,citations,downloads,hot_label,"
            "search_url_template,detail_abstract,requires_javascript,notes。"
            "item 应选择重复的论文结果容器，其余选择器相对于 item。"
            "如果页面有 GET 搜索表单，将 search_url_template 写成含 {query} 的绝对 URL；"
            "不确定的字段用空字符串。"
        )
        user_prompt = (
            f"页面 URL: {source_url}\n"
            f"关键词: {', '.join(keywords)}\n"
            f"启发式候选: {json.dumps(fallback.to_dict(), ensure_ascii=False)}\n\n"
            f"HTML 样本:\n{sample}"
        )
        try:
            content = call_codex_responses(
                system_prompt,
                user_prompt,
                max_output_tokens=1400,
                timeout=60,
            )
            data = _extract_json_object(content)
            candidate = SelectorConfig(
                **{key: data[key] for key in SelectorConfig.__dataclass_fields__ if key in data}
            )
            return self._validate_config(candidate, fallback, soup, source_url)
        except Exception as exc:
            logger.warning("Codex DOM analysis failed, using heuristic selectors: %s", exc)
            fallback.notes = f"智能分析失败，已使用启发式选择器: {exc}"
            return fallback

    def _heuristic_config(self, soup: BeautifulSoup) -> SelectorConfig:
        config = SelectorConfig(**EXAMPLE_CONFIGS["generic-schema-org"])
        candidates = [
            "article",
            "li.arxiv-result",
            "li.search-result",
            ".search-result",
            ".result-item",
            ".paper-item",
            ".publication",
            "[itemtype*='ScholarlyArticle']",
        ]
        scored = []
        for selector in candidates:
            nodes = soup.select(selector)
            useful = sum(1 for node in nodes if node.select_one("a[href]") and len(node.get_text(" ", strip=True)) > 40)
            if useful:
                scored.append((useful, selector))
        if scored:
            config.item = max(scored)[1]

        form = soup.select_one("form[action]")
        if form:
            query_input = form.select_one(
                "input[name*='query' i], input[name='q'], input[name*='search' i], input[type='search']"
            )
            if query_input and query_input.get("name"):
                action = form.get("action", "")
                separator = "&" if "?" in action else "?"
                config.search_url_template = f"{action}{separator}{query_input['name']}={{query}}"
        return config

    def _validate_config(
        self,
        candidate: SelectorConfig,
        fallback: SelectorConfig,
        soup: BeautifulSoup,
        source_url: str,
    ) -> SelectorConfig:
        for field_name in (
            "item", "title", "link", "authors", "abstract", "date",
            "citations", "downloads", "hot_label", "detail_abstract",
        ):
            value = getattr(candidate, field_name)
            if not isinstance(value, str) or len(value) > 300:
                setattr(candidate, field_name, getattr(fallback, field_name))
                continue
            if not value:
                continue
            try:
                soup.select(value)
            except SelectorSyntaxError:
                setattr(candidate, field_name, getattr(fallback, field_name))

        try:
            item_count = len(soup.select(candidate.item))
        except SelectorSyntaxError:
            item_count = 0
        if item_count == 0:
            candidate.item = fallback.item
        if not candidate.title:
            candidate.title = fallback.title
        if not candidate.link:
            candidate.link = fallback.link

        if candidate.search_url_template:
            absolute = urljoin(source_url, candidate.search_url_template)
            if "{query}" not in absolute:
                candidate.search_url_template = ""
            else:
                source_host = (urlparse(source_url).hostname or "").lower()
                target_host = (urlparse(absolute).hostname or "").lower()
                if target_host != source_host and not target_host.endswith(f".{source_host}"):
                    candidate.search_url_template = ""
                else:
                    validate_public_url(absolute.replace("{query}", "test"))
                    candidate.search_url_template = absolute
        candidate.requires_javascript = bool(candidate.requires_javascript)
        candidate.notes = str(candidate.notes or "")[:500]
        return candidate

    def _dom_sample(self, soup: BeautifulSoup) -> str:
        for node in soup.select("script, style, noscript, svg, canvas, iframe"):
            node.decompose()
        body = soup.body or soup
        sample = str(body)
        sample = re.sub(r"\s+", " ", sample)
        return sample[:24_000]


def _extract_json_object(content: str) -> dict:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise
        data = json.loads(match.group())
    if not isinstance(data, dict):
        raise ValueError("DOM analysis response must be an object")
    return data
