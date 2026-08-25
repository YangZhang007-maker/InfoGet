"""Optional Playwright fallback for JavaScript-rendered public pages."""

from __future__ import annotations

import logging

try:
    from ...get_acdemic_info.security import validate_public_url
except (ImportError, ValueError):
    from get_acdemic_info.security import validate_public_url

logger = logging.getLogger(__name__)


def render_page(url: str) -> tuple[str, str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "", "页面需要 JavaScript；请安装 playwright 并执行 `playwright install chromium`。"

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.route("**/*", _guard_request)
            page.goto(validate_public_url(url), wait_until="networkidle", timeout=35_000)
            validate_public_url(page.url)
            content = page.content()
            browser.close()
            return content, ""
    except Exception as exc:
        logger.warning("Playwright rendering failed for %s: %s", url, exc)
        return "", f"Playwright 渲染失败：{exc}"


def _guard_request(route) -> None:
    try:
        validate_public_url(route.request.url)
    except Exception:
        route.abort()
        return
    route.continue_()
