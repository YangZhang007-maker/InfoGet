import asyncio
import time

from combine_up_and_source.report_models import (
    ReportOverview,
    SemanticDraft,
    SemanticItem,
)
from combine_up_and_source.report_service import DiscoveryReportService
from combine_up_and_source.storage import DiscoveryStorage


def discovery_result(items):
    return {
        "query": "机器学习",
        "keywords": ["机器学习"],
        "recommendation": {"bloggers": [], "platforms": []},
        "source_inputs": [],
        "batches": [{
            "status": "completed",
            "results": [{
                "source_url": "https://example.com",
                "source_name": "示例平台",
                "matched_platform": "示例平台",
                "items": items,
            }],
        }],
        "summary": {"total_items": len(items)},
        "warnings": [],
    }


class FakeAnalyzer:
    def __init__(self, *, fail=False, score=92, delay=0):
        self.fail = fail
        self.score = score
        self.delay = delay
        self.calls = 0

    def analyze(self, _snapshot, candidates):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if self.fail:
            raise RuntimeError("model unavailable")
        return SemanticDraft(
            intent="learning",
            overview=ReportOverview(
                topic_summary="机器学习内容概览",
                covered_directions=["基础"],
                reading_order="先基础后实践",
                missing_directions=["进阶方向"],
            ),
            bloggers=[],
            platforms=[],
            items=[SemanticItem(
                item_id=item.item_id,
                relevance_score=self.score,
                content_type="入门教程",
                stage="基础认知",
                relation_summary="解释机器学习基础概念",
                tags=["机器学习入门"],
                matched_keywords=["机器学习"],
            ) for item in candidates],
        )


def test_generates_report_and_backfills_trusted_content(tmp_path):
    storage = DiscoveryStorage(tmp_path)
    original_url = "https://example.com/trusted"
    discovery_id = storage.save_discovery(discovery_result([{
        "title": "机器学习基础教程",
        "url": original_url,
        "summary": "机器学习概念与方法",
        "relevance": 100,
        "hot": "1000",
    }]))
    analyzer = FakeAnalyzer()
    service = DiscoveryReportService(storage=storage, analyzer=analyzer)

    response = asyncio.run(service.generate(discovery_id, amount=10))

    assert response.generation_mode == "codex"
    assert response.returned_amount == 1
    assert response.report.stages[0].name == "基础认知"
    assert response.report.stages[0].items[0].url == original_url
    assert response.markdown.startswith("# 机器学习智能发现报告")


def test_reuses_complete_report_for_same_snapshot_and_amount(tmp_path):
    storage = DiscoveryStorage(tmp_path)
    discovery_id = storage.save_discovery(discovery_result([{
        "title": "机器学习基础",
        "url": "https://example.com/a",
        "summary": "机器学习",
        "relevance": 100,
    }]))
    analyzer = FakeAnalyzer()
    service = DiscoveryReportService(storage=storage, analyzer=analyzer)

    first = asyncio.run(service.generate(discovery_id, amount=5))
    second = asyncio.run(service.generate(discovery_id, amount=5))

    assert first.report_id == second.report_id
    assert first.model_dump() == second.model_dump()
    assert analyzer.calls == 1


def test_model_failure_returns_deterministic_fallback(tmp_path):
    storage = DiscoveryStorage(tmp_path)
    discovery_id = storage.save_discovery(discovery_result([{
        "title": "机器学习实战项目",
        "url": "https://example.com/project",
        "summary": "机器学习完整实践",
        "relevance": 100,
    }]))
    service = DiscoveryReportService(
        storage=storage, analyzer=FakeAnalyzer(fail=True)
    )

    response = asyncio.run(service.generate(discovery_id, amount=5))

    assert response.generation_mode == "fallback"
    assert "基础排序" in response.degraded_reason
    assert response.returned_amount == 1
    assert any("智能总结暂不可用" in warning for warning in response.report.warnings)


def test_empty_candidates_return_successful_empty_report(tmp_path):
    storage = DiscoveryStorage(tmp_path)
    discovery_id = storage.save_discovery(discovery_result([]))
    analyzer = FakeAnalyzer()
    service = DiscoveryReportService(storage=storage, analyzer=analyzer)

    response = asyncio.run(service.generate(discovery_id, amount=10))

    assert response.returned_amount == 0
    assert response.report.stages == []
    assert response.generation_mode == "fallback"
    assert analyzer.calls == 0
    assert all("智能总结暂不可用" not in warning for warning in response.report.warnings)


def test_concurrent_identical_requests_share_one_generation(tmp_path):
    storage = DiscoveryStorage(tmp_path)
    discovery_id = storage.save_discovery(discovery_result([{
        "title": "机器学习基础",
        "url": "https://example.com/concurrent",
        "summary": "机器学习",
        "relevance": 100,
    }]))
    analyzer = FakeAnalyzer(delay=0.1)
    first_service = DiscoveryReportService(storage=storage, analyzer=analyzer)
    second_service = DiscoveryReportService(storage=storage, analyzer=analyzer)

    async def generate_both():
        return await asyncio.gather(
            first_service.generate(discovery_id, amount=5),
            second_service.generate(discovery_id, amount=5),
        )

    first, second = asyncio.run(generate_both())

    assert analyzer.calls == 1
    assert first.model_dump() == second.model_dump()


def test_overview_is_reconciled_with_final_selected_items(tmp_path):
    storage = DiscoveryStorage(tmp_path)
    discovery_id = storage.save_discovery(discovery_result([{
        "title": "机器学习候选",
        "url": "https://example.com/low-score",
        "summary": "机器学习",
        "relevance": 100,
    }]))
    service = DiscoveryReportService(
        storage=storage,
        analyzer=FakeAnalyzer(score=40),
    )

    response = asyncio.run(service.generate(discovery_id, amount=5))

    assert response.returned_amount == 0
    assert response.report.overview.covered_directions == []
    assert response.report.overview.reading_order == ""
    assert "0 条" in response.report.overview.topic_summary
    assert response.report.overview.missing_directions == response.report.stage_order
