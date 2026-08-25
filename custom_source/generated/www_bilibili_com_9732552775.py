"""Generated custom-source crawler for https://www.bilibili.com/.

Review the selectors and the target site's terms before running this file.
"""

import argparse
import json

from custom_source.crawler.engine import CrawlerEngine
from custom_source.crawler.models import CrawlPlan


PLAN = {'source_url': 'https://www.bilibili.com/',
 'item_selector': '.feed-card',
 'title_selector': '.bili-video-card__info--tit a',
 'link_selector': '.bili-video-card__image--link',
 'published_selector': '',
 'summary_selector': '',
 'hot_selector': '.bili-video-card__stats--left .bili-video-card__stats--text, '
                 '.bili-video-card__info--icon-text',
 'search_url_template': '/search?keyword={query}',
 'next_page_selector': '',
 'next_page_template': '/search?keyword={query}&page={page}',
 'requires_javascript': True,
 'sort_field': 'hot',
 'notes': '首页推荐卡片无稳定发布时间和摘要；关键词搜索结果由客户端动态渲染。'}


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
