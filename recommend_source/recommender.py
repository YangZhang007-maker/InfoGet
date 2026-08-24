"""
推荐博主核心逻辑

数据流：
  用户输入 → Codex 模型提取关键词+推荐平台 → B站搜索API收集视频 →
  统计UP主频次 → B站用户卡API获取粉丝/简介 → 按粉丝数排序 → 返回
"""

import os
import sys
import json
import requests
from typing import List, Dict, Any, Optional
from urllib.parse import quote

# 支持包导入和脚本运行
try:
    from ..codex_llm import call_codex_responses
except (ImportError, ValueError):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from codex_llm import call_codex_responses


# ============================================
# Codex：提取关键词 + 推荐平台
# ============================================

def extract_keywords_and_platforms(query: str) -> Dict[str, Any]:
    """
    用 Codex 模型从用户输入中提取：
    1. 领域搜索关键词（用于B站搜索）
    2. 推荐的其他平台及理由（不编博主，只推荐平台）

    Args:
        query: 用户输入的问题或兴趣描述

    Returns:
        {"keywords": [...], "platforms": [{name, link, reason}]}
    """
    system_prompt = (
        "你是一个内容推荐助手。用户会输入关心的问题或感兴趣的内容。\n"
        "请完成两个任务：\n"
        "1. 提取 2-3 个用于搜索该领域的简短关键词（中文优先，最长不超过6个字）\n"
        "2. 推荐 3-5 个适合获取该领域内容的平台（从以下列表选择或补充）：\n"
        "   微博(weibo.com)、知乎(zhihu.com)、抖音(douyin.com)、36氪(36kr.com)、\n"
        "   虎嗅(huxiu.com)、IT之家(ithome.com)、CSDN(csdn.net)、掘金(juejin.cn)、\n"
        "   小红书(xiaohongshu.com)、澎湃新闻(thepaper.cn)、豆瓣(douban.com)\n"
        "严格只返回 JSON，格式：\n"
        '{"keywords": ["关键词1", "关键词2"], "platforms": [{"name": "平台名", "link": "https://域名", "reason": "一句话理由"}]}'
    )

    try:
        content = call_codex_responses(
            system_prompt,
            f"用户关心的内容：{query}",
            max_output_tokens=800,
            timeout=45,
        )

        # 清理 markdown
        content = content.strip()
        for prefix in ["```json", "```"]:
            if content.startswith(prefix):
                content = content[len(prefix):]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        result = json.loads(content)
        return {
            "keywords": result.get("keywords", [])[:3],
            "platforms": result.get("platforms", [])[:5],
        }

    except Exception as e:
        print(f"[Recommend] LLM 提取失败: {e}")
        # 兜底：用原始 query 作为关键词
        return {"keywords": [query[:6]], "platforms": []}


# ============================================
# B站搜索：收集领域视频及UP主
# ============================================

