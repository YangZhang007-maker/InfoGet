"""
每日热榜 - 增强版后端 API 服务

提供自定义信息源搜索端点，供前端调用。
"""

import os
import sys
import asyncio
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 支持包导入和脚本运行两种方式
try:
    from .custom_source import custom_search, match_platform, get_platform_name
except (ImportError, ValueError):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from custom_source import custom_search, match_platform, get_platform_name

app = FastAPI(
    title="每日热榜增强API",
    description="自定义信息源搜索 + 智能热点提取",
    version="1.0.0",
)

# CORS 开放，允许前端调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# 请求/响应模型
# ============================================

class CustomSearchRequest(BaseModel):
    urls: List[str]
    interests: List[str]
    max_per_source: int = 20


class HotItemResp(BaseModel):
    title: str
    hot: str = ""
    url: str = ""
    desc: str = ""
    rank: int = 0
    source_platform: Optional[str] = None
    source_name: str = ""
    summary: str = ""
    relevance: int = 0
    match_type: str = ""


class SourceResult(BaseModel):
    source_url: str
    source_name: str
    matched_platform: Optional[str] = None
    is_known: bool = False
    items: List[HotItemResp] = []
    error: Optional[str] = None


class CustomSearchResponse(BaseModel):
    results: List[SourceResult]
    total_sources: int
    total_items: int


# ============================================
# 端点
# ============================================

@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "daily-hot-enhancer"}


@app.post("/api/custom-search", response_model=CustomSearchResponse)
async def api_custom_search(req: CustomSearchRequest):
    """
    自定义信息源搜索

    接收用户输入的网站 URL 和兴趣方向，
    判断已知/未知平台，返回筛选/提取的热点信息。
    """
    if not req.urls:
        raise HTTPException(status_code=400, detail="请提供至少一个网站 URL")

    if not req.interests:
        raise HTTPException(status_code=400, detail="请提供至少一个兴趣方向")

    # 过滤空字符串
    urls = [u.strip() for u in req.urls if u.strip()]
    interests = [i.strip() for i in req.interests if i.strip()]

    if not urls:
        raise HTTPException(status_code=400, detail="URL 列表为空")
    if not interests:
        raise HTTPException(status_code=400, detail="兴趣方向列表为空")

    # 执行搜索
    search_results = await custom_search(urls, interests, req.max_per_source)

    # 转换为响应模型
    results = []
    total_items = 0
    for r in search_results:
        items = [
            HotItemResp(
                title=item.get("title", ""),
                hot=str(item.get("hot", "")),
                url=item.get("url", ""),
                desc=item.get("desc", item.get("summary", "")),
                rank=item.get("rank", 0),
                source_platform=item.get("source_platform"),
                source_name=item.get("source_name", r.source_name),
                summary=item.get("summary", ""),
                relevance=item.get("relevance", 0),
                match_type=item.get("match_type", ""),
            )
            for item in r.items
        ]
        total_items += len(items)
        results.append(SourceResult(
            source_url=r.source_url,
            source_name=r.source_name,
            matched_platform=r.matched_platform,
            is_known=r.is_known,
            items=items,
            error=r.error,
        ))

    return CustomSearchResponse(
        results=results,
        total_sources=len(results),
        total_items=total_items,
    )


@app.post("/api/check-platform")
async def api_check_platform(url: str):
    """检查 URL 是否匹配已知平台"""
    platform_id = match_platform(url)
    if platform_id:
        return {
            "matched": True,
            "platform_id": platform_id,
            "platform_name": get_platform_name(platform_id),
        }
    return {"matched": False}


# ============================================
# 启动入口
# ============================================
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("ENHANCER_PORT", "5001"))
    print(f"🚀 启动每日热榜增强后端...")
    print(f"   📡 API: http://localhost:{port}")
    print(f"   📋 文档: http://localhost:{port}/docs")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")