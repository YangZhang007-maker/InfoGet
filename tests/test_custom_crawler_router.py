from fastapi.testclient import TestClient

from custom_source.crawler.models import CrawlerArticle, CrawlResult
from custom_source.server import app


client = TestClient(app)


def test_custom_crawler_analyze_route(monkeypatch):
    def fake_analyze(_self, request):
        return {
            "analysis_id": "a" * 32,
            "source_url": request.source_url,
            "warnings": [],
            "plan": {"item_selector": "article"},
            "generated_code": "print('ok')",
        }

    monkeypatch.setattr("custom_source.crawler.router.CustomCrawlerService.analyze", fake_analyze)
    response = client.post("/api/custom-crawler/analyze", json={
        "source_url": "https://example.com/news", "keywords": ["AI"]
    })
    assert response.status_code == 200
    assert response.json()["analysis_id"] == "a" * 32


def test_custom_crawler_run_route(monkeypatch):
    article = CrawlerArticle("AI news", "2026-08-20", "summary", "https://example.com/ai", matched_keywords=["AI"])
    result = CrawlResult("a" * 32, "https://example.com", [article], json_file="results.json")
    monkeypatch.setattr("custom_source.crawler.router.CustomCrawlerService.run", lambda _self, _id: result)
    response = client.post("/api/custom-crawler/run", json={"analysis_id": "a" * 32})
    assert response.status_code == 200
    assert response.json()["articles"][0]["title"] == "AI news"


def test_custom_crawler_rejects_empty_keywords():
    response = client.post("/api/custom-crawler/analyze", json={
        "source_url": "https://example.com", "keywords": []
    })
    assert response.status_code == 422
