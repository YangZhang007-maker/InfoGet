"""Parsing, filtering, ranking, and formatting helpers."""

from __future__ import annotations

import html
import math
import re
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from .models import AcademicArticle, AcademicSearchRequest


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(value or "", "html.parser").get_text(" ")).strip()


def parse_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = date_parser.parse(clean_text(value), fuzzy=True)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError, TypeError):
        return None


def parse_number(value: str) -> Optional[int]:
    if not value:
        return None
    normalized = value.lower().replace(",", "").strip()
    match = re.search(r"(\d+(?:\.\d+)?)\s*([km万亿]?)", normalized)
    if not match:
        return None
    number = float(match.group(1))
    multiplier = {"k": 1_000, "m": 1_000_000, "万": 10_000, "亿": 100_000_000}.get(
        match.group(2), 1
    )
    return int(number * multiplier)


def keyword_matches(article: AcademicArticle, keywords: Iterable[str]) -> bool:
    haystack = f"{article.title} {article.abstract}".casefold()
    return any(keyword.casefold() in haystack for keyword in keywords if keyword.strip())


def calculate_hot_score(article: AcademicArticle, now: Optional[datetime] = None) -> float:
    now = now or datetime.now(timezone.utc)
    score = 0.0
    if article.citations is not None:
        score += math.log1p(max(article.citations, 0)) * 32
    if article.downloads is not None:
        score += math.log1p(max(article.downloads, 0)) * 8
    if article.rating is not None:
        score += max(article.rating, 0) * 10
    published = parse_date(article.published_at or "")
    if published:
        age_days = max((now - published).total_seconds() / 86400, 0)
        score += 80 * math.exp(-age_days / 30)
    if article.hot_label:
        score += 25
    return round(score, 2)


def filter_and_rank(
    articles: List[AcademicArticle], request: AcademicSearchRequest
) -> List[AcademicArticle]:
    now = datetime.now(timezone.utc)
    filtered = []
    seen = set()

    for article in articles:
        title_key = article.title.casefold().strip()
        if not title_key or title_key in seen or not keyword_matches(article, request.keywords):
            continue
        seen.add(title_key)

        published = parse_date(article.published_at or "")
        age_days = (now - published).days if published else None
        if request.time_range_days is not None:
            if age_days is None or age_days > request.time_range_days:
                continue

        threshold_enabled = request.min_citations is not None or request.recent_days is not None
        if threshold_enabled:
            citation_match = (
                request.min_citations is not None
                and (article.citations or 0) >= request.min_citations
            )
            recent_match = (
                request.recent_days is not None
                and age_days is not None
                and age_days <= request.recent_days
            )
            if not citation_match and not recent_match:
                continue

        article.hot_score = calculate_hot_score(article, now)
        filtered.append(article)

    filtered.sort(
        key=lambda item: (
            item.hot_score,
            item.citations or 0,
            parse_date(item.published_at or "") or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )
    return filtered[: request.max_results]


def to_markdown(articles: List[AcademicArticle]) -> str:
    lines = [
        "| # | 标题 | 作者 | 发布时间 | 引用 | 热度 |",
        "|---:|---|---|---|---:|---:|",
    ]
    for index, article in enumerate(articles, 1):
        title = html.escape(article.title).replace("|", "\\|")
        authors = html.escape(", ".join(article.authors[:3])).replace("|", "\\|")
        citation_text = str(article.citations) if article.citations is not None else "-"
        lines.append(
            f"| {index} | [{title}]({article.url}) | {authors or '-'} | "
            f"{article.published_at or '-'} | {citation_text} | {article.hot_score:.1f} |"
        )
    return "\n".join(lines)
