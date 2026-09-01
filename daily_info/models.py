"""Response models for the daily information module."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DailyRankedItem(BaseModel):
    id: str | int
    title: str
    url: str
    mobile_url: str = ""
    description: str = ""
    hot: float | None = None
    timestamp: float | None = None
    platform_id: str
    platform_name: str
    platform_rank: int = Field(ge=1)


class DailyTopResponse(BaseModel):
    schema_version: int = 1
    date: str
    generated_at: str
    cached: bool = False
    source_count: int = Field(ge=0)
    failed_sources: list[str] = Field(default_factory=list)
    items: list[DailyRankedItem] = Field(default_factory=list)
