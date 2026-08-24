"""Polite HTTP client with retry, delay, UA rotation, and redirect checks."""

from __future__ import annotations

import logging
import random
import time
from typing import Optional
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .security import validate_public_url

logger = logging.getLogger(__name__)

USER_AGENTS = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
)


class PoliteHttpClient:
    def __init__(self, delay_range: tuple[float, float] = (0.4, 1.2)) -> None:
        self.delay_range = delay_range
        self.session = requests.Session()
        retry = Retry(
            total=3,
            connect=3,
            read=2,
            backoff_factor=0.7,
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
        accept: str = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    ) -> requests.Response:
        current_url = validate_public_url(url)
        current_params = params

        for redirect_count in range(5):
            time.sleep(random.uniform(*self.delay_range))
            logger.info("Fetching academic source %s", current_url)
            response = self.session.get(
                current_url,
                params=current_params,
                headers={
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept": accept,
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
                timeout=timeout,
                allow_redirects=False,
            )
            if response.is_redirect or response.is_permanent_redirect:
                location = response.headers.get("Location")
                if not location:
                    break
                current_url = validate_public_url(urljoin(response.url, location))
                current_params = None
                continue
            response.raise_for_status()
            return response

        raise requests.TooManyRedirects("学术来源重定向次数过多")
