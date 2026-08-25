"""Orchestrate custom-source crawler analysis, execution, and persistence."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from .analyzer import CrawlPlanAnalyzer
from .code_generator import CrawlerCodeGenerator
from .detector import assess_access
from .engine import CrawlBlockedError, CrawlerEngine
from .http import CrawlerHttpClient
from .models import CrawlPlan, CrawlRequest, CrawlResult
from .plan_validator import validate_plan
from .robots import inspect_robots
from .storage import CrawlerStorage
try:
    from ...get_acdemic_info.security import validate_public_url
except (ImportError, ValueError):
    from get_acdemic_info.security import validate_public_url

logger = logging.getLogger(__name__)


class CustomCrawlerService:
    def __init__(
        self,
        *,
        analyzer: CrawlPlanAnalyzer | None = None,
        storage: CrawlerStorage | None = None,
        generator: CrawlerCodeGenerator | None = None,
    ) -> None:
        self.analyzer = analyzer or CrawlPlanAnalyzer()
        self.storage = storage or CrawlerStorage()
        self.generator = generator or CrawlerCodeGenerator()

    def analyze(self, request: CrawlRequest) -> dict:
        source_url = validate_public_url(request.source_url)
        keywords = self._clean_keywords(request.keywords)
        client = CrawlerHttpClient(delay=0.5)
        policy = inspect_robots(source_url, client)
        if not policy.allowed:
            raise CrawlBlockedError("robots.txt 不允许自动抓取该路径")

        response = client.get(source_url)
        if (urlparse(response.url).hostname or "").lower() != (urlparse(source_url).hostname or "").lower():
            raise CrawlBlockedError("目标网站重定向到不同域名，已终止分析")
        assessment = assess_access(response.status_code, response.text)
        warnings = policy.warnings + assessment.warnings
        if assessment.blocked:
            raise CrawlBlockedError("目标网站要求登录、授权或验证码，已终止分析")
        response.raise_for_status()

        plan = validate_plan(self.analyzer.analyze(response.text, response.url, keywords))
        code, generated_file = self.generator.generate(plan)
        analysis_id = uuid.uuid4().hex
        payload = {
            "analysis_id": analysis_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_url": source_url,
            "keywords": keywords,
            "max_pages": min(max(request.max_pages, 1), 5),
            "max_results": min(max(request.max_results, 1), 100),
            "allow_javascript": bool(request.allow_javascript),
            "crawl_delay": policy.crawl_delay,
            "robots_allowed": policy.allowed,
            "robots_url": policy.url,
            "warnings": list(dict.fromkeys(warnings)),
            "plan": plan.to_dict(),
            "generated_code": code,
            "generated_file": generated_file,
        }
        plan_file = self.storage.save_plan(analysis_id, payload)
        payload["plan_file"] = str(plan_file)
        return payload

    def run(self, analysis_id: str) -> CrawlResult:
        bundle = self.storage.load_plan(analysis_id)
        plan = validate_plan(CrawlPlan(**bundle["plan"]))
        articles, run_warnings = CrawlerEngine().execute(
            plan,
            self._clean_keywords(bundle["keywords"]),
            max_pages=int(bundle.get("max_pages", 3)),
            max_results=int(bundle.get("max_results", 30)),
            allow_javascript=bool(bundle.get("allow_javascript", False)),
            crawl_delay=float(bundle.get("crawl_delay", 0.0)),
        )
        run_id = uuid.uuid4().hex
        warnings = list(dict.fromkeys([*bundle.get("warnings", []), *run_warnings]))
        result = CrawlResult(
            analysis_id=analysis_id,
            source_url=plan.source_url,
            articles=articles,
            warnings=warnings,
            robots_allowed=bool(bundle.get("robots_allowed", True)),
            generated_code=bundle.get("generated_code", ""),
            plan=plan.to_dict(),
        )
        payload = result.to_dict()
        payload["run_id"] = run_id
        payload["generated_file"] = bundle.get("generated_file", "")
        json_file = self.storage.save_result(run_id, payload)
        result.json_file = str(json_file)
        payload["json_file"] = str(json_file)
        self.storage.save_result(run_id, payload)

        print(f"\n自定义源爬取完成：{len(articles)} 条，结果文件：{json_file}")
        for index, article in enumerate(articles, 1):
            print(f"{index:>2}. {article.title}\n    {article.url}")
        return result

    @staticmethod
    def _clean_keywords(keywords: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(str(value).strip() for value in keywords if str(value).strip()))
        if not cleaned:
            raise ValueError("请至少提供一个有效关键词")
        if len(cleaned) > 20 or any(len(value) > 80 for value in cleaned):
            raise ValueError("关键词最多 20 个，每个不超过 80 个字符")
        return cleaned
