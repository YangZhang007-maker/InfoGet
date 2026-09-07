"""Orchestrate discovery report generation and deterministic fallback."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from pydantic import ValidationError

from .report_candidates import ReportCandidateBuilder
from .report_markdown import render_report_markdown
from .report_models import (
    DiscoveryReport,
    RecommendedSources,
    ReportItem,
    ReportOverview,
    ReportResponse,
    ReportSourceAnnotation,
    SemanticDraft,
    ReportDetail,
    ReportNarrative,
    ReportNarrativeParagraph,
    ReportNarrativeSpan,
    STRUCTURE_NAMES,
    stages_for_intent,
)
from .report_ranking import (
    build_fallback_draft,
    group_into_stages,
    select_report_items,
)
from .report_semantics import ReportSemanticAnalyzer, build_source_catalog
from .storage import DiscoveryStorage

logger = logging.getLogger(__name__)


class DiscoveryReportService:
    # Bump when narrative composition changes so cached reports are rebuilt.
    REPORT_SCHEMA_VERSION = 3
    _generation_locks: dict[str, asyncio.Lock] = {}

    def __init__(
        self,
        *,
        storage: DiscoveryStorage | None = None,
        candidate_builder: ReportCandidateBuilder | None = None,
        analyzer: ReportSemanticAnalyzer | None = None,
    ) -> None:
        self.storage = storage or DiscoveryStorage()
        self.candidate_builder = candidate_builder or ReportCandidateBuilder()
        self.analyzer = analyzer or ReportSemanticAnalyzer()

    async def generate(
        self,
        discovery_id: str,
        amount: int = 10,
        detail: ReportDetail = "brief",
    ) -> ReportResponse:
        if not 1 <= int(amount) <= 30:
            raise ValueError("报告信息量必须在 1 到 30 之间")
        snapshot = self.storage.load_discovery(discovery_id)
        if detail not in ("brief", "detailed"):
            raise ValueError("报告总结程度必须是 brief 或 detailed")
        report_id = self.storage.report_id(
            discovery_id, amount, self.REPORT_SCHEMA_VERSION,
            variant=detail,
        )
        lock_key = f"{self.storage.data_dir.resolve()}:{report_id}"
        lock = self._generation_locks.setdefault(lock_key, asyncio.Lock())
        async with lock:
            return await self._generate_locked(
                discovery_id, amount, detail, snapshot, report_id
            )

    async def _generate_locked(
        self,
        discovery_id: str,
        amount: int,
        detail: ReportDetail,
        snapshot: dict[str, Any],
        report_id: str,
    ) -> ReportResponse:
        cached = self.storage.load_report(discovery_id, report_id)
        if cached is not None:
            try:
                return ReportResponse.model_validate(cached)
            except ValidationError:
                logger.warning("Ignoring invalid cached report %s", report_id)

        candidates = self.candidate_builder.build(snapshot, amount)
        generation_mode = "codex"
        degraded_reason = None
        if not candidates:
            draft = build_fallback_draft(snapshot, candidates)
            generation_mode = "fallback"
            degraded_reason = "没有可用于生成报告的有效内容，已生成基础报告"
        else:
            try:
                draft = await asyncio.to_thread(
                    self.analyzer.analyze, snapshot, candidates
                )
            except Exception as exc:
                logger.warning(
                    "Report semantic analysis failed for %s (%s)",
                    discovery_id,
                    type(exc).__name__,
                )
                draft = build_fallback_draft(snapshot, candidates)
                generation_mode = "fallback"
                degraded_reason = "Codex 语义分析暂不可用，已生成基础排序报告"

        response = self._build_response(
            discovery_id=discovery_id,
            report_id=report_id,
            amount=amount,
            detail=detail,
            snapshot=snapshot,
            candidates=candidates,
            draft=draft,
            generation_mode=generation_mode,
            degraded_reason=degraded_reason,
        )
        response.markdown = render_report_markdown(response.report)
        self.storage.save_report(
            discovery_id,
            report_id,
            response.model_dump(mode="json", exclude={"markdown"}),
            response.markdown,
        )
        persisted = self.storage.load_report(discovery_id, report_id)
        if persisted is None:
            raise RuntimeError("报告持久化失败")
        return ReportResponse.model_validate(persisted)

    def _build_response(
        self,
        *,
        discovery_id: str,
        report_id: str,
        amount: int,
        detail: ReportDetail,
        snapshot: dict[str, Any],
        candidates: list,
        draft: SemanticDraft,
        generation_mode: str,
        degraded_reason: str | None,
    ) -> ReportResponse:
        result = snapshot["result"]
        candidate_map = {candidate.item_id: candidate for candidate in candidates}
        report_items = []
        for semantic in draft.items:
            candidate = candidate_map[semantic.item_id]
            report_items.append(ReportItem(
                item_id=candidate.item_id,
                title=candidate.title,
                url=candidate.url,
                source_name=candidate.source_name,
                source_key=candidate.source_key,
                content_type=semantic.content_type,
                stage=semantic.stage,
                relation_summary=semantic.relation_summary,
                tags=semantic.tags,
                matched_keywords=semantic.matched_keywords,
                relevance_score=semantic.relevance_score,
                hot=candidate.hot,
                quality_score=candidate.quality_score,
                heat_score=candidate.heat_score,
            ))
        # The user's amount controls how many valid search results are
        # summarized. Relevance remains the stable sort signal, but a failed
        # Codex call must not turn an otherwise useful result set into zero
        # lines merely because fallback scores are conservative.
        selected = select_report_items(
            report_items,
            amount,
            include_low_relevance=True,
        )
        stages = group_into_stages(draft.intent, selected)
        stage_names = stages_for_intent(draft.intent)
        covered_directions = list(dict.fromkeys(
            item.content_type for item in selected
        ))[:12]
        used_stages = {item.stage for item in selected}
        query = str(result.get("query") or "当前兴趣").strip()
        overview = ReportOverview(
            topic_summary=(
                f"围绕“{query}”精选了 {len(selected)} 条高相关内容，"
                f"覆盖 {len(used_stages)} 个报告阶段。"
            )[:800],
            covered_directions=covered_directions,
            reading_order=" → ".join(
                stage for stage in stage_names if stage in used_stages
            ),
            missing_directions=[
                stage for stage in stage_names if stage not in used_stages
            ],
        )
        warnings = [str(value) for value in result.get("warnings", [])]
        if generation_mode == "fallback" and candidates:
            warnings.append("智能总结暂不可用，当前为基础排序报告。")
        if len(selected) < amount:
            warnings.append(
                f"达到相关度要求的内容为 {len(selected)} 条，少于请求的 {amount} 条。"
            )
        if selected and any(item.relevance_score < 55 for item in selected):
            warnings.append("部分内容相关度低于 55，已按热度和结果顺序纳入整合摘要。")
        report = DiscoveryReport(
            schema_version=self.REPORT_SCHEMA_VERSION,
            title=f'{str(result.get("query") or "智能发现").strip()}智能发现报告',
            query=str(result.get("query") or ""),
            keywords=[str(value) for value in result.get("keywords", [])],
            intent=draft.intent,
            structure_name=STRUCTURE_NAMES[draft.intent],
            stage_order=stages_for_intent(draft.intent),
            overview=overview,
            recommended_sources=self._materialize_sources(snapshot, draft),
            narrative=self._build_narrative(query, selected, detail),
            stages=stages,
            warnings=list(dict.fromkeys(warnings)),
        )
        return ReportResponse(
            report_id=report_id,
            discovery_id=discovery_id,
            requested_amount=amount,
            returned_amount=len(selected),
            detail=detail,
            generation_mode=generation_mode,
            degraded_reason=degraded_reason,
            report=report,
        )

    @staticmethod
    def _build_narrative(
        query: str,
        items: list[ReportItem],
        detail: ReportDetail,
    ) -> ReportNarrative:
        """Create deterministic linked prose from the validated report items.

        Each item title and relation summary becomes a citation span, so every
        claim shown in the paragraph remains traceable to one or more URLs.
        """
        if not items:
            return ReportNarrative(detail=detail, paragraphs=[])
        paragraphs: list[ReportNarrativeParagraph] = []
        by_stage: dict[str, list[ReportItem]] = {}
        for item in items:
            by_stage.setdefault(item.stage, []).append(item)
        for stage, stage_items in by_stage.items():
            spans = [ReportNarrativeSpan(text=_stage_lead(stage, query))]
            for index, item in enumerate(stage_items):
                relation = _relation_clause(item)
                if detail == "brief":
                    text = _item_link_text(item)
                else:
                    text = _item_link_text(item)
                    if relation:
                        text += f"，它{relation}"
                if index == 0:
                    spans.append(ReportNarrativeSpan(text="可先参考"))
                elif index == 1:
                    spans.append(ReportNarrativeSpan(text="随后，"))
                else:
                    spans.append(ReportNarrativeSpan(text="此外，"))
                spans.append(ReportNarrativeSpan(
                    text=text[:500],
                    item_ids=[item.item_id],
                    matched_keywords=item.matched_keywords,
                ))
            if detail == "brief":
                spans.append(ReportNarrativeSpan(text="，共同构成这一部分的参考脉络。"))
            else:
                spans.append(ReportNarrativeSpan(text="。把这些内容放在一起看，就能更清楚地了解这一步该怎么做。"))
            paragraphs.append(ReportNarrativeParagraph(spans=spans))
        return ReportNarrative(detail=detail, paragraphs=paragraphs)

    @staticmethod
    def _materialize_sources(
        snapshot: dict[str, Any], draft: SemanticDraft
    ) -> RecommendedSources:
        catalog = {source["source_id"]: source for source in build_source_catalog(snapshot)}

        def materialize(annotations, kind):
            sources = []
            for annotation in annotations:
                trusted = catalog[annotation.source_id]
                sources.append(ReportSourceAnnotation(
                    source_id=annotation.source_id,
                    kind=kind,
                    name=trusted["name"],
                    role_label=annotation.role_label,
                    relation_summary=annotation.relation_summary,
                    matched_keywords=annotation.matched_keywords,
                    url=trusted["url"],
                ))
            return sources

        return RecommendedSources(
            bloggers=materialize(draft.bloggers, "blogger"),
            platforms=materialize(draft.platforms, "platform"),
        )


def _stage_lead(stage: str, query: str) -> str:
    transitions = {
        "基础认知": "我们先从最基本的内容看起",
        "背景概览": "我们先从事情的来龙去脉看起",
        "基础知识": "我们先把最基本的知识弄明白",
        "方法与工具": "知道基本情况后，再看看使用的方法和工具",
        "当前热点": "了解背景后，再看看现在大家正在关注什么",
        "可选方案": "掌握基础知识后，再比较有哪些办法可以选择",
        "实战内容": "接着看看这些方法在实际中怎么用",
        "典型案例": "接着通过具体例子看看事情是怎样做成的",
        "实践建议": "接着说说实际操作时可以怎么做",
        "进阶方向": "最后再看看还能怎样继续深入",
        "趋势判断": "最后根据这些信息看看今后可能怎样发展",
        "风险提醒": "最后提醒几个需要特别小心的地方",
    }
    return f"{transitions.get(stage, f'围绕“{query}”，本段聚焦{stage}')}："


def _relation_clause(item: ReportItem) -> str:
    """Remove deterministic fallback boilerplate and duplicate titles."""
    relation = item.relation_summary.strip()
    if not relation:
        return ""
    prefixes = (
        "内容围绕",
        "根据标题和来源信息，该内容与当前兴趣相关：",
    )
    if relation.startswith("内容围绕") and "展开：" in relation:
        relation = relation.split("展开：", 1)[1].strip()
    for prefix in prefixes:
        if relation.startswith(prefix):
            relation = relation[len(prefix):].lstrip("：: ")
    if relation.endswith(item.title):
        relation = relation[: -len(item.title)].rstrip(" ：:，,。.")
    relation = relation.strip(" ：:，,。.!！?？")
    return relation[:420]


def _item_link_text(item: ReportItem) -> str:
    """Use a plain-language citation label instead of a raw clickbait title."""
    title = item.title.strip()
    title = re.sub(r"^[【\[][^】\]]{1,30}[】\]]\s*", "", title)
    title = re.sub(r"\s+", " ", title).strip(" 。.!！")
    descriptors = {
        "基础认知": "一份入门介绍",
        "背景概览": "一份背景介绍",
        "基础知识": "一份基础资料",
        "方法与工具": "一份方法说明",
        "当前热点": "一条热点信息",
        "可选方案": "一份方案比较",
        "实战内容": "一个实践案例",
        "典型案例": "一个典型案例",
        "实践建议": "一份实践建议",
        "进阶方向": "一份进阶资料",
        "趋势判断": "一份趋势分析",
        "风险提醒": "一条风险提醒",
    }
    descriptor = descriptors.get(item.stage, "一条相关信息")
    return f"{descriptor}《{title[:180]}》"
