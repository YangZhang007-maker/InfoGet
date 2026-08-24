from datetime import datetime, timedelta, timezone

import pytest

from get_acdemic_info.analyzer import SelectorConfig
from get_acdemic_info.generic_crawler import GenericAcademicCrawler
from get_acdemic_info.models import AcademicArticle, AcademicSearchRequest
from get_acdemic_info.security import UnsafeUrlError, validate_public_url
from get_acdemic_info.utils import filter_and_rank


ACADEMIC_HTML = """
<html><body>
  <article class="paper">
    <h2><a href="/paper/1">Efficient Transformer Models</a></h2>
    <div class="authors">Ada Lovelace, Alan Turing</div>
    <time datetime="2026-08-20">20 Aug 2026</time>
    <p class="abstract">A transformer architecture for efficient long context.</p>
    <span class="citations">Cited by 42</span>
  </article>
  <article class="paper">
    <h2><a href="/paper/2">Unrelated Biology Study</a></h2>
    <div class="authors">Researcher One</div>
    <time datetime="2024-01-01">1 Jan 2024</time>
    <p class="abstract">A wet lab study.</p>
    <span class="citations">Cited by 500</span>
  </article>
</body></html>
"""


def test_generic_crawler_parses_configured_academic_fields():
    crawler = GenericAcademicCrawler()
    config = SelectorConfig(
        item="article.paper",
        title="h2",
        link="h2 a",
        authors=".authors",
        abstract=".abstract",
        date="time",
        citations=".citations",
    )

    articles = crawler._parse_articles(ACADEMIC_HTML, "https://journal.example", config)

    assert len(articles) == 2
    assert articles[0].title == "Efficient Transformer Models"
    assert articles[0].url == "https://journal.example/paper/1"
    assert articles[0].authors == ["Ada Lovelace", "Alan Turing"]
    assert articles[0].published_at == "2026-08-20"
    assert articles[0].citations == 42


def test_filter_and_rank_applies_keyword_recency_and_hot_threshold():
    now = datetime.now(timezone.utc)
    articles = [
        AcademicArticle(
            title="Transformer survey",
            url="https://example.org/1",
            abstract="LLM methods",
            citations=30,
            published_at=(now - timedelta(days=120)).date().isoformat(),
        ),
        AcademicArticle(
            title="New transformer result",
            url="https://example.org/2",
            abstract="Efficient attention",
            citations=1,
            published_at=(now - timedelta(days=3)).date().isoformat(),
        ),
        AcademicArticle(
            title="Unrelated chemistry",
            url="https://example.org/3",
            citations=1000,
            published_at=now.date().isoformat(),
        ),
    ]
    request = AcademicSearchRequest(
        source_url="https://example.org",
        keywords=["transformer"],
        min_citations=10,
        recent_days=7,
    )

    ranked = filter_and_rank(articles, request)

    assert {article.url for article in ranked} == {
        "https://example.org/1",
        "https://example.org/2",
    }
    assert ranked[0].hot_score >= ranked[1].hot_score


def test_validate_public_url_rejects_localhost():
    with pytest.raises(UnsafeUrlError):
        validate_public_url("http://localhost:5001/private")
