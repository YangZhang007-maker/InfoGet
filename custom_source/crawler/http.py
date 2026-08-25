"""Polite HTTP client for custom-source crawling."""

from __future__ import annotations

import random
import time
from typing import Optional
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from ...get_acdemic_info.security import validate_public_url
except (ImportError, ValueError):
    from get_acdemic_info.security import validate_public_url


USER_AGENTS = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/127 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125 Safari/537.36",
)


class CrawlerHttpClient:
    def __init__(self, delay: float = 1.0, crawl_delay: float = 0.0) -> None:
        self.delay = max(delay, crawl_delay)
        self.session = requests.Session()
        retry = Retry(
            total=3,
            connect=3,
            read=2,
            backoff_factor=0.8,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def get(
        self,
        url: str,
        *,
        params: Optional[dict] = None,
        timeout: int = 25,
    ) -> requests.Response:
        current = validate_public_url(url)
        for _ in range(5):
            time.sleep(self.delay + random.uniform(0.0, 0.6))
            response = self.session.get(
                current,
                params=params,
                headers={
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
                timeout=timeout,
                allow_redirects=False,
            )
            if response.is_redirect or response.is_permanent_redirect:
                location = response.headers.get("Location")
                if not location:
                    break
                current = validate_public_url(urljoin(response.url, location))
                params = None
                continue
            return response
        raise requests.TooManyRedirects("目标网站重定向次数过多")
