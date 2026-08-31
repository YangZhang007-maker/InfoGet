"""Deterministic intent, fallback, diversity, and stage ordering rules."""

from __future__ import annotations

from collections import Counter
from math import floor
from typing import Any

from .report_models import (
    CandidateItem,
    ReportIntent,
    ReportItem,
    ReportOverview,
    ReportStage,
    SemanticDraft,
    SemanticItem,
    SemanticSourceAnnotation,
    stages_for_intent,
)
from .report_semantics import build_source_catalog


RELEVANCE_THRESHOLD = 55

_INTENT_TERMS = {
    "learning": ("入门", "学习", "教程", "课程", "基础", "怎么", "实践"),
    "industry": ("行业", "市场", "动态", "热点", "趋势", "现状", "发展"),
    "decision": ("比较", "选型", "选择", "方案", "建议", "风险", "决策", "推荐"),
}


def infer_intent(query: str, keywords: list[str]) -> ReportIntent:
    text = " ".join([str(query or ""), *[str(value) for value in keywords]]).casefold()
    scores = {
        intent: sum(term.casefold() in text for term in terms)
        for intent, terms in _INTENT_TERMS.items()
    }
    best_score = max(scores.values(), default=0)
    if best_score == 0:
        return "learning"
    for intent in ("decision", "industry", "learning"):
        if scores[intent] == best_score:
            return intent  # type: ignore[return-value]
    return "learning"


def build_fallback_draft(
    snapshot: dict[str, Any],
    candidates: list[CandidateItem],
) -> SemanticDraft:
    result = snapshot.get("result", snapshot)
    query = str(result.get("query") or "").strip()
    keywords = [str(value).strip() for value in result.get("keywords", []) if str(value).strip()]
    intent = infer_intent(query, keywords)
    semantic_items: list[SemanticItem] = []
    for candidate in candidates:
        matched = _matched_keywords(
            f"{candidate.title} {candidate.summary}", keywords
        )
        content_type = _content_type(candidate.title, candidate.summary)
        stage = _fallback_stage(intent, candidate.title, candidate.summary)
        relation = _item_relation(candidate, matched)
        semantic_items.append(SemanticItem(
            item_id=candidate.item_id,
            relevance_score=candidate.rule_score,
            content_type=content_type,
            stage=stage,
            relation_summary=relation,
            tags=list(dict.fromkeys([*matched, content_type]))[:8],
            matched_keywords=matched,
        ))

    bloggers: list[SemanticSourceAnnotation] = []
    platforms: list[SemanticSourceAnnotation] = []
    for source in build_source_catalog(snapshot):
        matched = _matched_keywords(f'{source["name"]} {source["reason"]}', keywords)
        keyword_label = "、".join(matched) or "用户兴趣"
        suffix = "教学博主" if source["kind"] == "blogger" else "信息平台"
        reason = source["reason"] or source["name"]
        annotation = SemanticSourceAnnotation(
            source_id=source["source_id"],
            role_label=f"{keyword_label}{suffix}"[:80],
            relation_summary=f"与{keyword_label}相关：{reason}"[:300],
            matched_keywords=matched,
        )
        (bloggers if source["kind"] == "blogger" else platforms).append(annotation)

    stage_names = stages_for_intent(intent)
    covered = list(dict.fromkeys(item.content_type for item in semantic_items))[:12]
    used_stages = {item.stage for item in semantic_items}
    missing = [stage for stage in stage_names if stage not in used_stages]
    topic = query or "、".join(keywords) or "当前兴趣"
    overview = ReportOverview(
        topic_summary=f"围绕“{topic}”整理了 {len(semantic_items)} 条候选内容。"[:800],
        covered_directions=covered,
        reading_order=" → ".join(stage for stage in stage_names if stage in used_stages),
        missing_directions=missing,
    )
    return SemanticDraft(
        intent=intent,
        overview=overview,
        bloggers=bloggers,
        platforms=platforms,
        items=semantic_items,
    )


def select_report_items(items: list[ReportItem], amount: int) -> list[ReportItem]:
    ordered = sorted(
        (item for item in items if item.relevance_score >= RELEVANCE_THRESHOLD),
        key=_item_sort_key,
    )
    target_count = min(max(int(amount), 0), len(ordered))
    if target_count == 0:
        return []
    source_limit = max(1, floor(target_count * 0.4))
    counts: Counter[str] = Counter()
    selected: list[ReportItem] = []
    selected_ids: set[str] = set()
    for item in ordered:
        if counts[item.source_key] >= source_limit:
            continue
        selected.append(item)
        selected_ids.add(item.item_id)
        counts[item.source_key] += 1
        if len(selected) == target_count:
            return selected
    for item in ordered:
        if item.item_id in selected_ids:
            continue
        selected.append(item)
        if len(selected) == target_count:
            break
    return selected


def group_into_stages(intent: ReportIntent, items: list[ReportItem]) -> list[ReportStage]:
    stages = []
    for stage_name in stages_for_intent(intent):
        stage_items = sorted(
            (item for item in items if item.stage == stage_name),
            key=_item_sort_key,
        )
        if stage_items:
            stages.append(ReportStage(name=stage_name, items=stage_items))
    return stages


def _item_sort_key(item: ReportItem) -> tuple[int, int, int, str]:
    return (-item.relevance_score, -item.quality_score, -item.heat_score, item.item_id)


def _matched_keywords(text: str, keywords: list[str]) -> list[str]:
    normalized = text.casefold()
    return [keyword for keyword in keywords if keyword.casefold() in normalized]


def _content_type(title: str, summary: str) -> str:
    text = f"{title} {summary}".casefold()
    if any(term in text for term in ("项目", "实战", "案例", "实践")):
        return "实践内容"
    if any(term in text for term in ("工具", "框架", "python", "方法")):
        return "方法与工具"
    if any(term in text for term in ("趋势", "行业", "市场", "热点")):
        return "行业分析"
    if any(term in text for term in ("风险", "比较", "选型", "方案")):
        return "决策参考"
    return "基础内容"


def _fallback_stage(intent: ReportIntent, title: str, summary: str) -> str:
    text = f"{title} {summary}".casefold()
    stages = stages_for_intent(intent)
    if intent == "learning":
        signals = (
            (("进阶", "深入", "部署", "优化", "研究"), 3),
            (("实战", "项目", "案例", "实践"), 2),
            (("方法", "工具", "框架", "python", "教程"), 1),
        )
    elif intent == "industry":
        signals = (
            (("趋势", "预测", "未来"), 3),
            (("案例", "企业", "应用"), 2),
            (("热点", "最新", "动态", "当前"), 1),
        )
    else:
        signals = (
            (("风险", "注意", "限制"), 3),
            (("建议", "实践", "落地"), 2),
            (("比较", "选型", "方案", "选择"), 1),
        )
    for terms, index in signals:
        if any(term in text for term in terms):
            return stages[index]
    return stages[0]


def _item_relation(candidate: CandidateItem, matched: list[str]) -> str:
    if matched:
        return f"内容围绕{'、'.join(matched)}展开：{candidate.title}"[:300]
    return f"根据标题和来源信息，该内容与当前兴趣相关：{candidate.title}"[:300]
