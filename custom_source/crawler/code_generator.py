"""Generate reviewable crawlers from validated CrawlPlans using a fixed template."""

from __future__ import annotations

import hashlib
import pprint
import re
from pathlib import Path
from urllib.parse import urlparse

from .models import CrawlPlan
from .plan_validator import validate_plan


class CrawlerCodeGenerator:
    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir or Path(__file__).resolve().parents[1] / "generated"

    def generate(self, plan: CrawlPlan) -> tuple[str, str]:
        plan = validate_plan(plan)
        plan_literal = pprint.pformat(plan.to_dict(), sort_dicts=False, width=100)
        code = f'''"""Generated custom-source crawler for {plan.source_url}.

Review the selectors and the target site's terms before running this file.
"""

import argparse
import json

from custom_source.crawler.engine import CrawlerEngine
from custom_source.crawler.models import CrawlPlan


PLAN = {plan_literal}


def crawl(keywords: list[str], max_pages: int = 3, max_results: int = 30,
          allow_javascript: bool = False) -> list[dict]:
    articles, warnings = CrawlerEngine().execute(
        CrawlPlan(**PLAN), keywords, max_pages=max_pages,
        max_results=max_results, allow_javascript=allow_javascript,
    )
    if warnings:
        print("Warnings:", "; ".join(warnings))
    return [article.to_dict() for article in articles]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("keywords", nargs="+")
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--max-results", type=int, default=30)
    parser.add_argument("--playwright", action="store_true")
    args = parser.parse_args()
    print(json.dumps(crawl(
        args.keywords, args.max_pages, args.max_results, args.playwright
    ), ensure_ascii=False, indent=2))
'''
        self.output_dir.mkdir(parents=True, exist_ok=True)
        host = re.sub(
            r"[^a-z0-9]+", "_", (urlparse(plan.source_url).hostname or "source").lower()
        ).strip("_") or "source"
        digest = hashlib.sha256(code.encode("utf-8")).hexdigest()[:10]
        path = self.output_dir / f"{host}_{digest}.py"
        path.write_text(code, encoding="utf-8")
        return code, str(path)

