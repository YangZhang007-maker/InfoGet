from uuid import UUID

import pytest
from pydantic import ValidationError

from combine_up_and_source.report_models import (
    REPORT_STRUCTURES,
    ReportRequest,
    SemanticItem,
    stages_for_intent,
)


def test_report_structures_are_fixed():
    assert stages_for_intent("learning") == [
        "基础认知", "方法与工具", "实战内容", "进阶方向"
    ]
    assert stages_for_intent("industry") == [
        "背景概览", "当前热点", "典型案例", "趋势判断"
    ]
    assert stages_for_intent("decision") == [
        "基础知识", "可选方案", "实践建议", "风险提醒"
    ]
    assert set(REPORT_STRUCTURES) == {"learning", "industry", "decision"}


def test_unknown_intent_defaults_to_learning_structure():
    assert stages_for_intent("ambiguous") == stages_for_intent("learning")


def test_report_amount_must_be_between_one_and_thirty():
    request = ReportRequest(
        discovery_id="00000000-0000-4000-8000-000000000000", amount=1
    )
    assert isinstance(request.discovery_id, UUID)
    assert request.amount == 1

    for invalid in (0, 31):
        with pytest.raises(ValidationError):
            ReportRequest(
                discovery_id="00000000-0000-4000-8000-000000000000",
                amount=invalid,
            )


def test_semantic_item_rejects_model_supplied_url_and_long_tags():
    fields = {
        "item_id": "abc",
        "relevance_score": 90,
        "content_type": "实践教程",
        "stage": "实战内容",
        "relation_summary": "与机器学习实践直接相关",
        "tags": ["机器学习"],
        "matched_keywords": ["机器学习"],
    }
    with pytest.raises(ValidationError):
        SemanticItem(**fields, url="https://invented.example")
    with pytest.raises(ValidationError):
        SemanticItem(**{**fields, "tags": [str(i) for i in range(9)]})
    with pytest.raises(ValidationError):
        SemanticItem(**{**fields, "tags": ["x" * 101]})
    with pytest.raises(ValidationError):
        SemanticItem(**{**fields, "relation_summary": "合法内容\n## 注入标题"})
