"""Validated data contracts for discovery reports."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


ReportIntent = Literal["learning", "industry", "decision"]
GenerationMode = Literal["codex", "fallback"]
LabelText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        pattern=r"^[^\x00-\x1f\x7f]+$",
    ),
]
BriefText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=300,
        pattern=r"^[^\x00-\x1f\x7f]+$",
    ),
]

REPORT_STRUCTURES: dict[str, tuple[str, ...]] = {
    "learning": ("基础认知", "方法与工具", "实战内容", "进阶方向"),
    "industry": ("背景概览", "当前热点", "典型案例", "趋势判断"),
    "decision": ("基础知识", "可选方案", "实践建议", "风险提醒"),
}

STRUCTURE_NAMES: dict[str, str] = {
    "learning": "学习型",
    "industry": "行业型",
    "decision": "决策型",
}


def stages_for_intent(intent: str) -> list[str]:
    return list(REPORT_STRUCTURES.get(intent, REPORT_STRUCTURES["learning"]))


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReportRequest(StrictModel):
    discovery_id: UUID
    amount: int = Field(default=10, ge=1, le=30)


class CandidateItem(StrictModel):
    item_id: str = Field(min_length=8, max_length=64)
    title: str = Field(min_length=1, max_length=500)
    url: str = Field(min_length=1, max_length=4000)
    normalized_url: str = Field(min_length=1, max_length=4000)
    source_name: str = Field(default="未知来源", max_length=200)
    source_key: str = Field(default="unknown", max_length=300)
    summary: str = Field(default="", max_length=3000)
    hot: str = Field(default="", max_length=200)
    existing_relevance: int = Field(default=0, ge=0, le=100)
    match_type: str = Field(default="", max_length=200)
    rule_score: int = Field(default=0, ge=0, le=100)
    quality_score: int = Field(default=0, ge=0, le=100)
    heat_score: int = Field(default=0, ge=0, le=100)


class SemanticItem(StrictModel):
    item_id: str = Field(min_length=1, max_length=64)
    relevance_score: int = Field(ge=0, le=100)
    content_type: LabelText
    stage: LabelText
    relation_summary: BriefText
    tags: list[LabelText] = Field(default_factory=list, max_length=8)
    matched_keywords: list[LabelText] = Field(default_factory=list, max_length=10)


class SemanticSourceAnnotation(StrictModel):
    source_id: str = Field(min_length=1, max_length=64)
    role_label: LabelText
    relation_summary: BriefText
    matched_keywords: list[LabelText] = Field(default_factory=list, max_length=10)


class ReportOverview(StrictModel):
    topic_summary: str = Field(default="", max_length=800)
    covered_directions: list[LabelText] = Field(default_factory=list, max_length=12)
    reading_order: str = Field(default="", max_length=800)
    missing_directions: list[LabelText] = Field(default_factory=list, max_length=12)


class SemanticDraft(StrictModel):
    intent: ReportIntent
    overview: ReportOverview
    bloggers: list[SemanticSourceAnnotation] = Field(default_factory=list, max_length=20)
    platforms: list[SemanticSourceAnnotation] = Field(default_factory=list, max_length=20)
    items: list[SemanticItem] = Field(default_factory=list, max_length=60)


class ReportSourceAnnotation(StrictModel):
    source_id: str
    kind: Literal["blogger", "platform"]
    name: str
    role_label: str
    relation_summary: str
    matched_keywords: list[str] = Field(default_factory=list)
    url: str


class RecommendedSources(StrictModel):
    bloggers: list[ReportSourceAnnotation] = Field(default_factory=list)
    platforms: list[ReportSourceAnnotation] = Field(default_factory=list)


class ReportItem(StrictModel):
    item_id: str
    title: str
    url: str
    source_name: str
    source_key: str
    content_type: str
    stage: str
    relation_summary: str
    tags: list[str] = Field(default_factory=list)
    matched_keywords: list[str] = Field(default_factory=list)
    relevance_score: int = Field(ge=0, le=100)
    hot: str = ""
    quality_score: int = Field(default=0, ge=0, le=100)
    heat_score: int = Field(default=0, ge=0, le=100)


class ReportStage(StrictModel):
    name: str
    items: list[ReportItem] = Field(default_factory=list)


class DiscoveryReport(StrictModel):
    schema_version: int = 1
    title: str
    query: str
    keywords: list[str]
    intent: ReportIntent
    structure_name: str
    stage_order: list[str]
    overview: ReportOverview
    recommended_sources: RecommendedSources
    stages: list[ReportStage]
    warnings: list[str] = Field(default_factory=list)


class ReportResponse(StrictModel):
    report_id: str
    discovery_id: str
    requested_amount: int = Field(ge=1, le=30)
    returned_amount: int = Field(ge=0, le=30)
    generation_mode: GenerationMode
    degraded_reason: str | None = None
    report: DiscoveryReport
    markdown: str = ""
