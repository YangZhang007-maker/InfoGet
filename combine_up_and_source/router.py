"""FastAPI route for combined recommendation and source discovery."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from .report_models import ReportRequest, ReportResponse
from .report_service import DiscoveryReportService
from .service import CombinedDiscoveryService
from .storage import SnapshotCorruptError, SnapshotNotFoundError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/combined-discovery", tags=["combined-discovery"])


class CombinedDiscoveryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    max_bloggers: int = Field(default=6, ge=1, le=8)
    batch_size: int = Field(default=3, ge=1, le=5)
    max_per_source: int = Field(default=10, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def clean_query(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("请输入感兴趣的内容")
        return cleaned


@router.post("/run")
async def run_combined_discovery(payload: CombinedDiscoveryRequest):
    try:
        return await CombinedDiscoveryService().discover(
            payload.query,
            max_bloggers=payload.max_bloggers,
            batch_size=payload.batch_size,
            max_per_source=payload.max_per_source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Combined discovery failed")
        raise HTTPException(status_code=500, detail="智能发现失败，请查看服务日志") from exc


@router.post("/reports", response_model=ReportResponse)
async def generate_discovery_report(payload: ReportRequest):
    try:
        service = DiscoveryReportService()
        if payload.detail == "brief":
            # Keep the default call compatible with integrations that wrap the
            # original two-argument service method.
            return await service.generate(str(payload.discovery_id), payload.amount)
        return await service.generate(
            str(payload.discovery_id), payload.amount, payload.detail
        )
    except SnapshotNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SnapshotCorruptError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Discovery report generation failed")
        raise HTTPException(status_code=500, detail="展示报告生成失败，请查看服务日志") from exc
