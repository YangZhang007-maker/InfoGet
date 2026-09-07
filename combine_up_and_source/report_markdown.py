"""Deterministic Markdown rendering for validated discovery reports."""

from __future__ import annotations

import re
from urllib.parse import quote

from .report_models import DiscoveryReport


def render_report_markdown(report: DiscoveryReport) -> str:
    lines = [
        f"# {_escape(report.title)}",
        "",
        f"- 报告结构：{_escape(report.structure_name)}",
        f"- 兴趣关键词：{_escape('、'.join(report.keywords) or '未提供')}",
        "",
        "## 报告总览",
        "",
        report.overview.topic_summary or "暂无主题概览。",
    ]
    if report.overview.covered_directions:
        lines.extend(["", f"- 覆盖方向：{_escape('、'.join(report.overview.covered_directions))}"])
    if report.overview.reading_order:
        lines.append(f"- 推荐顺序：{_escape(report.overview.reading_order)}")
    if report.overview.missing_directions:
        lines.append(f"- 尚缺方向：{_escape('、'.join(report.overview.missing_directions))}")

    item_urls = {
        item.item_id: item.url
        for stage in report.stages
        for item in stage.items
    }
    lines.extend(["", "## 整合摘要", ""])
    if not report.narrative.paragraphs:
        lines.append("暂无可整合的内容。")
    else:
        for paragraph in report.narrative.paragraphs:
            parts = []
            for span in paragraph.spans:
                text = _escape(span.text)
                item_id = next((value for value in span.item_ids if value in item_urls), None)
                if item_id:
                    parts.append(f"[{text}](<{_safe_url(item_urls[item_id])}>)")
                else:
                    parts.append(text)
            lines.append("".join(parts))

    sources = report.recommended_sources
    if sources.bloggers:
        lines.extend(["", "## 推荐博主", ""])
        for source in sources.bloggers:
            lines.append(
                f"- [{_escape(source.name)}](<{_safe_url(source.url)}>)："
                f"{_escape(source.role_label)}。{_escape(source.relation_summary)}"
            )
    if sources.platforms:
        lines.extend(["", "## 推荐平台", ""])
        for source in sources.platforms:
            lines.append(
                f"- [{_escape(source.name)}](<{_safe_url(source.url)}>)："
                f"{_escape(source.role_label)}。{_escape(source.relation_summary)}"
            )

    for stage in report.stages:
        lines.extend(["", f"## {_escape(stage.name)}", ""])
        for item in stage.items:
            lines.extend([
                f"### [{_escape(item.title)}](<{_safe_url(item.url)}>)",
                "",
                f"- 来源：{_escape(item.source_name)}",
                f"- 相关度：{item.relevance_score}",
                f"- 内容类型：{_escape(item.content_type)}",
                f"- 兴趣关联：{_escape(item.relation_summary)}",
            ])
            if item.tags:
                lines.append(f"- 标签：{_escape('、'.join(item.tags))}")
            if item.hot:
                lines.append(f"- 热度：{_escape(item.hot)}")
            lines.append("")

    if not report.stages:
        lines.extend(["", "## 精选内容", "", "没有达到展示条件的内容。"])
    if report.warnings:
        lines.extend(["", "## 说明", ""])
        lines.extend(f"- {_escape(warning)}" for warning in report.warnings)
    return "\n".join(lines).strip() + "\n"


def _escape(value: str) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(value or "")).strip()
    for character in ("\\", "[", "]", "*", "_", "#"):
        text = text.replace(character, f"\\{character}")
    return text


def _safe_url(value: str) -> str:
    return quote(str(value or ""), safe=":/?&=#%+@,;~-._")
