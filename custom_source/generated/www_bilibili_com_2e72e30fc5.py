"""Generated custom-source crawler for https://www.bilibili.com/.

Review the selectors and the target site's terms before running this file.
"""

import argparse
import json

from custom_source.crawler.engine import CrawlerEngine
from custom_source.crawler.models import CrawlPlan


PLAN = {'source_url': 'https://www.bilibili.com/',
 'item_selector': '.feed-card > .bili-feed-card > .bili-video-card',
 'title_selector': '.bili-video-card__info--tit > a',
 'link_selector': '.bili-video-card__info--tit > a',
 'published_selector': '',
 'summary_selector': '',
 'hot_selector': '.bili-video-card__stats--text, .bili-video-card__info--icon-text',
 'search_url_template': '',
 'next_page_selector': '',
 'next_page_template': '',
 'requires_javascript': True,
 'sort_field': 'hot',
 'notes': '样本为首页推荐流，视频卡片由客户端动态加载；站内搜索跳转至不同子域名，不能提供同源搜索 URL 模板。'}


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
