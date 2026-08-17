"""
推荐博主 FastAPI 路由

POST /api/recommend
"""

import os
import sys
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# 支持包导入和脚本运行
try:
    from .recommender import recommend
except (ImportError, ValueError):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from recommender import recommend

router = APIRouter(prefix="/api", tags=["recommend"])


class RecommendRequest(BaseModel):
    query: str
    max_bloggers: int = 6


class BloggerInfo(BaseModel):
    name: str
    fans: int = 0
    fans_text: str = ""
    sign: str = ""
    avatar: str = ""
    profile_url: str = ""
    video_count: int = 0
    sample_video: str = ""
    sample_url: str = ""
    reason: str = ""


class PlatformInfo(BaseModel):
    name: str
    link: str
    reason: str = ""


class RecommendResponse(BaseModel):
    query: str
    keywords: List[str] = []
    bloggers: List[BloggerInfo] = []
    platforms: List[PlatformInfo] = []


@router.post("/recommend", response_model=RecommendResponse)
async def api_recommend(req: RecommendRequest):
    """推荐相关平台和博主"""
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="请输入关心的问题或感兴趣的内容")

    result = recommend(req.query.strip(), req.max_bloggers)

    return RecommendResponse(
        query=result["query"],
        keywords=result["keywords"],
        bloggers=[BloggerInfo(**b) for b in result["bloggers"]],
        platforms=[PlatformInfo(**p) for p in result["platforms"]],
    )
