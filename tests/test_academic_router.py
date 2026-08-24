from fastapi.testclient import TestClient

from custom_source.server import app
from get_acdemic_info.models import AcademicArticle, AcademicSearchResult
from get_acdemic_info.service import AcademicCrawlerService


def test_academic_crawl_route(monkeypatch):
    def fake_search(self, request):
        return AcademicSearchResult(
            source_url=request.source_url,
            source_name="arXiv",
            strategy="official_api",
            articles=[
                AcademicArticle(
                    title="Transformer Paper",
                    url="https://arxiv.org/abs/1234",
                    authors=["Ada"],
                    published_at="2026-08-20",
                    abstract="A result",
                    hot_score=88,
                    source="arXiv",
                )
            ],
            generated_code="# generated",
            markdown="| paper |",
        )

    monkeypatch.setattr(AcademicCrawlerService, "search", fake_search)
    client = TestClient(app)
    response = client.post(
        "/api/academic/crawl",
        json={
            "source_url": "https://arxiv.org/",
            "keywords": ["transformer"],
            "output_format": "json",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["strategy"] == "official_api"
    assert data["articles"][0]["title"] == "Transformer Paper"
