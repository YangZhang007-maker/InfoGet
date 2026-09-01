"""Build and cache the daily cross-platform Top 20 ranking."""

from __future__ import annotations

import asyncio
import logging
import math
import os
import re
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from .models import DailyRankedItem, DailyTopResponse
from .storage import DailyTopStorage

logger = logging.getLogger(__name__)
SHANGHAI = ZoneInfo("Asia/Shanghai")

DEFAULT_PLATFORM_IDS = (
    "bilibili", "acfun", "douyin", "kuaishou", "coolapk",
    "weibo", "zhihu", "zhihu-daily", "tieba", "douban-group", "v2ex", "ngabbs", "hupu",
    "baidu", "thepaper", "toutiao", "36kr", "qq-news", "sina", "sina-news",
    "netease-news", "huxiu", "ifanr", "ithome", "ithome-xijiayi", "sspai", "csdn",
    "juejin", "51cto", "nodeseek", "hellogithub", "genshin", "miyoushe", "honkai",
    "starrail", "lol", "jianshu", "guokr", "weread", "douban-movie", "52pojie",
    "hostloc", "weatheralarm", "earthquake", "history",
)

FetchPlatform = Callable[[str], Awaitable[dict[str, Any] | None]]
Clock = Callable[[], datetime]


class DailyTopService:
    def __init__(
        self,
        storage: DailyTopStorage | None = None,
        fetch_platform: FetchPlatform | None = None,
        platform_ids: tuple[str, ...] = DEFAULT_PLATFORM_IDS,
        clock: Clock | None = None,
        concurrency: int = 8,
    ) -> None:
        self.storage = storage or DailyTopStorage()
        self.fetch_platform = fetch_platform
        self.platform_ids = platform_ids
        self.clock = clock or (lambda: datetime.now(SHANGHAI))
        self.concurrency = max(1, concurrency)
        self._refresh_lock = asyncio.Lock()

    async def get_top20(self, force: bool = False) -> DailyTopResponse:
        date_key = self._now().date().isoformat()
        if not force:
            cached = self.storage.load(date_key)
            if cached is not None:
                return cached.model_copy(update={"cached": True})

        async with self._refresh_lock:
            if not force:
                cached = self.storage.load(date_key)
                if cached is not None:
                    return cached.model_copy(update={"cached": True})
            response = await self._build(date_key)
            self.storage.save(response)
            return response

    async def _build(self, date_key: str) -> DailyTopResponse:
        semaphore = asyncio.Semaphore(self.concurrency)

        async def fetch(
            source_id: str,
            client: httpx.AsyncClient | None,
        ) -> tuple[str, dict[str, Any] | None]:
            async with semaphore:
                try:
                    payload = await (
                        self.fetch_platform(source_id)
                        if self.fetch_platform is not None
                        else self._fetch_from_hot_api(source_id, client)
                    )
                    return source_id, payload
                except Exception as exc:
                    logger.warning("Daily Top20 source %s failed: %s", source_id, exc)
                    return source_id, None

        if self.fetch_platform is not None:
            source_results = await asyncio.gather(
                *(fetch(source_id, None) for source_id in self.platform_ids)
            )
        else:
            timeout = httpx.Timeout(12.0, connect=3.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                source_results = await asyncio.gather(
                    *(fetch(source_id, client) for source_id in self.platform_ids)
                )
        failed_sources: list[str] = []
        candidates: list[DailyRankedItem] = []
        successful_sources = 0

        for platform_id, payload in source_results:
            if not payload or payload.get("code") != 200 or not isinstance(payload.get("data"), list):
                failed_sources.append(platform_id)
                continue
            successful_sources += 1
            platform_name = str(payload.get("title") or payload.get("name") or platform_id)
            for platform_rank, raw_item in enumerate(payload["data"], start=1):
                item = self._to_item(raw_item, platform_id, platform_name, platform_rank)
                if item is not None:
                    candidates.append(item)

        if successful_sources == 0:
            raise RuntimeError("热榜服务当前不可用，无法生成每日 Top20")

        unique: dict[str, DailyRankedItem] = {}
        for item in candidates:
            key = re.sub(r"\s+", "", item.title).casefold()
            previous = unique.get(key)
            if previous is None or self._sort_key(item) > self._sort_key(previous):
                unique[key] = item

        ranked = sorted(unique.values(), key=self._sort_key, reverse=True)[:20]
        return DailyTopResponse(
            date=date_key,
            generated_at=self._now().isoformat(),
            source_count=successful_sources,
            failed_sources=failed_sources,
            items=ranked,
        )

    async def _fetch_from_hot_api(
        self,
        platform_id: str,
        client: httpx.AsyncClient | None,
    ) -> dict[str, Any] | None:
        if client is None:
            raise RuntimeError("HTTP client is not initialized")
        api_base = os.getenv("DAILY_HOT_API_URL", "http://localhost:6688").rstrip("/")
        response = await client.get(f"{api_base}/{platform_id}")
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else None

    def _to_item(
        self,
        raw: Any,
        platform_id: str,
        platform_name: str,
        platform_rank: int,
    ) -> DailyRankedItem | None:
        if not isinstance(raw, dict):
            return None
        title = str(raw.get("title") or "").strip()
        url = str(raw.get("url") or raw.get("mobileUrl") or "").strip()
        if not title or not url.startswith(("http://", "https://")):
            return None
        raw_id = raw.get("id")
        item_id = raw_id if isinstance(raw_id, (str, int)) else f"{platform_id}-{platform_rank}"
        return DailyRankedItem(
            id=item_id,
            title=title,
            url=url,
            mobile_url=str(raw.get("mobileUrl") or ""),
            description=str(raw.get("desc") or "").strip(),
            hot=_finite_number(raw.get("hot")),
            timestamp=_finite_number(raw.get("timestamp")),
            platform_id=platform_id,
            platform_name=platform_name,
            platform_rank=platform_rank,
        )

    def _sort_key(self, item: DailyRankedItem) -> tuple[float, float, int, str, str]:
        return (
            item.hot or 0.0,
            item.timestamp or 0.0,
            -item.platform_rank,
            item.platform_id,
            item.title,
        )

    def _now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None:
            return value.replace(tzinfo=SHANGHAI)
        return value.astimezone(SHANGHAI)


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if not isinstance(value, str):
        return None
    cleaned = value.replace(",", "").strip().lower()
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not match:
        return None
    number = float(match.group())
    if "亿" in cleaned:
        number *= 100_000_000
    elif "万" in cleaned:
        number *= 10_000
    elif cleaned.endswith("m"):
        number *= 1_000_000
    elif cleaned.endswith("k"):
        number *= 1_000
    return number if math.isfinite(number) else None
