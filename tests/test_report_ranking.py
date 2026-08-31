from collections import Counter

from combine_up_and_source.report_models import CandidateItem, ReportItem
from combine_up_and_source.report_ranking import (
    build_fallback_draft,
    group_into_stages,
    infer_intent,
    select_report_items,
)


def report_item(index, *, source="A", score=80, stage="基础认知", quality=70, heat=50):
    return ReportItem(
        item_id=f"{index:032x}",
        title=f"内容 {index}",
        url=f"https://{source.lower()}.example/{index}",
        source_name=source,
        source_key=source,
        content_type="教程",
        stage=stage,
        relation_summary="与机器学习相关",
        tags=["机器学习"],
        matched_keywords=["机器学习"],
        relevance_score=score,
        quality_score=quality,
        heat_score=heat,
    )


def test_infers_report_intent_and_defaults_to_learning():
    assert infer_intent("机器学习入门课程", []) == "learning"
    assert infer_intent("人工智能行业热点和市场趋势", []) == "industry"
    assert infer_intent("框架选型比较与风险", []) == "decision"
    assert infer_intent("机器学习", []) == "learning"


def test_never_selects_items_below_relevance_threshold_or_pads_count():
    items = [report_item(1, score=54), report_item(2, score=55)]

    selected = select_report_items(items, amount=10)

    assert [item.item_id for item in selected] == [f"{2:032x}"]


def test_limits_one_source_to_forty_percent_when_sources_are_available():
    items = [report_item(index, source="A", score=95 - index) for index in range(6)]
    items.extend(report_item(10 + index, source="B", score=80 - index) for index in range(2))
    items.extend(report_item(20 + index, source="C", score=78 - index) for index in range(2))
    items.extend(report_item(30 + index, source="D", score=76 - index) for index in range(2))

    selected = select_report_items(items, amount=10)
    counts = Counter(item.source_key for item in selected)

    assert len(selected) == 10
    assert counts["A"] <= 4


def test_relaxes_source_limit_only_when_qualified_sources_are_insufficient():
    items = [report_item(index, source="A", score=90 - index) for index in range(5)]

    selected = select_report_items(items, amount=5)

    assert len(selected) == 5
    assert {item.source_key for item in selected} == {"A"}


def test_small_result_sets_prefer_source_diversity():
    items = [
        report_item(1, source="A", score=95),
        report_item(2, source="A", score=94),
        report_item(3, source="B", score=80),
    ]

    selected = select_report_items(items, amount=2)

    assert {item.source_key for item in selected} == {"A", "B"}


def test_groups_in_fixed_stage_order_and_sorts_within_stage():
    items = [
        report_item(1, score=80, stage="实战内容", quality=80),
        report_item(2, score=90, stage="基础认知", quality=70),
        report_item(3, score=90, stage="基础认知", quality=90),
    ]

    stages = group_into_stages("learning", items)

    assert [stage.name for stage in stages] == ["基础认知", "实战内容"]
    assert [item.item_id for item in stages[0].items] == [f"{3:032x}", f"{2:032x}"]


def test_fallback_draft_uses_only_snapshot_keywords_and_sources():
    snapshot = {
        "result": {
            "query": "机器学习入门",
            "keywords": ["机器学习"],
            "recommendation": {
                "bloggers": [{
                    "name": "教学博主",
                    "profile_url": "https://example.com/blogger",
                    "reason": "机器学习课程",
                }],
                "platforms": [],
            },
        }
    }
    candidate = CandidateItem(
        item_id="a" * 32,
        title="机器学习基础概念",
        url="https://example.com/a",
        normalized_url="https://example.com/a",
        source_name="示例平台",
        source_key="示例平台",
        summary="讲解基础概念",
        rule_score=80,
        quality_score=70,
    )

    draft = build_fallback_draft(snapshot, [candidate])

    assert draft.intent == "learning"
    assert draft.items[0].matched_keywords == ["机器学习"]
    assert draft.items[0].relevance_score == 80
    assert draft.bloggers[0].matched_keywords == ["机器学习"]
    assert "机器学习" in draft.bloggers[0].relation_summary
