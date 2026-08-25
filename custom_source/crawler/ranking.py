"""Keyword matching, deduplication, and news-style hot ranking."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Iterable, List

from dateutil import parser as date_parser

from .models import CrawlerArticle


def match_keywords(title: str, summary: str, keywords: Iterable[str]) -> List[str]:
    text = f"{title} {summary}".casefold()
    return [keyword for keyword in keywords if keyword.casefold() in text]


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = date_parser.parse(value, fuzzy=True)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def rank_articles(articles: List[CrawlerArticle], max_results: int) -> List[CrawlerArticle]:
    now = datetime.now(timezone.utc)
    unique: dict[str, CrawlerArticle] = {}
    for article in articles:
        key = article.url.casefold().rstrip("/") or article.title.casefold().strip()
        if not key or not article.matched_keywords:
            continue
        published = parse_date(article.published_at)
        recency = 0.0
        if published:
            age_days = max((now - published).total_seconds() / 86400, 0)
            recency = 70 * math.exp(-age_days / 14)
        heat = math.log1p(max(article.hot or 0, 0)) * 15
        label_bonus = 20 if article.hot_label else 0
        keyword_bonus = len(article.matched_keywords) * 8
        article.hot_score = round(recency + heat + label_bonus + keyword_bonus, 2)
        previous = unique.get(key)
        if previous is None or article.hot_score > previous.hot_score:
            unique[key] = article
    return sorted(
        unique.values(),
        key=lambda item: (item.hot_score, parse_date(item.published_at) or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True,
    )[: max(1, min(max_results, 100))]
