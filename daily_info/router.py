"""FastAPI routes for the daily information dashboard."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from .models import DailyTopResponse
from .service import DailyTopService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/daily-info", tags=["daily-info"])
service = DailyTopService()


@router.get("/top20", response_model=DailyTopResponse)
async def get_daily_top20(
    refresh: bool = Query(default=False, description="忽略当日快照并重新聚合"),
) -> DailyTopResponse:
    try:
        return await service.get_top20(force=refresh)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Daily Top20 generation failed")
        raise HTTPException(status_code=500, detail="每日 Top20 生成失败") from exc
