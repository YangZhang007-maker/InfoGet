"""FastAPI routes for academic source analysis and crawling."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional

import requests
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, HttpUrl, field_validator

from .models import AcademicSearchRequest
from .security import UnsafeUrlError
from .service import AcademicCrawlerService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/academic", tags=["academic"])


class AcademicCrawlRequest(BaseModel):
    source_url: HttpUrl
    keywords: List[str] = Field(min_length=1, max_length=10)
    time_range_days: Optional[int] = Field(default=None, ge=1, le=3650)
    min_citations: Optional[int] = Field(default=None, ge=0, le=10_000_000)
    recent_days: Optional[int] = Field(default=None, ge=1, le=3650)
    max_results: int = Field(default=20, ge=1, le=50)
    render_javascript: bool = False
    output_format: Literal["json", "markdown"] = "json"
    selectors: Optional[Dict[str, Any]] = None

    @field_validator("selectors")
    @classmethod
    def validate_selectors(cls, value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if value is None:
            return None
        if len(value) > 20:
            raise ValueError("selectors 配置字段过多")
        for key, item in value.items():
            if not isinstance(key, str) or len(key) > 50:
                raise ValueError("selectors 字段名无效")
            if isinstance(item, str) and len(item) > 300:
                raise ValueError("selector 过长")
            if not isinstance(item, (str, bool)):
                raise ValueError("selector 只能是字符串或布尔值")
        return value

    @field_validator("keywords")
    @classmethod
    def clean_keywords(cls, value: List[str]) -> List[str]:
        cleaned = [keyword.strip() for keyword in value if keyword.strip()]
        if not cleaned:
            raise ValueError("请至少提供一个有效关键词")
        return cleaned


@router.post("/crawl")
async def crawl_academic_source(payload: AcademicCrawlRequest):
    request = AcademicSearchRequest(
        source_url=str(payload.source_url),
        keywords=payload.keywords,
        time_range_days=payload.time_range_days,
        min_citations=payload.min_citations,
        recent_days=payload.recent_days,
        max_results=payload.max_results,
        render_javascript=payload.render_javascript,
        output_format=payload.output_format,
        selectors=payload.selectors,
    )
    try:
        result = await run_in_threadpool(AcademicCrawlerService().search, request)
        response = result.to_dict()
        response["formatted_output"] = (
            result.markdown if payload.output_format == "markdown" else response["articles"]
        )
        return response
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except requests.Timeout as exc:
        raise HTTPException(status_code=504, detail="目标学术网站响应超时") from exc
    except requests.RequestException as exc:
        logger.warning("Academic source request failed: %s", exc)
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code in {401, 403}:
            raise HTTPException(
                status_code=502,
                detail=(
                    "目标网站需要登录或启用了强访问保护。建议优先使用该站官方 API、RSS/导出功能，"
                    "或在获得授权后配置 Playwright 登录会话；不要绕过验证码或访问控制。"
                ),
            ) from exc
        raise HTTPException(status_code=502, detail=f"无法访问目标学术网站: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Academic crawl failed")
        raise HTTPException(status_code=500, detail=f"学术信息采集失败: {exc}") from exc


@router.get("/examples")
async def academic_examples():
    from .examples import EXAMPLE_CONFIGS

    return {
        "sources": [
            {"name": "arXiv", "url": "https://arxiv.org/", "mode": "official_api"},
            {"name": "PubMed", "url": "https://pubmed.ncbi.nlm.nih.gov/", "mode": "official_api"},
            {"name": "Google Scholar", "url": "https://scholar.google.com/", "mode": "openalex_alternative"},
        ],
        "selector_configs": EXAMPLE_CONFIGS,
    }
