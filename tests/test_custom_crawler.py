from pathlib import Path
from unittest.mock import patch

import pytest
from requests import Response

from custom_source.crawler.code_generator import CrawlerCodeGenerator
from custom_source.crawler.detector import assess_access
from custom_source.crawler.engine import CrawlBlockedError, CrawlerEngine
from custom_source.crawler.http import CrawlerHttpClient
from custom_source.crawler.models import CrawlPlan
from custom_source.crawler.plan_validator import validate_plan
from custom_source.crawler.robots import RobotsPolicy, inspect_robots
from custom_source.crawler.storage import CrawlerStorage


def response(html: str, url: str = "https://example.com/news", status: int = 200) -> Response:
    item = Response()
    item.status_code = status
    item.url = url
    item._content = html.encode()
    item.encoding = "utf-8"
    return item


def test_access_detection_requires_real_login_page_or_captcha():
    assert not assess_access(200, '<nav><a href="/login">Sign in</a></nav>').blocked
    assert assess_access(200, '<title>Sign in</title><input type="password">').blocked
    assert assess_access(200, "Please complete reCAPTCHA").blocked


def test_robots_policy_honors_disallow_and_delay():
    client = CrawlerHttpClient(delay=0)
    robots = "User-agent: *\nDisallow: /private\nCrawl-delay: 2\n"
    with patch.object(client, "get", return_value=response(robots, "https://example.com/robots.txt")):
        policy = inspect_robots("https://example.com/private", client)
    assert not policy.allowed
    assert policy.crawl_delay == 2


def test_plan_rejects_cross_origin_templates():
    plan = CrawlPlan(source_url="https://example.com", search_url_template="https://evil.example/?q={query}")
    with patch("custom_source.crawler.plan_validator.validate_public_url", side_effect=lambda value: value):
        with pytest.raises(ValueError, match="同源"):
            validate_plan(plan)


def test_static_extraction_filters_and_ranks_keywords():
    html = """<article><h2>AI breakthrough</h2><a href="/ai">Read</a>
      <time datetime="2026-08-20">August 20</time><p class="summary">AI systems</p>
      <span class="views">12k views</span></article>
      <article><h2>Unrelated story</h2><a href="/other">Read</a></article>"""
    plan = CrawlPlan(
        source_url="https://example.com/news", item_selector="article", title_selector="h2",
        link_selector="a", published_selector="time", summary_selector=".summary",
        hot_selector=".views", next_page_selector="",
    )
    policy = RobotsPolicy("https://example.com/robots.txt", True, True)
    with patch("custom_source.crawler.engine.inspect_robots", return_value=policy), patch.object(
        CrawlerHttpClient, "get", return_value=response(html)
    ), patch("custom_source.crawler.engine.validate_public_url", side_effect=lambda value: value):
        articles, _ = CrawlerEngine().execute(plan, ["AI"])
    assert [article.title for article in articles] == ["AI breakthrough"]
    assert articles[0].hot == 12_000


def test_engine_rejects_cross_origin_pagination():
    html = '<article><h2>AI</h2><a href="/ai">Read</a></article><a class="next" href="https://other.example/p2">Next</a>'
    plan = CrawlPlan(source_url="https://example.com/news", item_selector="article", title_selector="h2", link_selector="a", next_page_selector=".next")
    policy = RobotsPolicy("https://example.com/robots.txt", True, True)
    with patch("custom_source.crawler.engine.inspect_robots", return_value=policy), patch.object(
        CrawlerHttpClient, "get", return_value=response(html)
    ), patch("custom_source.crawler.engine.validate_public_url", side_effect=lambda value: value):
        with pytest.raises(CrawlBlockedError, match="不同域名"):
            CrawlerEngine().execute(plan, ["AI"], max_pages=2)


def test_storage_and_generated_code(tmp_path: Path):
    storage = CrawlerStorage(tmp_path / "data")
    analysis_id = "a" * 32
    storage.save_plan(analysis_id, {"analysis_id": analysis_id})
    assert storage.load_plan(analysis_id)["analysis_id"] == analysis_id

    code, generated_file = CrawlerCodeGenerator(tmp_path / "generated").generate(
        CrawlPlan(source_url="https://example.com")
    )
    compile(code, generated_file, "exec")
    assert Path(generated_file).is_file()

