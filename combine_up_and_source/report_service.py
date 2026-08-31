"""Orchestrate discovery report generation and deterministic fallback."""

from __future__ import annotations

import asyncio
import logging
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
    REPORT_SCHEMA_VERSION = 1
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

    async def generate(self, discovery_id: str, amount: int = 10) -> ReportResponse:
        if not 1 <= int(amount) <= 30:
            raise ValueError("报告信息量必须在 1 到 30 之间")
        snapshot = self.storage.load_discovery(discovery_id)
        report_id = self.storage.report_id(
            discovery_id, amount, self.REPORT_SCHEMA_VERSION
        )
        lock_key = f"{self.storage.data_dir.resolve()}:{report_id}"
        lock = self._generation_locks.setdefault(lock_key, asyncio.Lock())
        async with lock:
            return await self._generate_locked(
                discovery_id, amount, snapshot, report_id
            )

    async def _generate_locked(
        self,
        discovery_id: str,
        amount: int,
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
        selected = select_report_items(report_items, amount)
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
            stages=stages,
            warnings=list(dict.fromkeys(warnings)),
        )
        return ReportResponse(
            report_id=report_id,
            discovery_id=discovery_id,
            requested_amount=amount,
            returned_amount=len(selected),
            generation_mode=generation_mode,
            degraded_reason=degraded_reason,
            report=report,
        )

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
