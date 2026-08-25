"""robots.txt inspection and compliance warnings."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from urllib.parse import urlparse, urlunparse
from urllib.robotparser import RobotFileParser

from .http import CrawlerHttpClient

logger = logging.getLogger(__name__)


@dataclass
class RobotsPolicy:
    url: str
    allowed: bool
    available: bool
    crawl_delay: float = 0.0
    warnings: list[str] = field(default_factory=list)


def robots_url(source_url: str) -> str:
    parsed = urlparse(source_url)
    return urlunparse((parsed.scheme, parsed.netloc, "/robots.txt", "", "", ""))


def inspect_robots(source_url: str, client: CrawlerHttpClient) -> RobotsPolicy:
    url = robots_url(source_url)
    try:
        response = client.get(url, timeout=12)
    except Exception as exc:
        return RobotsPolicy(
            url=url,
            allowed=True,
            available=False,
            warnings=[f"robots.txt 无法访问，已采用保守限速继续：{exc}"],
        )

    if response.status_code == 404:
        return RobotsPolicy(
            url=url,
            allowed=True,
            available=False,
            warnings=["目标站点未提供 robots.txt，请确认访问权限和站点条款。"],
        )
    if response.status_code >= 400:
        return RobotsPolicy(
            url=url,
            allowed=True,
            available=False,
            warnings=[f"robots.txt 返回 HTTP {response.status_code}，已采用保守限速。"],
        )

    parser = RobotFileParser()
    parser.set_url(url)
    parser.parse(response.text.splitlines())
    allowed = parser.can_fetch("*", source_url)
    delay = parser.crawl_delay("*") or parser.crawl_delay("Mozilla") or 0.0
    warnings = []
    if not allowed:
        warnings.append("robots.txt 不允许自动抓取该路径，已终止。")
    elif delay:
        warnings.append(f"robots.txt 指定 Crawl-delay={delay:g} 秒，已应用。")
    return RobotsPolicy(url, allowed, True, float(delay), warnings)
