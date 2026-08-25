"""FastAPI routes for custom-source crawler analysis and execution."""

from __future__ import annotations

import logging
from typing import List

import requests
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, HttpUrl, field_validator

from .engine import CrawlBlockedError
from .models import CrawlRequest
from .service import CustomCrawlerService
try:
    from ...get_acdemic_info.security import UnsafeUrlError
except (ImportError, ValueError):
    from get_acdemic_info.security import UnsafeUrlError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/custom-crawler", tags=["custom-crawler"])


class AnalyzeRequest(BaseModel):
    source_url: HttpUrl
    keywords: List[str] = Field(min_length=1, max_length=20)
    max_pages: int = Field(default=3, ge=1, le=5)
    max_results: int = Field(default=30, ge=1, le=100)
    allow_javascript: bool = False

    @field_validator("keywords")
    @classmethod
    def clean_keywords(cls, values: List[str]) -> List[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if not cleaned:
            raise ValueError("请至少提供一个有效关键词")
        if any(len(value) > 80 for value in cleaned):
            raise ValueError("单个关键词不能超过 80 个字符")
        return cleaned


class RunRequest(BaseModel):
    analysis_id: str = Field(pattern=r"^[a-f0-9]{32}$")


@router.post("/analyze")
async def analyze_custom_source(payload: AnalyzeRequest):
    request = CrawlRequest(
        source_url=str(payload.source_url),
        keywords=payload.keywords,
        max_pages=payload.max_pages,
        max_results=payload.max_results,
        allow_javascript=payload.allow_javascript,
    )
    try:
        return await run_in_threadpool(CustomCrawlerService().analyze, request)
    except (UnsafeUrlError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CrawlBlockedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except requests.Timeout as exc:
        raise HTTPException(status_code=504, detail="目标网站响应超时") from exc
    except requests.RequestException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in {401, 403}:
            detail = "目标网站需要登录或启用了访问保护，已终止。请改用官方 API、RSS 或公开导出功能。"
        else:
            detail = f"无法访问目标网站：{exc}"
        raise HTTPException(status_code=502, detail=detail) from exc
    except Exception as exc:
        logger.exception("Custom crawler analysis failed")
        raise HTTPException(status_code=500, detail=f"网站分析失败：{exc}") from exc


@router.post("/run")
async def run_custom_source(payload: RunRequest):
    try:
        return (await run_in_threadpool(CustomCrawlerService().run, payload.analysis_id)).to_dict()
    except (UnsafeUrlError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CrawlBlockedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except requests.Timeout as exc:
        raise HTTPException(status_code=504, detail="目标网站响应超时") from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"抓取目标网站失败：{exc}") from exc
    except Exception as exc:
        logger.exception("Custom crawler run failed")
        raise HTTPException(status_code=500, detail=f"爬虫执行失败：{exc}") from exc

