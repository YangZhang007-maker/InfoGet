import asyncio

from custom_source.custom_source import CustomSearchResult
from combine_up_and_source.service import CombinedDiscoveryService
from combine_up_and_source.storage import DiscoveryStorage


def test_combined_discovery_reuses_recommendation_and_batches_sources(tmp_path):
    calls = []

    def fake_recommend(query, max_bloggers):
        assert query == "AI 编程"
        assert max_bloggers == 2
        return {
            "keywords": ["AI编程", "智能代理"],
            "bloggers": [
                {"name": "UP One", "profile_url": "https://space.bilibili.com/1", "reason": "相关"},
                {"name": "UP Two", "profile_url": "https://space.bilibili.com/2", "reason": "高质量"},
            ],
            "platforms": [
                {"name": "掘金", "link": "https://juejin.cn", "reason": "教程"},
                {"name": "CSDN", "link": "https://csdn.net", "reason": "文档"},
                {"name": "知乎", "link": "https://zhihu.com", "reason": "讨论"},
            ],
        }

    async def fake_search(urls, interests, max_per_source):
        calls.append((urls, interests, max_per_source))
        return [CustomSearchResult(url, "source", items=[{"title": "item", "url": url}]) for url in urls]

    service = CombinedDiscoveryService(
        recommend_fn=fake_recommend,
        search_fn=fake_search,
        concurrency=2,
        storage=DiscoveryStorage(tmp_path),
    )
    result = asyncio.run(service.discover(
        "AI 编程", max_bloggers=2, batch_size=2, max_per_source=5
    ))

    assert len(calls) == 4  # two blogger jobs and two platform batches
    assert calls[0][1][0] in {"UP One", "UP Two"}
    assert sorted(len(call[0]) for call in calls) == [1, 1, 1, 2]
    assert result["summary"] == {
        "recommended_bloggers": 2,
        "recommended_platforms": 3,
        "sources_processed": 5,
        "total_items": 5,
        "failed_batches": 0,
    }
    assert result["discovery_id"]
    snapshot = service.storage.load_discovery(result["discovery_id"])
    assert snapshot["result"]["query"] == "AI 编程"
    assert "discovery_id" not in snapshot["result"]


def test_combined_discovery_keeps_successful_batches_when_one_fails(tmp_path):
    def fake_recommend(_query, _max_bloggers):
        return {
            "keywords": ["科技"],
            "bloggers": [],
            "platforms": [
                {"name": "A", "link": "https://a.example", "reason": ""},
                {"name": "B", "link": "https://b.example", "reason": ""},
            ],
        }

    async def fake_search(urls, _interests, _max_per_source):
        if "a.example" in urls[0]:
            raise RuntimeError("source failed")
        return [CustomSearchResult(urls[0], "B", items=[])]

    result = asyncio.run(CombinedDiscoveryService(
        recommend_fn=fake_recommend,
        search_fn=fake_search,
        storage=DiscoveryStorage(tmp_path),
    ).discover("科技", batch_size=1))

    assert [batch["status"] for batch in result["batches"]] == ["failed", "completed"]
    assert result["summary"]["failed_batches"] == 1
    assert any("1 个批次" in warning for warning in result["warnings"])
