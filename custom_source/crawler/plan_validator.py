"""Final validation boundary for model-produced crawl plans."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

from soupsieve import compile as compile_selector

try:
    from ...get_acdemic_info.security import validate_public_url
except (ImportError, ValueError):
    from get_acdemic_info.security import validate_public_url

from .models import CrawlPlan


SELECTOR_FIELDS = (
    "item_selector", "title_selector", "link_selector", "published_selector",
    "summary_selector", "hot_selector", "next_page_selector",
)


def validate_plan(plan: CrawlPlan) -> CrawlPlan:
    plan.source_url = validate_public_url(plan.source_url)
    for field in SELECTOR_FIELDS:
        value = getattr(plan, field)
        if not isinstance(value, str) or len(value) > 400:
            raise ValueError(f"无效的 CSS selector: {field}")
        if value:
            compile_selector(value)
    if not plan.item_selector or not plan.title_selector or not plan.link_selector:
        raise ValueError("CrawlPlan 缺少 item/title/link selector")
    for field, placeholder in (("search_url_template", "{query}"), ("next_page_template", "{page}")):
        template = getattr(plan, field)
        if not template:
            continue
        if placeholder not in template or len(template) > 600:
            raise ValueError(f"{field} 缺少 {placeholder} 占位符")
        resolved = urljoin(plan.source_url, template.replace(placeholder, "test"))
        validate_public_url(resolved)
        if (urlparse(resolved).hostname or "").lower() != (urlparse(plan.source_url).hostname or "").lower():
            raise ValueError(f"{field} 必须与目标网站同源")
    if plan.sort_field not in {"published_at", "hot", "auto"}:
        plan.sort_field = "auto"
    return plan