def search_bilibili_videos(keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    用 B站搜索API 搜索关键词，返回带 author/mid 的视频列表
    """
    try:
        session = requests.Session()
        session.get("https://www.bilibili.com", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)

        resp = session.get(
            "https://api.bilibili.com/x/web-interface/search/type",
            params={"keyword": keyword, "search_type": "video", "order": "click", "page": 1},
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Referer": f"https://search.bilibili.com/all?keyword={quote(keyword, safe='')}",
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        if data.get("code") != 0:
            return []

        results = []
        for item in data.get("data", {}).get("result", [])[:limit]:
            title = item.get("title", "").replace('<em class="keyword">', "").replace("</em>", "")
            mid = item.get("mid", "")
            author = item.get("author", "")
            if title and mid:
                results.append({
                    "title": title,
                    "author": author,
                    "mid": str(mid),
                    "play": item.get("play", 0),
                    "url": f"https://www.bilibili.com/video/{item.get('bvid', '')}",
                })
        return results

    except Exception as e:
        print(f"[Recommend] B站搜索 '{keyword}' 失败: {e}")
        return []


# ============================================
# B站用户卡：获取博主信息
# ============================================

def get_up_info(mid: str) -> Optional[Dict[str, Any]]:
    """
    用 B站用户卡API 获取 UP主 的粉丝数/简介/头像/主页链接
    """
    try:
        resp = requests.get(
            "https://api.bilibili.com/x/web-interface/card",
            params={"mid": mid},
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Referer": "https://www.bilibili.com",
            },
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("code") != 0:
            return None

        card = data.get("data", {}).get("card", {})
        return {
            "name": card.get("name", ""),
            "fans": card.get("fans", 0),
            "sign": card.get("sign", ""),
            "avatar": card.get("face", ""),
            "profile_url": f"https://space.bilibili.com/{mid}",
            "mid": mid,
        }

    except Exception as e:
        print(f"[Recommend] 用户卡 {mid} 失败: {e}")
        return None


def format_fans(fans: int) -> str:
    """格式化粉丝数"""
    if fans >= 10000_0000:
        return f"{fans / 10000_0000:.1f}亿"
    if fans >= 10000:
        return f"{fans / 10000:.1f}万"
    return str(fans)


# ============================================
# 主推荐入口
# ============================================

def recommend(query: str, max_bloggers: int = 6) -> Dict[str, Any]:
    """
    推荐主入口

    Args:
        query: 用户输入的问题或兴趣描述
        max_bloggers: 最多推荐的博主数

    Returns:
        {"keywords": [...], "bloggers": [...], "platforms": [...]}
    """
    print(f"[Recommend] 用户输入: {query}")

    # 步骤1: LLM 提取关键词 + 推荐平台
    llm_result = extract_keywords_and_platforms(query)
    keywords = llm_result["keywords"]
    platforms = llm_result["platforms"]
    print(f"[Recommend] 关键词: {keywords}")
    print(f"[Recommend] 平台: {[p['name'] for p in platforms]}")

    # 步骤2: B站搜索每个关键词，收集视频和UP主
    all_videos = []
    for kw in keywords:
        videos = search_bilibili_videos(kw, limit=10)
        all_videos.extend(videos)
        print(f"[Recommend] '{kw}' → {len(videos)} 条视频")

    # 步骤3: 统计UP主频次
    author_stats: Dict[str, Dict[str, Any]] = {}
    for video in all_videos:
        mid = video["mid"]
        if mid not in author_stats:
            author_stats[mid] = {
                "mid": mid,
                "name": video["author"],
                "count": 0,
                "sample_video": video["title"],
                "sample_url": video["url"],
            }
        author_stats[mid]["count"] += 1

    # 按频次排序取 top 候选
    candidates = sorted(author_stats.values(), key=lambda x: x["count"], reverse=True)[:15]
    print(f"[Recommend] 候选UP主: {len(candidates)} 位")

    # 步骤4: 用户卡API获取详细信息
    bloggers = []
    for cand in candidates:
        info = get_up_info(cand["mid"])
        if info and info["name"]:
            bloggers.append({
                "name": info["name"],
                "fans": info["fans"],
                "fans_text": format_fans(info["fans"]),
                "sign": info["sign"],
                "avatar": info["avatar"],
                "profile_url": info["profile_url"],
                "video_count": cand["count"],
                "sample_video": cand["sample_video"],
                "sample_url": cand["sample_url"],
                "reason": f"该领域视频出现 {cand['count']} 次",
            })

    # 步骤5: 按粉丝数排序（粉丝多的优先）
    bloggers.sort(key=lambda x: x["fans"], reverse=True)
    bloggers = bloggers[:max_bloggers]

    print(f"[Recommend] 最终推荐 {len(bloggers)} 位博主")
    return {
        "query": query,
        "keywords": keywords,
        "bloggers": bloggers,
        "platforms": platforms,
    }


if __name__ == "__main__":
    # 测试
    result = recommend("我想学习AI绘画")
    print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
