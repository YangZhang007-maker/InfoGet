import asyncio
import importlib
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from daily_info.models import DailyRankedItem, DailyTopResponse
from daily_info.service import DailyTopService, _finite_number
from daily_info.storage import DailyTopStorage


SHANGHAI = ZoneInfo("Asia/Shanghai")


def make_response(date_key: str = "2026-09-01") -> DailyTopResponse:
    return DailyTopResponse(
        date=date_key,
        generated_at=f"{date_key}T08:00:00+08:00",
        source_count=1,
        items=[
            DailyRankedItem(
                id="item-1",
                title="测试热点",
                url="https://example.com/item-1",
                hot=100,
                platform_id="alpha",
                platform_name="Alpha",
                platform_rank=1,
            )
        ],
    )


def test_daily_storage_round_trip_and_validation(tmp_path):
    storage = DailyTopStorage(tmp_path)
    storage.save(make_response())

    loaded = storage.load("2026-09-01")

    assert loaded is not None
    assert loaded.items[0].title == "测试热点"
    assert list((tmp_path / "daily_info").glob("*.tmp")) == []
    with pytest.raises(ValueError):
        storage.load("../../etc/passwd")


@pytest.mark.asyncio
async def test_service_builds_sorted_deduplicated_snapshot_and_reuses_cache(tmp_path):
    calls: list[str] = []

    async def fetch(platform_id: str):
        calls.append(platform_id)
        if platform_id == "broken":
            return None
        return {
            "code": 200,
            "title": platform_id.title(),
            "data": [
                {
                    "id": f"{platform_id}-1",
                    "title": "同一热点" if platform_id == "alpha" else "第二热点",
                    "url": f"https://example.com/{platform_id}/1",
                    "hot": "2万" if platform_id == "alpha" else 9000,
                    "timestamp": 10,
                },
                {
                    "id": f"{platform_id}-2",
                    "title": "同一热点",
                    "url": f"https://example.com/{platform_id}/2",
                    "hot": 100,
                },
            ],
        }

    service = DailyTopService(
        storage=DailyTopStorage(tmp_path),
        fetch_platform=fetch,
        platform_ids=("alpha", "beta", "broken"),
        clock=lambda: datetime(2026, 9, 1, 8, tzinfo=SHANGHAI),
    )

    generated = await service.get_top20()
    cached = await service.get_top20()

    assert generated.cached is False
    assert generated.source_count == 2
    assert generated.failed_sources == ["broken"]
    assert [item.title for item in generated.items] == ["同一热点", "第二热点"]
    assert generated.items[0].hot == 20_000
    assert cached.cached is True
    assert calls == ["alpha", "beta", "broken"]


@pytest.mark.asyncio
async def test_concurrent_requests_share_one_refresh(tmp_path):
    calls = 0

    async def fetch(platform_id: str):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return {
            "code": 200,
            "title": "Alpha",
            "data": [{"id": 1, "title": "热点", "url": "https://example.com", "hot": 1}],
        }

    service = DailyTopService(
        storage=DailyTopStorage(tmp_path),
        fetch_platform=fetch,
        platform_ids=("alpha",),
        clock=lambda: datetime(2026, 9, 1, 9, tzinfo=SHANGHAI),
    )

    first, second = await asyncio.gather(service.get_top20(), service.get_top20())

    assert calls == 1
    assert first.cached is False
    assert second.cached is True


@pytest.mark.asyncio
async def test_cross_day_request_creates_new_snapshot(tmp_path):
    current = datetime(2026, 9, 1, 23, 59, tzinfo=SHANGHAI)

    async def fetch(platform_id: str):
        return {
            "code": 200,
            "title": platform_id,
            "data": [{"id": 1, "title": str(current.date()), "url": "https://example.com", "hot": 1}],
        }

    service = DailyTopService(
        storage=DailyTopStorage(tmp_path),
        fetch_platform=fetch,
        platform_ids=("alpha",),
        clock=lambda: current,
    )
    await service.get_top20()
    current = datetime(2026, 9, 2, 0, 1, tzinfo=SHANGHAI)
    await service.get_top20()

    snapshots = sorted(path.name for path in (tmp_path / "daily_info").glob("*.json"))
    assert snapshots == ["2026-09-01.json", "2026-09-02.json"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [("1.5万", 15_000), ("2m", 2_000_000), ("3k", 3_000), (None, None), (float("nan"), None)],
)
def test_finite_number_normalization(value, expected):
    assert _finite_number(value) == expected


def test_daily_info_router_returns_snapshot(monkeypatch):
    router_module = importlib.import_module("daily_info.router")

    class FakeService:
        async def get_top20(self, force=False):
            assert force is True
            return make_response()

    monkeypatch.setattr(router_module, "service", FakeService())
    app = FastAPI()
    app.include_router(router_module.router)

    response = TestClient(app).get("/api/daily-info/top20?refresh=true")

    assert response.status_code == 200
    assert response.json()["items"][0]["title"] == "测试热点"


def test_daily_info_router_reports_upstream_failure(monkeypatch):
    router_module = importlib.import_module("daily_info.router")

    class FailingService:
        async def get_top20(self, force=False):
            raise RuntimeError("热榜服务不可用")

    monkeypatch.setattr(router_module, "service", FailingService())
    app = FastAPI()
    app.include_router(router_module.router)

    response = TestClient(app).get("/api/daily-info/top20")

    assert response.status_code == 503
    assert response.json()["detail"] == "热榜服务不可用"
