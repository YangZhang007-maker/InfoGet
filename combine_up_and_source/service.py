"""Combine blogger/platform recommendations with custom-source discovery."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from typing import Any, Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit

try:
    from ..recommend_source.recommender import recommend
    from ..custom_source.custom_source import custom_search
    from .storage import DiscoveryStorage
except (ImportError, ValueError):
    from recommend_source.recommender import recommend
    from combine_up_and_source.storage import DiscoveryStorage
    try:
        from custom_source.custom_source import custom_search
    except (ImportError, ModuleNotFoundError):
        # `python custom_source/server.py` loads custom_source.py as a module.
        from custom_source import custom_search

logger = logging.getLogger(__name__)


class CombinedDiscoveryService:
    """Run recommendation first, then feed its sources into custom search."""

    def __init__(
        self,
        *,
        recommend_fn: Callable[[str, int], dict[str, Any]] = recommend,
        search_fn: Callable[..., Awaitable[list[Any]]] = custom_search,
        concurrency: int = 2,
        storage: DiscoveryStorage | None = None,
    ) -> None:
        self.recommend_fn = recommend_fn
        self.search_fn = search_fn
        self.concurrency = min(max(concurrency, 1), 3)
        self.storage = storage or DiscoveryStorage()

    async def discover(
        self,
        query: str,
        *,
        max_bloggers: int = 6,
        batch_size: int = 3,
        max_per_source: int = 10,
    ) -> dict[str, Any]:
        query = query.strip()
        if not query:
            raise ValueError("请输入感兴趣的内容")
        max_bloggers = min(max(max_bloggers, 1), 8)
        batch_size = min(max(batch_size, 1), 5)
        max_per_source = min(max(max_per_source, 1), 20)

        recommendation = await asyncio.to_thread(self.recommend_fn, query, max_bloggers)
        keywords = self._keywords(recommendation.get("keywords"), query)
        bloggers = self._blogger_sources(recommendation.get("bloggers", []))
        platforms = self._platform_sources(recommendation.get("platforms", []))
        warnings: list[str] = []

        if not bloggers:
            warnings.append("推荐结果中没有带公开主页链接的博主，已仅处理推荐平台。")
        if not platforms:
            warnings.append("推荐结果中没有带有效链接的平台。")

        jobs: list[dict[str, Any]] = []
        for blogger in bloggers:
            jobs.append({
                "kind": "blogger",
                "sources": [blogger],
                "interests": self._unique([blogger["name"], *keywords]),
            })
        for index in range(0, len(platforms), batch_size):
            jobs.append({
                "kind": "platform",
                "sources": platforms[index:index + batch_size],
                "interests": keywords,
            })

        semaphore = asyncio.Semaphore(self.concurrency)

        async def execute(job_index: int, job: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                urls = [source["url"] for source in job["sources"]]
                try:
                    raw_results = await self.search_fn(urls, job["interests"], max_per_source)
                    return {
                        "batch": job_index + 1,
                        "kind": job["kind"],
                        "status": "completed",
                        "sources": job["sources"],
                        "interests": job["interests"],
                        "results": [self._serialize_result(item) for item in raw_results],
                        "error": None,
                    }
                except Exception as exc:
                    logger.warning("Combined discovery batch %s failed: %s", job_index + 1, exc)
                    return {
                        "batch": job_index + 1,
                        "kind": job["kind"],
                        "status": "failed",
                        "sources": job["sources"],
                        "interests": job["interests"],
                        "results": [],
                        "error": str(exc),
                    }

        batches = await asyncio.gather(*(execute(index, job) for index, job in enumerate(jobs)))
        sources_processed = sum(len(batch["sources"]) for batch in batches if batch["status"] == "completed")
        total_items = sum(
            len(result.get("items", []))
            for batch in batches
            for result in batch["results"]
        )
        failed = sum(batch["status"] == "failed" for batch in batches)
        if failed:
            warnings.append(f"{failed} 个批次处理失败，其他批次结果仍已保留。")

        discovery = {
            "query": query,
            "keywords": keywords,
            "recommendation": {
                "bloggers": recommendation.get("bloggers", []),
                "platforms": recommendation.get("platforms", []),
            },
            "source_inputs": [*bloggers, *platforms],
            "batches": batches,
            "summary": {
                "recommended_bloggers": len(recommendation.get("bloggers", [])),
                "recommended_platforms": len(recommendation.get("platforms", [])),
                "sources_processed": sources_processed,
                "total_items": total_items,
                "failed_batches": failed,
            },
            "warnings": warnings,
        }
        discovery_id = self.storage.save_discovery(discovery)
        return {"discovery_id": discovery_id, **discovery}

    @classmethod
    def _blogger_sources(cls, bloggers: list[dict[str, Any]]) -> list[dict[str, str]]:
        sources = []
        seen = set()
        for blogger in bloggers:
            url = cls._normalize_url(blogger.get("profile_url", ""))
            name = str(blogger.get("name", "")).strip()
            if not url or not name or url in seen:
                continue
            seen.add(url)
            sources.append({
                "kind": "blogger",
                "name": name,
                "url": url,
                "reason": str(blogger.get("reason", "")).strip(),
                "scope": "平台级检索（以博主名优先匹配）",
            })
        return sources

    @classmethod
    def _platform_sources(cls, platforms: list[dict[str, Any]]) -> list[dict[str, str]]:
        sources = []
        seen = set()
        for platform in platforms:
            url = cls._normalize_url(platform.get("link", ""))
            if not url or url in seen:
                continue
            seen.add(url)
            sources.append({
                "kind": "platform",
                "name": str(platform.get("name", "")).strip() or url,
                "url": url,
                "reason": str(platform.get("reason", "")).strip(),
                "scope": "推荐平台关键词检索",
            })
        return sources

    @staticmethod
    def _normalize_url(value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        if "://" not in raw:
            raw = f"https://{raw}"
        parsed = urlsplit(raw)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return ""
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))

    @staticmethod
    def _keywords(values: Any, fallback: str) -> list[str]:
        keywords = CombinedDiscoveryService._unique(
            [str(value).strip() for value in (values or []) if str(value).strip()]
        )
        return keywords[:5] or [fallback[:80]]

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        return list(dict.fromkeys(value for value in values if value))

    @staticmethod
    def _serialize_result(result: Any) -> dict[str, Any]:
        if hasattr(result, "__dataclass_fields__"):
            return asdict(result)
        if hasattr(result, "model_dump"):
            return result.model_dump()
        if isinstance(result, dict):
            return result
        raise TypeError("自定义源返回了无法序列化的结果")
