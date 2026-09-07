from combine_up_and_source.report_markdown import render_report_markdown
from combine_up_and_source.report_models import (
    DiscoveryReport,
    RecommendedSources,
    ReportItem,
    ReportOverview,
    ReportStage,
)


def item(item_id, title, stage):
    return ReportItem(
        item_id=item_id,
        title=title,
        url=f"https://example.com/{item_id}",
        source_name="示例平台",
        source_key="示例平台",
        content_type="教程",
        stage=stage,
        relation_summary="与机器学习相关",
        tags=["机器学习"],
        matched_keywords=["机器学习"],
        relevance_score=90,
    )


def test_markdown_follows_stage_order_and_contains_only_selected_items():
    basic = item("basic", "基础内容", "基础认知")
    practice = item("practice", "实践内容", "实战内容")
    report = DiscoveryReport(
        title="机器学习智能发现报告",
        query="机器学习",
        keywords=["机器学习"],
        intent="learning",
        structure_name="学习型",
        stage_order=["基础认知", "方法与工具", "实战内容", "进阶方向"],
        overview=ReportOverview(topic_summary="概览"),
        recommended_sources=RecommendedSources(),
        stages=[
            ReportStage(name="基础认知", items=[basic]),
            ReportStage(name="实战内容", items=[practice]),
        ],
        warnings=[],
    )

    markdown = render_report_markdown(report)

    assert markdown.index("## 基础认知") < markdown.index("## 实战内容")
    assert "基础内容" in markdown
    assert "实践内容" in markdown
    assert "## 整合摘要" in markdown
    assert "未选择内容" not in markdown


def test_markdown_neutralizes_line_breaks_and_unsafe_url_characters():
    malicious = item("unsafe", "标题\n## 注入章节", "基础认知")
    malicious.url = "https://example.com/a path?q=(value)>"
    report = DiscoveryReport(
        title="报告\n# 伪标题",
        query="机器学习",
        keywords=["机器学习"],
        intent="learning",
        structure_name="学习型",
        stage_order=["基础认知", "方法与工具", "实战内容", "进阶方向"],
        overview=ReportOverview(topic_summary="概览"),
        recommended_sources=RecommendedSources(),
        stages=[ReportStage(name="基础认知", items=[malicious])],
        warnings=[],
    )

    markdown = render_report_markdown(report)

    assert "\n## 注入章节" not in markdown
    assert "\n# 伪标题" not in markdown
    assert "a%20path" in markdown
    assert "%28value%29%3E" in markdown
