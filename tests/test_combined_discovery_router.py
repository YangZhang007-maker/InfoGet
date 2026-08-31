from fastapi.testclient import TestClient

from custom_source.server import app
from combine_up_and_source.storage import SnapshotCorruptError, SnapshotNotFoundError


client = TestClient(app)


def test_combined_discovery_route(monkeypatch):
    async def fake_discover(_self, query, **options):
        return {
            "discovery_id": "00000000-0000-4000-8000-000000000000",
            "query": query,
            "keywords": ["AI"],
            "recommendation": {"bloggers": [], "platforms": []},
            "source_inputs": [],
            "batches": [],
            "summary": {"total_items": 0, **options},
            "warnings": [],
        }

    monkeypatch.setattr(
        "combine_up_and_source.router.CombinedDiscoveryService.discover", fake_discover
    )
    response = client.post("/api/combined-discovery/run", json={
        "query": "Claude Code", "batch_size": 2, "max_per_source": 6
    })
    assert response.status_code == 200
    assert response.json()["discovery_id"] == "00000000-0000-4000-8000-000000000000"
    assert response.json()["query"] == "Claude Code"
    assert response.json()["summary"]["batch_size"] == 2


def test_combined_discovery_rejects_blank_query():
    response = client.post("/api/combined-discovery/run", json={"query": "  "})
    assert response.status_code == 422


def report_response(discovery_id, amount):
    return {
        "report_id": "a" * 32,
        "discovery_id": discovery_id,
        "requested_amount": amount,
        "returned_amount": 0,
        "generation_mode": "fallback",
        "degraded_reason": "没有有效内容",
        "report": {
            "schema_version": 1,
            "title": "AI智能发现报告",
            "query": "AI",
            "keywords": ["AI"],
            "intent": "learning",
            "structure_name": "学习型",
            "stage_order": ["基础认知", "方法与工具", "实战内容", "进阶方向"],
            "overview": {
                "topic_summary": "",
                "covered_directions": [],
                "reading_order": "",
                "missing_directions": [],
            },
            "recommended_sources": {"bloggers": [], "platforms": []},
            "stages": [],
            "warnings": [],
        },
        "markdown": "# AI智能发现报告\n",
    }


def test_generate_report_route(monkeypatch):
    async def fake_generate(_self, discovery_id, amount):
        return report_response(discovery_id, amount)

    monkeypatch.setattr(
        "combine_up_and_source.router.DiscoveryReportService.generate", fake_generate
    )
    discovery_id = "00000000-0000-4000-8000-000000000000"
    response = client.post("/api/combined-discovery/reports", json={
        "discovery_id": discovery_id,
        "amount": 10,
    })

    assert response.status_code == 200
    assert response.json()["discovery_id"] == discovery_id
    assert response.json()["requested_amount"] == 10


def test_report_route_validates_request_fields():
    discovery_id = "00000000-0000-4000-8000-000000000000"
    for payload in (
        {"discovery_id": "not-a-uuid", "amount": 10},
        {"discovery_id": discovery_id, "amount": 0},
        {"discovery_id": discovery_id, "amount": 31},
    ):
        response = client.post("/api/combined-discovery/reports", json=payload)
        assert response.status_code == 422


def test_report_route_maps_snapshot_errors(monkeypatch):
    discovery_id = "00000000-0000-4000-8000-000000000000"

    async def missing(_self, _discovery_id, _amount):
        raise SnapshotNotFoundError("不存在")

    monkeypatch.setattr(
        "combine_up_and_source.router.DiscoveryReportService.generate", missing
    )
    response = client.post("/api/combined-discovery/reports", json={
        "discovery_id": discovery_id, "amount": 10,
    })
    assert response.status_code == 404

    async def corrupt(_self, _discovery_id, _amount):
        raise SnapshotCorruptError("格式无效")

    monkeypatch.setattr(
        "combine_up_and_source.router.DiscoveryReportService.generate", corrupt
    )
    response = client.post("/api/combined-discovery/reports", json={
        "discovery_id": discovery_id, "amount": 10,
    })
    assert response.status_code == 409


def test_report_route_does_not_leak_internal_error(monkeypatch):
    async def fail(_self, _discovery_id, _amount):
        raise RuntimeError("/Users/private/secret.json")

    monkeypatch.setattr(
        "combine_up_and_source.router.DiscoveryReportService.generate", fail
    )
    response = client.post("/api/combined-discovery/reports", json={
        "discovery_id": "00000000-0000-4000-8000-000000000000",
        "amount": 10,
    })

    assert response.status_code == 500
    assert "/Users/private" not in response.json()["detail"]
