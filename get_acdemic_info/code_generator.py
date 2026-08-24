"""Generate reviewable Python crawlers from validated site configurations."""

from __future__ import annotations

import hashlib
import json
import pprint
import re
from pathlib import Path
from urllib.parse import urlparse

from .analyzer import SelectorConfig


class CrawlerCodeGenerator:
    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir or Path(__file__).resolve().parent / "generated"

    def generate(
        self,
        *,
        source_url: str,
        strategy: str,
        selector_config: SelectorConfig | None = None,
    ) -> tuple[str, str]:
        if selector_config:
            code = self._generic_code(source_url, selector_config)
        else:
            code = self._adapter_code(source_url)
        path = self._persist(source_url, strategy, code)
        return code, str(path)

    def _generic_code(self, source_url: str, config: SelectorConfig) -> str:
        config_literal = pprint.pformat(config.to_dict(), sort_dicts=False, width=100)
        return f'''"""Generated academic crawler for {source_url}.

Review selectors before running against a changed site layout.
"""

import argparse
import json

from get_acdemic_info.analyzer import SelectorConfig
from get_acdemic_info.generic_crawler import GenericAcademicCrawler
from get_acdemic_info.models import AcademicSearchRequest
from get_acdemic_info.utils import filter_and_rank


SOURCE_URL = {source_url!r}
SELECTORS = {config_literal}


def crawl(keywords: list[str], max_results: int = 20) -> list[dict]:
    request = AcademicSearchRequest(
        source_url=SOURCE_URL,
        keywords=keywords,
        max_results=max_results,
    )
    crawler = GenericAcademicCrawler()
    articles, _, warnings = crawler.crawl(
        request,
        selector_override=SelectorConfig(**SELECTORS),
    )
    if warnings:
        print("Warnings:", "; ".join(warnings))
    return [item.to_dict() for item in filter_and_rank(articles, request)]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("keywords", nargs="+")
    parser.add_argument("--max-results", type=int, default=20)
    args = parser.parse_args()
    print(json.dumps(crawl(args.keywords, args.max_results), ensure_ascii=False, indent=2))
'''

    def _adapter_code(self, source_url: str) -> str:
        return f'''"""Generated API-first academic crawler for {source_url}."""

import argparse
import json

from get_acdemic_info.service import AcademicCrawlerService
from get_acdemic_info.models import AcademicSearchRequest


SOURCE_URL = {source_url!r}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("keywords", nargs="+")
    parser.add_argument("--max-results", type=int, default=20)
    args = parser.parse_args()
    result = AcademicCrawlerService().search(AcademicSearchRequest(
        source_url=SOURCE_URL,
        keywords=args.keywords,
        max_results=args.max_results,
    ))
    print(json.dumps([item.to_dict() for item in result.articles], ensure_ascii=False, indent=2))
'''

    def _persist(self, source_url: str, strategy: str, code: str) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        hostname = (urlparse(source_url).hostname or "academic").lower()
        safe_host = re.sub(r"[^a-z0-9]+", "_", hostname).strip("_") or "academic"
        digest = hashlib.sha256(f"{source_url}\n{code}".encode("utf-8")).hexdigest()[:10]
        path = self.output_dir / f"{safe_host}_{strategy}_{digest}.py"
        path.write_text(code, encoding="utf-8")
        return path
