from combine_up_and_source.report_candidates import ReportCandidateBuilder


def snapshot_with_items(items, *, keywords=None, source_name="示例平台"):
    return {
        "result": {
            "query": "机器学习",
            "keywords": keywords or ["机器学习", "Python"],
            "recommendation": {"bloggers": [], "platforms": []},
            "source_inputs": [],
            "batches": [{
                "status": "completed",
                "results": [{
                    "source_url": "https://example.com",
                    "source_name": source_name,
                    "matched_platform": source_name,
                    "items": items,
                }],
            }],
        }
    }


def test_filters_invalid_items_and_deduplicates_normalized_urls():
    snapshot = snapshot_with_items([
        {"title": "", "url": "https://example.com/empty"},
        {"title": "错误协议", "url": "javascript:alert(1)"},
        {
            "title": "Python机器学习项目实战",
            "url": "https://Example.com:443/post?id=1&utm_source=x#section",
            "summary": "完整项目与模型训练步骤",
            "hot": "1.2万",
            "relevance": 90,
        },
        {
            "title": "Python机器学习项目实战",
            "url": "https://example.com/post?utm_medium=social&id=1",
            "summary": "短摘要",
            "relevance": 30,
        },
    ])

    candidates = ReportCandidateBuilder().build(snapshot, amount=10)

    assert len(candidates) == 1
    assert candidates[0].url.endswith("utm_source=x#section")
    assert candidates[0].normalized_url == "https://example.com/post?id=1"
    assert candidates[0].source_key == "example.com"


def test_source_key_uses_source_domain_instead_of_display_name():
    snapshot = {
        "result": {
            "query": "机器学习",
            "keywords": ["机器学习"],
            "recommendation": {"bloggers": [], "platforms": []},
            "source_inputs": [],
            "batches": [{
                "status": "completed",
                "results": [
                    {
                        "source_url": "https://example.com/channel-a",
                        "source_name": "展示名 A",
                        "items": [{"title": "机器学习 A", "url": "https://example.com/a"}],
                    },
                    {
                        "source_url": "https://example.com/channel-b",
                        "source_name": "展示名 B",
                        "items": [{"title": "机器学习 B", "url": "https://example.com/b"}],
                    },
                ],
            }],
        }
    }

    candidates = ReportCandidateBuilder().build(snapshot, amount=10)

    assert {candidate.source_key for candidate in candidates} == {"example.com"}


def test_deduplicates_highly_similar_titles_across_urls():
    snapshot = snapshot_with_items([
        {
            "title": "机器学习 Python 项目实战教程",
            "url": "https://example.com/a",
            "summary": "短摘要",
        },
        {
            "title": "机器学习Python项目实战教程！",
            "url": "https://example.com/b",
            "summary": "更完整的项目训练、评估和部署步骤",
            "relevance": 80,
        },
    ])

    candidates = ReportCandidateBuilder().build(snapshot, amount=10)

    assert len(candidates) == 1
    assert candidates[0].url == "https://example.com/b"


def test_title_match_scores_higher_than_summary_only_match():
    snapshot = snapshot_with_items([
        {
            "title": "机器学习基础教程",
            "url": "https://example.com/title",
            "summary": "适合初学者",
        },
        {
            "title": "数据分析基础教程",
            "url": "https://example.com/summary",
            "summary": "包含机器学习相关内容",
        },
    ], keywords=["机器学习"])

    candidates = ReportCandidateBuilder().build(snapshot, amount=10)

    scores = {candidate.url: candidate.rule_score for candidate in candidates}
    assert scores["https://example.com/title"] > scores["https://example.com/summary"]


def test_candidate_ids_and_order_are_stable():
    snapshot = snapshot_with_items([
        {"title": "机器学习 A", "url": "https://example.com/a"},
        {"title": "机器学习 B", "url": "https://example.com/b"},
    ])
    builder = ReportCandidateBuilder()

    first = builder.build(snapshot, amount=10)
    second = builder.build(snapshot, amount=10)

    assert [item.item_id for item in first] == [item.item_id for item in second]
    assert [item.url for item in first] == [item.url for item in second]


def test_candidate_shortlist_is_capped_at_sixty():
    items = [
        {
            "title": f"机器学习独立主题 {index}",
            "url": f"https://example.com/{index}",
        }
        for index in range(100)
    ]

    candidates = ReportCandidateBuilder().build(
        snapshot_with_items(items), amount=30
    )

    assert len(candidates) == 60
    assert all(0 <= item.rule_score <= 100 for item in candidates)
