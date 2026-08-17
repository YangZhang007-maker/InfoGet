"""
自定义信息源模块 - Custom Source Module

功能：
- 域名匹配：判断用户输入的网站是否在现有 54 平台 API 覆盖范围内
- 已知平台：通过现有 API 查询 + 按兴趣方向关键词过滤
- 未知平台：抓取网页 HTML → Deepseek API 提取结构化热点信息
"""

import os
import re
import sys
import json
import asyncio
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

# 支持三种导入方式：
# 1. 包导入: from custom_source.custom_source import ...（from ..api_client 生效）
# 2. 脚本运行: python3 custom_source/custom_source.py（sys.path 兜底生效）
# 3. 从项目根目录: from custom_source import ...（sys.path 兜底生效）
try:
    from ..api_client import api_client, HOT_SOURCES
    from ..config import config
except (ImportError, ValueError):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from api_client import api_client, HOT_SOURCES
    from config import config

# ============================================
# Deepseek API 配置
# ============================================
# API Key 从环境变量或项目根目录 .env 文件读取（不硬编码，避免泄露）
def _load_env_file():
    """从项目根目录 .env 加载环境变量（不覆盖已有值）

    查找顺序：项目根目录 .env → 本文件目录 .env
    """
    this_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(this_dir)  # custom_source/ 的上一级 = 项目根目录
    candidate_paths = [
        os.path.join(root_dir, ".env"),    # 项目根目录
        os.path.join(this_dir, ".env"),    # 本文件目录（兜底）
    ]
    env_path = next((p for p in candidate_paths if os.path.exists(p)), None)
    if env_path:
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key and key not in os.environ:
                            os.environ[key] = value
        except Exception:
            pass


_load_env_file()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"


@dataclass
class CustomSearchResult:
    """自定义搜索结果"""
    source_url: str
    source_name: str
    matched_platform: Optional[str] = None  # 匹配到的平台 ID，None 表示未知
    is_known: bool = False
    items: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None


# ============================================
# 域名匹配
# ============================================

# 平台域名映射（平台 ID → 常见域名关键词）
PLATFORM_DOMAIN_MAP: Dict[str, List[str]] = {
    "weibo": ["weibo.com", "weibo.cn"],
    "zhihu": ["zhihu.com"],
    "zhihu-daily": ["zhihu.com/daily", "daily.zhihu.com"],
    "bilibili": ["bilibili.com", "b23.tv"],
    "douyin": ["douyin.com"],
    "kuaishou": ["kuaishou.com"],
    "tieba": ["tieba.baidu.com", "baidu.com/tieba"],
    "douban-group": ["douban.com/group"],
    "douban-movie": ["douban.com/movie", "movie.douban.com"],
    "v2ex": ["v2ex.com"],
    "ngabbs": ["nga.cn", "ngabbs.com"],
    "hupu": ["hupu.com"],
    "baidu": ["baidu.com", "top.baidu.com"],
    "thepaper": ["thepaper.cn"],
    "toutiao": ["toutiao.com"],
    "36kr": ["36kr.com"],
    "qq-news": ["news.qq.com"],
    "sina": ["sina.com.cn"],
    "sina-news": ["news.sina.com.cn"],
    "netease-news": ["news.163.com"],
    "huxiu": ["huxiu.com"],
    "ifanr": ["ifanr.com"],
    "ithome": ["ithome.com"],
    "sspai": ["sspai.com"],
    "csdn": ["csdn.net"],
    "juejin": ["juejin.cn"],
    "51cto": ["51cto.com"],
    "nodeseek": ["nodeseek.com"],
    "hellogithub": ["hellogithub.com"],
    "coolapk": ["coolapk.com"],
    "acfun": ["acfun.cn"],
    "genshin": ["ys.mihoyo.com", "genshin"],
    "miyoushe": ["miyoushe.com"],
    "honkai": ["bh3.com", "honkai"],
    "starrail": ["hsr.com", "starrail"],
    "lol": ["lol.qq.com"],
    "jianshu": ["jianshu.com"],
    "guokr": ["guokr.com"],
    "weread": ["weread.qq.com"],
    "52pojie": ["52pojie.cn"],
    "hostloc": ["hostloc.com"],
    "weatheralarm": ["weather.com.cn", "nmc.cn"],
    "earthquake": ["cea.gov.cn", "earthquake"],
    "history": ["history"],
}


def extract_domain(url: str) -> str:
    """从 URL 中提取域名"""
    if not url:
        return ""
    # 如果没有协议前缀，自动添加
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # 去掉 www 前缀
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return url.lower()


def match_platform(url: str) -> Optional[str]:
    """
    判断 URL 是否匹配已知的 54 个平台之一
    支持 URL、域名、中文名称（如"微博""B站""知乎"）

    Args:
        url: 用户输入

    Returns:
        匹配到的平台 ID，或 None（未匹配）
    """
    input_lower = url.lower().strip()

    # 如果是纯中文名/别名（不含 :// 和 .），直接搜索平台名称
    if "://" not in input_lower and "." not in input_lower:
        # 别名映射（常用简称 → 平台ID）
        ALIASES = {
            "b站": "bilibili", "bilibili": "bilibili",
            "a站": "acfun", "acfun": "acfun",
            "nga": "ngabbs",
            "网易": "netease-news", "网易新闻": "netease-news",
            "头条": "toutiao", "今日头条": "toutiao",
            "澎湃": "thepaper",
            "掘金": "juejin", "稀土掘金": "juejin",
            "ithome": "ithome", "it之家": "ithome",
        }
        if input_lower in ALIASES:
            return ALIASES[input_lower]
        for platform_id, source in HOT_SOURCES.items():
            if input_lower == source.name.lower() or input_lower == source.id.lower():
                return platform_id
        # 模糊匹配
        for platform_id, source in HOT_SOURCES.items():
            if input_lower in source.name.lower():
                return platform_id
        return None

    domain = extract_domain(url)
    full_url = url.lower()

    # 遍历域名映射
    for platform_id, patterns in PLATFORM_DOMAIN_MAP.items():
        for pattern in patterns:
            if pattern in domain or pattern in full_url:
                return platform_id

    # 第二层匹配：用平台名称匹配
    for platform_id, source in HOT_SOURCES.items():
        name_lower = source.name.lower()
        if name_lower in full_url or name_lower in domain:
            return platform_id

    return None


def get_platform_name(platform_id: str) -> str:
    """获取平台中文名称"""
    source = HOT_SOURCES.get(platform_id)
    if source:
        return source.name
    return platform_id


# ============================================
# 已知平台搜索
# ============================================

async def search_known_platform(
    platform_id: str,
    interests: List[str],
    max_items: int = 20
) -> List[Dict[str, Any]]:
    """
    通过现有 API 查询已知平台，按兴趣方向筛选

    Args:
        platform_id: 平台 ID
        interests: 兴趣方向关键词列表
        max_items: 最大返回条目数

    Returns:
        筛选后的热榜条目列表
    """
    try:
        data = await api_client.fetch_hot_list(platform_id)
        if not data or not data.get("data"):
            return []

        items = data["data"]
        matched_items = []

        for item in items:
            title = item.get("title", "")
            desc = item.get("desc", "")

            # 用扩展关键词做精确匹配，只用标题（避免描述中的免责声明/模板文案误命中）
            for interest in interests:
                keywords = INTEREST_RELATED_KEYWORDS.get(interest, [interest.lower()])
                matched = False
                for kw in keywords:
                    if kw.lower() in title.lower():
                        matched = True
                        break
                if matched:
                    matched_items.append({
                        "title": title,
                        "hot": item.get("hot", ""),
                        "url": item.get("url", ""),
                        "desc": desc,
                        "rank": item.get("rank", 0),
                        "source_platform": platform_id,
                        "source_name": get_platform_name(platform_id),
                        "match_type": "known_api",
                    })
                    break

        return matched_items[:max_items]

    except Exception as e:
        print(f"[CustomSource] Error searching {platform_id}: {e}")
        return []


async def search_known_platform_with_llm(
    platform_id: str,
    interests: List[str],
    max_items: int = 20
) -> List[Dict[str, Any]]:
    """
    已知平台 API 无关键词匹配结果时，用 Deepseek 对热榜数据做语义匹配

    不爬网站，而是把 API 返回的热榜标题/描述发给 LLM 做语义分析，
    找出与用户兴趣方向真正相关的内容。

    Args:
        platform_id: 平台 ID
        interests: 兴趣方向关键词列表
        max_items: 最大返回条目数

    Returns:
        语义匹配后的热榜条目列表
    """
    try:
        # 获取热榜数据（非B站平台获取50条，B站20条足够）
        if platform_id == "bilibili":
            data = await api_client.fetch_hot_list(platform_id)
        else:
            # 非B站平台直接调 DailyHotApi 获取更多数据
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{config.api_url}/{platform_id}?limit=50",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status != 200:
                        return []
                    raw = await resp.json()
                    if raw.get("code") != 200:
                        return []
                    source = HOT_SOURCES.get(platform_id)
                    data = {
                        "platform": source.name if source else platform_id,
                        "data": api_client._format_items(raw.get("data", [])),
                    }

        if not data or not data.get("data"):
            return []

        items = data["data"]

        # 构建热榜文本（标题 + 描述）
        items_text = ""
        for idx, item in enumerate(items[:50]):
            title = item.get("title", "")
            desc = item.get("desc", "")
            hot = item.get("hot", "")
            url = item.get("url", "")
            items_text += f"[{idx+1}] 标题: {title}\n"
            if desc and desc != title:
                items_text += f"    描述: {desc[:200]}\n"
            if hot:
                items_text += f"    热度: {hot}\n"
            items_text += f"    链接: {url}\n\n"

        source_name = get_platform_name(platform_id)
        interest_str = "、".join(interests)

        system_prompt = (
            "你是一个专业的内容分类助手。"
            "你会收到一个热榜列表（包含标题、描述、热度），"
            "请从中筛选出与用户指定方向真正相关的内容。"
            "注意：不要只做关键词匹配，要理解内容的实际含义。"
            "比如「汽车」方向应包含新能源车、自动驾驶、车企动态等相关内容。"
            "严格只返回 JSON 数组格式，每条包含：index（原文中的序号）、title（标题）、"
            "reason（一句话说明为什么相关）。"
            "按相关度从高到低排序，最多返回10条。如果没有相关内容则返回空数组 []。"
        )

        user_prompt = (
            f"平台：{source_name}\n"
            f"用户感兴趣的方向：{interest_str}\n\n"
            f"请从以下热榜中，筛选出与「{interest_str}」真正相关的内容：\n\n"
            f"{items_text}"
        )

        import requests as req
        resp = req.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 2000,
            },
            timeout=60,
        )
        resp.raise_for_status()
        result = resp.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "[]")

        # 清理 markdown 代码块
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # 解析 JSON
        try:
            matched = json.loads(content)
            if not isinstance(matched, list):
                matched = []
        except json.JSONDecodeError:
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match:
                try:
                    matched = json.loads(match.group())
                except json.JSONDecodeError:
                    matched = []
            else:
                matched = []

        # 回填完整的条目信息
        result_items = []
        for m in matched[:max_items]:
            idx = m.get("index", 0) - 1  # LLM 返回的 index 从 1 开始
            if 0 <= idx < len(items):
                item = items[idx]
                result_items.append({
                    "title": item.get("title", ""),
                    "hot": item.get("hot", ""),
                    "url": item.get("url", ""),
                    "desc": item.get("desc", ""),
                    "rank": item.get("rank", idx + 1),
                    "source_platform": platform_id,
                    "source_name": source_name,
                    "match_type": "llm_fallback",
                    "summary": m.get("reason", ""),
                    "relevance": m.get("relevance", 8),
                })

        print(f"[CustomSource] LLM 语义匹配: {len(result_items)} 条结果")
        return result_items

    except Exception as e:
        print(f"[CustomSource] LLM semantic match error: {e}")
        return []


# ============================================
# 未知平台搜索（Deepseek API）
# ============================================

def fetch_webpage(url: str, timeout: int = 15) -> Optional[str]:
    """
    抓取网页 HTML 内容

    Args:
        url: 网页 URL
        timeout: 超时秒数

    Returns:
        网页文本内容，失败返回 None
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()

        # 检测编码
        if resp.encoding and resp.encoding.lower() != "utf-8":
            resp.encoding = resp.apparent_encoding or "utf-8"

        return resp.text

    except requests.exceptions.Timeout:
        print(f"[CustomSource] Timeout fetching {url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[CustomSource] Error fetching {url}: {e}")
        return None


def extract_text_from_html(html: str, max_chars: int = 8000) -> str:
    """
    从 HTML 中提取可见文本

    Args:
        html: HTML 内容
        max_chars: 最大字符数（避免 token 超限）

    Returns:
        提取的纯文本
    """
    try:
        soup = BeautifulSoup(html, "html.parser")

        # 移除 script、style、nav、footer 等标签
        for tag in soup(["script", "style", "nav", "footer", "header",
                         "iframe", "noscript", "svg", "form"]):
            tag.decompose()

        # 获取文本
        text = soup.get_text(separator="\n", strip=True)

        # 压缩空白行
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]{2,}', ' ', text)

        # 截断到最大字符数
        if len(text) > max_chars:
            text = text[:max_chars] + "..."

        return text

    except Exception as e:
        print(f"[CustomSource] Error extracting text: {e}")
        return html[:max_chars]


# ============================================
# 平台板块搜索（第三层降级）
# ============================================

# 已知平台 → 板块搜索 URL 模板
# {keyword} 会被替换为用户兴趣方向关键词
PLATFORM_SECTION_SEARCH: Dict[str, Dict[str, str]] = {
    "bilibili": {
        # 分区排行 API（更可靠，不需要 wbi 签名）
        "zone_api_url": "https://api.bilibili.com/x/web-interface/ranking/v2?rid={rid}&type=all",
        "zone_interest_map": json.dumps({
            # 汽车 (rid=223)
            "汽车": 223, "车": 223, "新能源": 223, "无人驾驶": 223, "电动车": 223,
            # 科技/数码 (rid=188)
            "科技": 188, "数码": 188, "IT": 188, "互联网": 188,
            "编程": 188, "AI": 188, "人工智能": 188, "大模型": 188,
            "机器学习": 188, "深度学习": 188, "软件": 188, "硬件": 188,
            "芯片": 188, "手机": 188, "计算机": 188, "机器人": 188,
            # 游戏 (rid=4)
            "游戏": 4, "手游": 4, "网游": 4, "电竞": 4, "主机游戏": 4,
            # 医疗健康 (rid=177)
            "医疗": 177, "健康": 177, "医药": 177, "养生": 177, "医生": 177,
            # 知识/教育 (rid=36)
            "教育": 36, "学习": 36, "知识": 36, "科普": 36, "考试": 36,
            "考研": 36, "英语": 36, "读书": 36, "公开课": 36,
            # 美食 (rid=211)
            "美食": 211, "餐厅": 211, "餐饮": 211, "做饭": 211, "探店": 211, "小吃": 211,
            # 体育 (rid=234)
            "体育": 234, "运动": 234, "足球": 234, "篮球": 234, "健身": 234,
            # 科学 (rid=201)
            "科学": 201, "天文": 201, "数学": 201, "物理": 201, "化学": 201,
            # 动画 (rid=1)
            "动画": 1, "动漫": 1, "二次元": 1, "番剧": 1, "漫画": 1,
            # 音乐 (rid=3)
            "音乐": 3, "歌曲": 3, "翻唱": 3, "乐器": 3,
            # 娱乐 (rid=5)
            "娱乐": 5, "明星": 5, "八卦": 5, "综艺": 5,
            # 电视剧 (rid=11)
            "电视剧": 11, "剧集": 11, "美剧": 11, "韩剧": 11, "国产剧": 11,
            # 时尚 (rid=155)
            "时尚": 155, "穿搭": 155, "美妆": 155, "护肤": 155, "奢侈品": 155,
            # 生活 (rid=160)
            "生活": 160, "日常": 160, "vlog": 160, "家居": 160,
            # 舞蹈 (rid=129)
            "舞蹈": 129, "街舞": 129, "编舞": 129,
            # 鬼畜 (rid=119)
            "鬼畜": 119, "搞笑": 119, "幽默": 119,
            # 影视 (rid=181)
            "电影": 181, "影视": 181, "大片": 181, "影评": 181,
            # 动物 (rid=217)
            "宠物": 217, "动物": 217, "猫": 217, "狗": 217, "萌宠": 217,
            # 纪录片 (rid=177 的一部分, 用 177)
            "纪录片": 177, "历史": 177,
            # 国创 (rid=168)
            "国创": 168, "国产": 168,
        }),
        "zone_item_fields": json.dumps({
            "title": "title",
            "hot": "stat.view",
            "desc": "desc",
            "url": "short_link_v2",
            "author": "owner.name",
        }),
        # 搜索 API（如有需要，备选）
        "web_url": "https://search.bilibili.com/all?keyword={keyword}&order=click",
    },
    "weibo": {
        "api_url": "https://m.weibo.cn/api/container/getIndex?containerid=100103type%3D1%26q%3D{keyword}&page=1",
        "api_method": "GET",
        "api_headers": json.dumps({
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15",
        }),
        "api_response_path": "data.cards",
        "api_item_fields": json.dumps({
            "title": "mblog.text",
            "hot": "mblog.attitudes_count",
            "url": "mblog.id",
        }),
        "web_url": "https://s.weibo.com/weibo?q={keyword}",
    },
    "zhihu": {
        "web_url": "https://www.zhihu.com/search?type=content&q={keyword}",
    },
    "douyin": {
        "web_url": "https://www.douyin.com/search/{keyword}?type=general",
    },
    "ithome": {
        "web_url": "https://www.ithome.com/search/{keyword}.html",
    },
    "36kr": {
        "web_url": "https://36kr.com/search/articles/{keyword}",
    },
    "csdn": {
        "web_url": "https://so.csdn.net/so/search?q={keyword}&t=blog",
    },
    "juejin": {
        "web_url": "https://juejin.cn/search?query={keyword}&sort=hot",
    },
    "hupu": {
        "web_url": "https://bbs.hupu.com/search?q={keyword}",
    },
}


# 兴趣方向 → 关联词扩展（用于 Zone/Search API 结果的相关性过滤）
INTEREST_RELATED_KEYWORDS: Dict[str, List[str]] = {
    "AI": ["人工智能", "大模型", "deepseek", "chatgpt", "机器学习",
           "深度学习", "神经网络", "llm", "gpt", "claude", "copilot",
           "codex", "cursor", "智能体", "agent", "transformer", "openai",
           "语言模型", "stable diffusion", "midjourney", "aigc"],
    "汽车": ["汽车", "车", "新能源", "特斯拉", "比亚迪", "蔚来", "小鹏",
             "小米su7", "理想", "问界", "驾驶", "f1", "方程式", "漂移"],
    "金融": ["金融", "财经", "股票", "基金", "投资", "理财", "银行", "保险",
             "贷款", "利率", "汇率", "比特币", "区块链", "洗钱", "经济学",
             "贸易", "货币", "通胀", "债务", "花呗", "借呗", "征信", "消费贷"],
    "科技": ["科技", "ai", "人工智能", "芯片", "半导体", "5g", "量子",
             "航天", "太空", "机器人", "自动驾驶", "新能源", "电池"],
    "游戏": ["游戏", "手游", "网游", "原神", "崩坏", "王者荣耀", "lol",
             "英雄联盟", "switch", "ps5", "xbox", "steam", "电竞"],
    "医疗": ["医疗", "健康", "医院", "医生", "药", "病", "手术", "治疗",
             "中医", "西医", "疫苗", "癌症", "糖尿病", "心血管"],
    "教育": ["教育", "学习", "考试", "考研", "高考", "留学", "英语",
             "数学", "物理", "历史", "公开课", "教程", "课程"],
    "娱乐": ["娱乐", "明星", "八卦", "综艺", "真人秀", "选秀", "偶像", "爱豆"],
    "体育": ["体育", "足球", "篮球", "nba", "cba", "世界杯", "奥运会",
             "健身", "马拉松", "游泳", "网球", "f1", "拳击"],
    "美食": ["美食", "吃", "餐厅", "外卖", "做饭", "厨", "探店", "小吃", "火锅", "烧烤"],
    "时尚": ["时尚", "穿搭", "美妆", "护肤", "化妆", "发型", "奢侈", "潮牌"],
    "电影": ["电影", "票房", "导演", "演员", "影评", "好莱坞", "奥斯卡",
             "科幻", "喜剧", "悬疑", "动作片", "剧情", "影院", "上映", "预告片"],
    "音乐": ["音乐", "歌", "曲", "演唱会", "乐队", "rap", "hiphop", "翻唱", "乐器"],
    "宠物": ["宠物", "猫", "狗", "萌宠", "动物", "仓鼠", "鹦鹉"],
    "医疗": ["医疗", "健康", "医院", "医生", "药", "病", "手术", "治疗",
             "中医", "西医", "疫苗", "癌症", "糖尿病", "心血管", "急诊",
             "icu", "门诊", "体检", "医保", "挂号", "护士", "患者"],
    "编程": ["编程", "代码", "程序员", "python", "java", "javascript",
             "前端", "后端", "全栈", "算法", "数据结构", "github", "开源"],
    "数码": ["数码", "手机", "电脑", "笔记本", "平板", "耳机", "相机",
             "iphone", "华为", "小米", "apple", "显卡", "cpu"],
    "科学": ["科学", "物理", "化学", "生物", "天文", "宇宙", "黑洞", "量子",
             "数学", "实验", "发现", "诺贝尔"],
    "历史": ["历史", "古代", "战争", "王朝", "考古", "文明", "皇帝", "二战"],
    "动漫": ["动漫", "动画", "二次元", "番剧", "漫画", "cosplay", "手办"],
    "职场": ["职场", "工作", "面试", "简历", "薪资", "跳槽", "裁员", "996"],
    "房产": ["房产", "房价", "买房", "租房", "楼市", "房贷", "装修"],
    "旅游": ["旅游", "旅行", "景点", "酒店", "机票", "签证", "自驾", "露营"],
}


def filter_items_by_interest(
    items: List[Dict[str, Any]],
    interest: str,
) -> List[Dict[str, Any]]:
    """
    相关性过滤：检查标题/描述是否包含兴趣关键词或其关联词
    防止 Zone API 返回的宽泛分类内容（如 科技分区 混入游戏/数码）
    """
    if not items:
        return items

    # 获取扩展关键词列表（始终包含原始关键词）
    keywords = list(INTEREST_RELATED_KEYWORDS.get(interest, [interest.lower()]))
    if interest.lower() not in keywords:
        keywords.insert(0, interest.lower())

    filtered = []
    for item in items:
        title = item.get("title", "").lower()
        desc = item.get("desc", "").lower()

        # 只用标题（避免描述中的免责声明）
        matched = False
        for kw in keywords:
            if kw.lower() in title:
                matched = True
                break

        if matched:
            filtered.append(item)

    # 标题过滤为 0 → 放宽到标题 OR 描述（Zone/Search API 的分类本身已有一定相关性）
    if len(filtered) == 0 and len(items) > 0:
        for item in items:
            title = item.get("title", "").lower()
            desc = item.get("desc", "").lower()
            # skip boilerplate (find earliest marker to truncate at)
            cut_at = len(desc)
            for marker in ["⛔", "请勿", "免责", "赞助", "鸣谢", "bgm", "音乐列表"]:
                idx = desc.find(marker)
                if 0 < idx < cut_at:
                    cut_at = idx
            desc = desc[:cut_at]
            for kw in keywords:
                if kw.lower() in title or kw.lower() in desc:
                    filtered.append(item)
                    break
        if filtered:
            print(f"[RelevanceFilter] '{interest}': title=0 relaxed: {len(filtered)}/{len(items)}")

    if 0 < len(filtered) < len(items):
        print(f"[RelevanceFilter] '{interest}': {len(filtered)}/{len(items)} passed "
              f"(keywords: {keywords[:5]}...)")

    return filtered


def search_platform_zone_api(
    platform_id: str,
    interest: str,
) -> Optional[List[Dict[str, Any]]]:
    """
    通过平台的分区/频道 API 获取板块内容（最可靠的方式）

    Args:
        platform_id: 平台 ID
        interest: 单个兴趣方向关键词

    Returns:
        搜索结果列表，失败返回 None
    """
    config = PLATFORM_SECTION_SEARCH.get(platform_id)
    if not config or "zone_api_url" not in config:
        return None

    interest_map = json.loads(config.get("zone_interest_map", "{}"))

    # 精确匹配
    rid = interest_map.get(interest)
    if not rid:
        # 模糊匹配：按关键词长度降序匹配，优先匹配长关键词（更精确）
        sorted_keys = sorted(interest_map.keys(), key=len, reverse=True)
        for key in sorted_keys:
            if key in interest or interest in key:
                rid = interest_map[key]
                print(f"[SectionSearch] Fuzzy match: '{interest}' → '{key}' (rid={rid})")
                break
    if not rid:
        return None  # 该兴趣方向没有对应的分区

    try:
        url = config["zone_api_url"].replace("{rid}", str(rid))

        print(f"[SectionSearch] Zone API: {url[:80]}...")

        # 使用 Session 保持 Cookie（B站需要 Cookie 才能访问分区 API）
        session = requests.Session()
        session.get(
            "https://www.bilibili.com",
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
            timeout=10,
        )

        resp = session.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Referer": "https://www.bilibili.com",
            },
            timeout=15,
        )

        if resp.status_code != 200:
            return None

        data = resp.json()
        if data.get("code") != 0:
            return None

        items = data.get("data", {}).get("list", [])
        if not items:
            return None

        field_map = json.loads(config.get("zone_item_fields", "{}"))
        results = []
        for idx, raw in enumerate(items[:20]):
            title = _extract_field(raw, field_map.get("title", "title"))
            hot_val = _extract_field(raw, field_map.get("hot", ""))
            url_val = _extract_field(raw, field_map.get("url", ""))
            desc_val = _extract_field(raw, field_map.get("desc", ""))
            author_val = _extract_field(raw, field_map.get("author", ""))

            # 格式化热度
            if hot_val and hot_val.isdigit():
                hot_val = format_hot_str(int(hot_val))

            if not title:
                continue

            results.append({
                "title": title,
                "hot": hot_val,
                "url": url_val or f"https://www.bilibili.com/video/{raw.get('bvid', '')}",
                "desc": desc_val,
                "author": author_val,
                "rank": idx + 1,
                "source_platform": platform_id,
                "source_name": get_platform_name(platform_id),
                "match_type": "section_search_api",
            })

        # 相关性过滤
        results = filter_items_by_interest(results, interest)
        print(f"[SectionSearch] Zone API found {len(results)} items for '{interest}' (after filter)")
        # 过滤后为 0 → 降级
        if len(results) == 0:
            print(f"[SectionSearch] Zone API 无相关结果, 降级到搜索 API")
            return None
        return results

    except Exception as e:
        print(f"[SectionSearch] Zone API error: {e}")
        return None


def format_hot_str(num: int) -> str:
    """格式化热度值为可读字符串"""
    if num >= 10000_0000:
        return f"{num / 10000_0000:.1f}亿"
    elif num >= 10000:
        return f"{num / 10000:.1f}万"
    return str(num)


def search_platform_section_api(
    platform_id: str,
    interest: str,
) -> Optional[List[Dict[str, Any]]]:
    """
    尝试通过平台的搜索 API 获取板块内容

    Args:
        platform_id: 平台 ID
        interest: 单个兴趣方向关键词

    Returns:
        搜索结果列表，失败返回 None
    """
    config = PLATFORM_SECTION_SEARCH.get(platform_id)
    if not config or "api_url" not in config:
        return None  # 该平台没有配置 API 搜索

    try:
        url = config["api_url"].replace("{keyword}", interest)
        headers = json.loads(config.get("api_headers", "{}"))
        method = config.get("api_method", "GET").upper()

        print(f"[SectionSearch] Trying API: {url[:80]}...")

        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=15)
        else:
            resp = requests.post(url, headers=headers, timeout=15)

        if resp.status_code != 200:
            return None

        data = resp.json()

        # 按路径提取结果列表
        path_parts = config.get("api_response_path", "data").split(".")
        items = data
        for part in path_parts:
            if isinstance(items, dict):
                items = items.get(part, [])
            elif isinstance(items, list):
                break
            else:
                return None

        if not isinstance(items, list) or not items:
            return None

        # 提取字段
        field_map = json.loads(config.get("api_item_fields", "{}"))
        results = []
        for idx, raw in enumerate(items[:20]):
            item = {
                "title": _extract_field(raw, field_map.get("title", "title")),
                "hot": _extract_field(raw, field_map.get("hot", "")),
                "url": _extract_field(raw, field_map.get("url", "")),
                "desc": _extract_field(raw, field_map.get("desc", "")),
                "rank": idx + 1,
                "source_platform": platform_id,
                "source_name": get_platform_name(platform_id),
                "match_type": "section_search_api",
            }
            # 过滤空标题
            if item["title"]:
                results.append(item)

        print(f"[SectionSearch] API found {len(results)} items")
        return results if results else None

    except Exception as e:
        print(f"[SectionSearch] API error: {e}")
        return None


def search_bilibili_search_api(
    interest: str,
) -> Optional[List[Dict[str, Any]]]:
    """
    B站专用：用搜索 API 查找内容（需要 cookie 但不需要 wbi 签名）
    作为分区 API 覆盖不到的兜底方案
    """
    try:
        from urllib.parse import quote
        session = requests.Session()
        # 先访问首页获取 cookie
        session.get(
            "https://www.bilibili.com",
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
            timeout=10,
        )

        encoded_keyword = quote(interest, safe='')
        resp = session.get(
            "https://api.bilibili.com/x/web-interface/search/type",
            params={
                "keyword": interest,
                "search_type": "video",
                "order": "click",
                "page": 1,
            },
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Referer": f"https://search.bilibili.com/all?keyword={encoded_keyword}",
            },
            timeout=15,
        )

        if resp.status_code != 200:
            return None

        data = resp.json()
        if data.get("code") != 0:
            print(f"[SectionSearch] B站 search API failed: code={data.get('code')}")
            return None

        items = data.get("data", {}).get("result", [])
        if not items:
            return None

        results = []
        for idx, raw in enumerate(items[:20]):
            title = raw.get("title", "").replace('<em class="keyword">', "").replace("</em>", "")
            if not title:
                continue
            play = raw.get("play", 0)
            bvid = raw.get("bvid", "")
            results.append({
                "title": title,
                "hot": format_hot_str(play) if play else "",
                "url": f"https://www.bilibili.com/video/{bvid}" if bvid else raw.get("arcurl", ""),
                "desc": raw.get("description", ""),
                "author": raw.get("author", ""),
                "rank": idx + 1,
                "source_platform": "bilibili",
                "source_name": "哔哩哔哩",
                "match_type": "section_search_api",
            })

        # 相关性过滤
        results = filter_items_by_interest(results, interest)
        print(f"[SectionSearch] B站 search API found {len(results)} items for '{interest}' (after filter)")
        if len(results) == 0:
            print(f"[SectionSearch] Search API 无相关结果, 降级")
            return None
        return results

    except Exception as e:
        print(f"[SectionSearch] B站 search API error: {e}")
        return None


def search_bilibili_popular_fallback(
    interest: str,
) -> Optional[List[Dict[str, Any]]]:
    """
    B站最终兜底：从热门视频中筛选（当搜索 API 也找不到内容时）
    用 B站 popular API + Deepseek 语义匹配
    """
    try:
        session = requests.Session()
        session.get(
            "https://www.bilibili.com",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )

        resp = session.get(
            "https://api.bilibili.com/x/web-interface/popular",
            params={"ps": 50, "pn": 1},
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.bilibili.com",
            },
            timeout=15,
        )

        if resp.status_code != 200:
            return None

        data = resp.json()
        if data.get("code") != 0:
            return None

        items = data.get("data", {}).get("list", [])
        if not items:
            return None

        # 构建文本给 Deepseek
        items_text = ""
        for idx, item in enumerate(items[:50]):
            title = item.get("title", "")
            desc = item.get("desc", "")
            owner = item.get("owner", {}).get("name", "")
            stat = item.get("stat", {})
            items_text += f"[{idx+1}] {title}\n"
            if desc and len(desc) > 10:
                items_text += f"    描述: {desc[:150]}\n"
            items_text += f"    作者: {owner} | 播放: {stat.get('view', 0)}\n\n"

        system_prompt = (
            "你是一个内容筛选助手。从视频列表中找出与用户指定话题最相关的视频。"
            "严格返回 JSON 数组 [{index, title, reason}]，最多5条。"
            "没有匹配的返回 []。"
        )

        user_prompt = (
            f"请在以下B站热门视频中，找出与「{interest}」话题最相关的视频：\n\n{items_text}"
        )

        llm_resp = requests.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 1000,
            },
            timeout=30,
        )
        llm_resp.raise_for_status()
        content = llm_resp.json().get("choices", [{}])[0].get("message", {}).get("content", "[]")

        # Parse
        content = content.strip()
        for prefix in ["```json", "```"]:
            if content.startswith(prefix):
                content = content[len(prefix):]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        try:
            matched = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r'\[.*\]', content, re.DOTALL)
            matched = json.loads(match.group()) if match else []

        results = []
        for m in matched[:10]:
            idx = m.get("index", 0) - 1
            if 0 <= idx < len(items):
                item = items[idx]
                bvid = item.get("bvid", "")
                stat = item.get("stat", {})
                results.append({
                    "title": item.get("title", ""),
                    "hot": format_hot_str(stat.get("view", 0)),
                    "url": f"https://www.bilibili.com/video/{bvid}" if bvid else "",
                    "desc": item.get("desc", ""),
                    "author": item.get("owner", {}).get("name", ""),
                    "rank": idx + 1,
                    "source_platform": "bilibili",
                    "source_name": "哔哩哔哩",
                    "match_type": "section_search_api",
                    "summary": m.get("reason", ""),
                })

        # 相关性过滤
        results = filter_items_by_interest(results, interest)
        print(f"[SectionSearch] B站 popular fallback found {len(results)} items for '{interest}' (after filter)")
        return results if results else None

    except Exception as e:
        print(f"[SectionSearch] B站 popular fallback error: {e}")
        return None


def search_platform_section_web(
    platform_id: str,
    interest: str,
) -> Optional[List[Dict[str, Any]]]:
    """
    抓取平台搜索页面 HTML，用 Deepseek 提取板块内容

    Args:
        platform_id: 平台 ID
        interest: 单个兴趣方向关键词

    Returns:
        搜索结果列表，失败返回 None
    """
    config = PLATFORM_SECTION_SEARCH.get(platform_id)
    if not config:
        return None

    web_url_template = config.get("web_url")
    if not web_url_template:
        return None

    url = web_url_template.replace("{keyword}", interest)
    print(f"[SectionSearch] Trying web: {url[:80]}...")

    html = fetch_webpage(url, timeout=15)
    if not html:
        print(f"[SectionSearch] Web fetch failed for {url}")
        return None

    text = extract_text_from_html(html, max_chars=6000)
    if not text or len(text) < 100:
        return None

    source_name = get_platform_name(platform_id)

    # 用 Deepseek 提取
    system_prompt = (
        "你是一个专业的信息提取助手。"
        "从网页内容中提取与指定方向相关的热门内容。"
        "严格只返回 JSON 数组，每条包含：title（标题）、summary（一句话描述）、"
        "hot（如有热度/播放量/点赞数则填入，否则为空）。最多返回10条。"
        "没有相关内容则返回空数组 []。"
    )

    user_prompt = (
        f"来源：{source_name}\n"
        f"感兴趣的方向：{interest}\n\n"
        f"请从以下网页内容中提取与「{interest}」相关的热门条目：\n\n{text}"
    )

    try:
        resp = requests.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 2000,
            },
            timeout=60,
        )
        resp.raise_for_status()
        result = resp.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "[]")

        # 清理 markdown
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        try:
            items = json.loads(content)
            if not isinstance(items, list):
                items = []
        except json.JSONDecodeError:
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match:
                try:
                    items = json.loads(match.group())
                except json.JSONDecodeError:
                    items = []
            else:
                items = []

        # 添加来源标记，过滤无链接的条目（SPA页面常出现）
        valid_items = []
        for item in items:
            url_val = item.get("url", "").strip()
            # 跳过无链接或无效链接的条目
            if not url_val or url_val.startswith("#") or len(url_val) < 5:
                continue
            item["source_platform"] = platform_id
            item["source_name"] = source_name
            item["match_type"] = "section_search_web"
            item["rank"] = len(valid_items) + 1
            valid_items.append(item)

        print(f"[SectionSearch] Web found {len(valid_items)} valid items (filtered from {len(items)})")
        return valid_items if valid_items else None

    except Exception as e:
        print(f"[SectionSearch] Web LLM error: {e}")
        return None


def _extract_field(obj: Dict, path: str) -> str:
    """从嵌套对象中按路径提取字段值"""
    if not path or not obj:
        return ""
    parts = path.split(".")
    val = obj
    for part in parts:
        if isinstance(val, dict):
            val = val.get(part, "")
        else:
            return str(val) if val else ""
    return str(val) if val else ""


def search_platform_section(
    platform_id: str,
    interest: str,
) -> List[Dict[str, Any]]:
    """
    平台板块搜索主入口：分区API → 搜索API → 网页抓取

    Args:
        platform_id: 平台 ID
        interest: 单个兴趣方向关键词

    Returns:
        搜索结果列表
    """
    # 1. 优先：分区/频道 API（最可靠）
    zone_results = search_platform_zone_api(platform_id, interest)
    if zone_results:
        return zone_results

    # 2. B站专用：搜索 API（需要 cookie）
    if platform_id == "bilibili":
        search_results = search_bilibili_search_api(interest)
        if search_results:
            return search_results

    # 3. 备选：通用搜索 API
    api_results = search_platform_section_api(platform_id, interest)
    if api_results:
        return api_results

    # 4. B站最终兜底：热门 API + LLM 语义筛选
    if platform_id == "bilibili":
        fallback_results = search_bilibili_popular_fallback(interest)
        if fallback_results:
            return fallback_results

    # 5. 最后：网页抓取 + LLM 提取
    web_results = search_platform_section_web(platform_id, interest)
    if web_results:
        return web_results

    return []


def call_deepseek_for_extraction(
    text: str,
    interests: List[str],
    source_url: str
) -> List[Dict[str, Any]]:
    """
    调用 Deepseek API 从文本中提取热点信息

    Args:
        text: 网页文本内容
        interests: 兴趣方向关键词列表
        source_url: 来源 URL

    Returns:
        提取的热点条目列表
    """
    interest_str = "、".join(interests)

    system_prompt = (
        "你是一个专业的信息提取助手。"
        "你的任务是从网页内容中提取与用户指定方向相关的热点信息。"
        "请以 JSON 数组格式返回结果，每条包含：title（标题）、summary（一句话摘要）、"
        "relevance（相关度 1-10）。"
        "只返回相关的热点信息，如果没有相关内容则返回空数组 []。"
        "严格只返回 JSON 数组，不要包含其他文字。"
    )

    user_prompt = (
        f"网页来源：{source_url}\n\n"
        f"用户感兴趣的方向：{interest_str}\n\n"
        f"请从以下网页内容中，提取与「{interest_str}」相关的热点信息：\n\n"
        f"{text}"
    )

    try:
        resp = requests.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 2000,
            },
            timeout=60,
        )
        resp.raise_for_status()
        result = resp.json()

        # 提取回复内容
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "[]")

        # 清理可能的 markdown 代码块
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # 解析 JSON
        try:
            items = json.loads(content)
            if not isinstance(items, list):
                items = []
        except json.JSONDecodeError:
            # 尝试提取 JSON 数组部分
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match:
                try:
                    items = json.loads(match.group())
                except json.JSONDecodeError:
                    items = []
            else:
                items = []

        # 添加来源信息
        for item in items:
            item["source_url"] = source_url
            item["match_type"] = "llm_extracted"

        return items

    except requests.exceptions.Timeout:
        print("[CustomSource] Deepseek API timeout")
        return []
    except requests.exceptions.RequestException as e:
        print(f"[CustomSource] Deepseek API error: {e}")
        return []
    except Exception as e:
        print(f"[CustomSource] Unexpected error: {e}")
        return []


def extract_links_from_html(html: str, base_url: str) -> List[Dict[str, str]]:
    """从 HTML 中提取所有 <a> 标签的文本和链接"""
    links = []
    try:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            text = a.get_text(strip=True)
            if href and len(text) > 3:  # 过滤空链接和极短文本
                # 相对路径转绝对路径
                if href.startswith("/"):
                    domain = extract_domain(base_url)
                    href = f"https://{domain}{href}"
                elif not href.startswith(("http://", "https://")):
                    continue
                links.append({"text": text, "href": href})
    except Exception:
        pass
    return links


def attach_urls_to_items(
    items: List[Dict[str, Any]], links: List[Dict[str, str]]
) -> List[Dict[str, Any]]:
    """将 HTML 链接匹配到 Deepseek 提取的条目"""
    if not links:
        return items

    for item in items:
        if item.get("url") and len(item["url"]) > 5:
            continue  # 已有有效URL，跳过

        title = item.get("title", "").lower()
        best_link = ""
        best_score = 0

        for link in links:
            link_text = link["text"].lower()
            # 计算标题与链接文本的重叠度
            score = 0
            # 精确包含
            if link_text in title or title in link_text:
                score = 10
            # 共同字符数
            else:
                common = sum(1 for c in link_text if c in title)
                score = common / max(len(link_text), 1)

            if score > best_score:
                best_score = score
                best_link = link["href"]

        if best_link and best_score > 0.3:
            item["url"] = best_link

    return items


def search_unknown_source(
    url: str,
    interests: List[str]
) -> List[Dict[str, Any]]:
    """
    搜索未知平台：抓取网页 + Deepseek 提取

    Args:
        url: 网页 URL
        interests: 兴趣方向关键词列表

    Returns:
        提取的热点条目列表
    """
    # 步骤1: 抓取网页
    print(f"[CustomSource] Fetching {url}...")
    html = fetch_webpage(url)

    if not html:
        return [{
            "title": f"无法访问 {url}",
            "summary": "网页抓取失败，请检查 URL 是否正确",
            "source_url": url,
            "match_type": "error",
        }]

    # 步骤2: 提取文本
    print(f"[CustomSource] Extracting text from {url}...")
    text = extract_text_from_html(html)

    if not text or len(text) < 100:
        return [{
            "title": f"{url} 内容不足",
            "summary": "网页内容过少，无法提取有效信息",
            "source_url": url,
            "match_type": "error",
        }]

    # 步骤3: 调用 Deepseek API
    print(f"[CustomSource] Calling Deepseek API for {url}...")
    items = call_deepseek_for_extraction(text, interests, url)

    # 步骤4: 从 HTML 中提取链接并匹配到条目
    links = extract_links_from_html(html, url)
    items = attach_urls_to_items(items, links)

    return items


# ============================================
# 最终保底层：智能拆词 + 多路搜索 + LLM 精选
# ============================================

# 中文停用词（拆分时过滤）
STOP_WORDS = {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
              "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会",
              "着", "没有", "看", "好", "自己", "这", "他", "她", "它", "们",
              "那", "些", "什么", "怎么", "如何", "为什么", "哪个", "吗", "啊",
              "吧", "呢", "哦", "嗯", "哈", "呀", "哇", "使用", "方式", "方法",
              "教程"}


def split_interest_keywords(phrase: str) -> List[str]:
    """
    智能拆分用户输入的兴趣短语为多个搜索关键词

    "人工智能教程" → ["人工智能", "教程"]
    "claude code使用方式" → ["claude", "code"]
    "Python机器学习入门" → ["python", "机器学习", "入门"]

    Args:
        phrase: 原始兴趣短语

    Returns:
        拆分后的关键词列表（最多4个）
    """
    phrase_lower = phrase.lower().strip()
    keywords = []

    # 1. 先尝试匹配已知关键词（长词优先）
    all_known = set()
    for k_list in INTEREST_RELATED_KEYWORDS.values():
        all_known.update(kw.lower() for kw in k_list)
    all_known.update(INTEREST_RELATED_KEYWORDS.keys())

    sorted_known = sorted(all_known, key=len, reverse=True)
    remaining = phrase_lower
    for kw in sorted_known:
        if kw in remaining and len(kw) >= 2:
            keywords.append(kw)
            remaining = remaining.replace(kw, " ", 1)

    # 2. 对剩余部分：英文按空格/标点拆分
    remaining_parts = re.split(r'[\s,，、。；;]+', remaining)
    for part in remaining_parts:
        part = part.strip()
        if not part:
            continue
        # 英文单词直接保留
        english_words = re.findall(r'[a-zA-Z0-9+#.]+', part)
        for ew in english_words:
            if len(ew) >= 2 and ew not in STOP_WORDS:
                keywords.append(ew.lower())

    # 3. 中文部分：滑动窗口取2-3字片段
    chinese_text = re.sub(r'[a-zA-Z0-9+#.\s]+', '', phrase_lower)
    windows = []
    for win_len in [3, 2]:
        for i in range(len(chinese_text) - win_len + 1):
            seg = chinese_text[i:i+win_len]
            if seg not in STOP_WORDS and seg not in keywords:
                windows.append(seg)

    # 优先保留更长的片段，去重
    seen = set()
    for seg in windows:
        if seg not in seen and len(keywords) < 6:
            keywords.append(seg)
            seen.add(seg)

    # 4. 去重 + 最多4个
    unique = []
    seen = set()
    for kw in keywords:
        if kw not in seen:
            unique.append(kw)
            seen.add(kw)
        if len(unique) >= 4:
            break

    # 如果拆分后为空，保留原始词
    if not unique:
        unique = [phrase_lower]

    print(f"[FinalFallback] Split '{phrase}' → {unique}")
    return unique


def search_bilibili_final_fallback(
    interest: str,
    max_items: int = 10
) -> Optional[List[Dict[str, Any]]]:
    """
    最终保底搜索：智能拆词 → 多路搜索 → LLM 精选

    当所有现有搜索层都返回 < 3 条结果时触发。

    Args:
        interest: 原始兴趣关键词
        max_items: 最大返回条目数

    Returns:
        LLM 精选后的搜索结果列表
    """
    print(f"[FinalFallback] Starting for '{interest}'...")

    # 1. 拆分关键词
    keywords = split_interest_keywords(interest)

    # 2. 每个关键词 → B站搜索 API（不过滤）
    all_items = []
    seen_titles = set()

    for kw in keywords:
        # 跳过太短的词
        if len(kw) < 2:
            continue

        try:
            raw_results = search_bilibili_search_api(kw)
            if not raw_results:
                # search API 可能内部做了过滤，直接用原始搜索（不带filter）
                # 通过直接调用 B站 API
                from urllib.parse import quote
                session = requests.Session()
                session.get("https://www.bilibili.com", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                resp = session.get(
                    "https://api.bilibili.com/x/web-interface/search/type",
                    params={"keyword": kw, "search_type": "video", "order": "click", "page": 1},
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                        "Referer": f"https://search.bilibili.com/all?keyword={quote(kw, safe='')}",
                    },
                    timeout=15,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == 0:
                        items = data.get("data", {}).get("result", [])
                        raw_results = []
                        for idx, item in enumerate(items[:10]):
                            title = item.get("title", "").replace('<em class="keyword">', "").replace("</em>", "")
                            bvid = item.get("bvid", "")
                            if title and bvid:
                                raw_results.append({
                                    "title": title,
                                    "hot": format_hot_str(item.get("play", 0)),
                                    "url": f"https://www.bilibili.com/video/{bvid}",
                                    "desc": item.get("description", ""),
                                    "author": item.get("author", ""),
                                    "source_keyword": kw,
                                })
            if raw_results:
                for item in raw_results[:10]:
                    title_key = item["title"].lower().strip()
                    if title_key not in seen_titles:
                        seen_titles.add(title_key)
                        all_items.append(item)
                print(f"[FinalFallback]   '{kw}' → {len(raw_results)} raw, {len(all_items)} total unique")
        except Exception as e:
            print(f"[FinalFallback]   '{kw}' search failed: {e}")
            continue

    if not all_items:
        print(f"[FinalFallback] No results from any split keyword")
        return None

    # 3. LLM 精选
    # 取前20条发给LLM（减少token消耗，降低超时风险）
    items_text = ""
    for idx, item in enumerate(all_items[:20]):
        items_text += f"[{idx+1}] {item['title']}\n"
        if item.get('desc') and len(item.get('desc', '')) > 10:
            items_text += f"    描述: {item['desc'][:80]}\n"
        items_text += f"    播放: {item.get('hot', '?')}\n\n"

    try:
        resp = requests.post(
            DEEPSEEK_API_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": (
                        "你是内容筛选助手。从搜索结果中选出与用户搜索意图最相关的视频。"
                        "只选真正相关的，不相关的坚决排除。"
                        "返回 JSON 数组 [{index, title, reason}]，按相关度降序，最多10条。"
                        "index 对应搜索结果中的序号。没有相关的返回 []。"
                    )},
                    {"role": "user", "content": (
                        f"用户搜索: {interest}\n\n"
                        f"请选出与「{interest}」最相关的视频:\n\n{items_text}"
                    )},
                ],
                "temperature": 0.3, "max_tokens": 1500,
            },
            timeout=60,
        )
        resp.raise_for_status()
        content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "[]")
    except Exception as e:
        print(f"[FinalFallback] LLM call failed: {e}")
        # LLM 失败 → 直接返回去重后的原始结果
        result = []
        for item in all_items[:max_items]:
            result.append({
                "title": item["title"],
                "hot": item.get("hot", ""),
                "url": item.get("url", ""),
                "desc": item.get("desc", ""),
                "source_platform": "bilibili",
                "source_name": "哔哩哔哩",
                "match_type": "final_fallback",
                "summary": f"搜索: {item.get('source_keyword', '')}",
            })
        return result if result else None

    # Parse LLM response
    content = content.strip()
    for prefix in ["```json", "```"]:
        if content.startswith(prefix):
            content = content[len(prefix):]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    try:
        matched = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r'\[.*\]', content, re.DOTALL)
        matched = json.loads(match.group()) if match else []

    # 回填完整信息
    result = []
    for m in matched[:max_items]:
        idx = int(m.get("index", 0)) - 1
        if 0 <= idx < len(all_items):
            item = all_items[idx]
            result.append({
                "title": item["title"],
                "hot": item.get("hot", ""),
                "url": item.get("url", ""),
                "desc": item.get("desc", ""),
                "author": item.get("author", ""),
                "rank": len(result) + 1,
                "source_platform": "bilibili",
                "source_name": "哔哩哔哩",
                "match_type": "final_fallback",
                "summary": m.get("reason", ""),
                "relevance": m.get("relevance", 8),
            })

    print(f"[FinalFallback] LLM curated: {len(result)} items for '{interest}'")
    return result if result else None


# ============================================
# 任意网页搜索（网页抓取 + 网站自身搜索 + LLM 提取）
# ============================================

def search_unknown_with_fallback(
    url: str,
    interests: List[str],
    max_items: int = 20
) -> List[Dict[str, Any]]:
    """
    任意网页搜索：网页抓取 → LLM提取 → 拆词+站内搜索兜底

    适用于不在 54 平台 API 覆盖范围内的任意网站

    Args:
        url: 网站 URL
        interests: 兴趣方向列表
        max_items: 最大条目数

    Returns:
        热点条目列表
    """
    all_items: List[Dict[str, Any]] = []

    # Layer 1: 网页抓取 + LLM 提取
    for interest in interests:
        print(f"[UnknownSearch] Layer 1: scraping {url} for '{interest}'")
        items = search_unknown_source(url, [interest])
        valid = [i for i in items if i.get("match_type") != "error"]
        all_items.extend(valid)

    if len(all_items) >= 3:
        print(f"[UnknownSearch] 网页抓取获得 {len(all_items)} 条, 返回")
        return all_items[:max_items]

    # Layer 2: 尝试网站自身搜索功能
    print(f"[UnknownSearch] 网页抓取仅 {len(all_items)} 条, 尝试网站搜索...")

    keywords = split_interest_keywords(interests[0])

    search_results = []
    seen_urls = set()

    # 常见的搜索 URL 模式
    search_patterns = [
        "/search?q={keyword}",
        "/search/{keyword}",
        "/search?query={keyword}",
        "/search/?q={keyword}",
        "/s?q={keyword}",
        "/?s={keyword}",
    ]

    for kw in keywords[:4]:
        for pattern in search_patterns:
            search_url = url.rstrip("/") + pattern.replace("{keyword}", kw)
            try:
                html = fetch_webpage(search_url, timeout=10)
                if not html:
                    continue
                text = extract_text_from_html(html, max_chars=4000)
                if not text or len(text) < 200:
                    continue

                # Deepseek 从搜索结果页提取条目
                resp = requests.post(
                    DEEPSEEK_API_URL,
                    headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": DEEPSEEK_MODEL,
                        "messages": [
                            {"role": "system", "content": "从搜索结果页提取条目。返回 JSON [{title, url, summary}]，最多5条。每条的url必须是完整绝对URL。"},
                            {"role": "user", "content": f"搜索: {kw}\n从以下搜索页提取结果:\n\n{text[:3000]}"},
                        ],
                        "temperature": 0.3, "max_tokens": 1500,
                    },
                    timeout=30,
                )
                if resp.status_code == 200:
                    content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "[]")
                    content = content.strip()
                    for prefix in ["```json", "```"]:
                        if content.startswith(prefix):
                            content = content[len(prefix):]
                    if content.endswith("```"):
                        content = content[:-3]
                    try:
                        items = json.loads(content)
                        # 从搜索页 HTML 提取链接并匹配到条目
                        links = extract_links_from_html(html, search_url)
                        items = attach_urls_to_items(items, links)
                        for item in items:
                            item_url = item.get("url", "")
                            if item_url not in seen_urls:
                                seen_urls.add(item_url)
                                search_results.append({
                                    "title": item.get("title", ""),
                                    "url": item_url,
                                    "summary": item.get("summary", ""),
                                    "source_keyword": kw,
                                })
                    except json.JSONDecodeError:
                        pass

                if search_results:
                    print(f"[UnknownSearch] 网站搜索 '{search_url[:60]}' → {len(search_results)} items")
                    break
            except Exception:
                continue
        if len(search_results) >= 15:
            break

    if not search_results:
        return all_items

    # LLM 精选
    items_text = ""
    for idx, r in enumerate(search_results[:20]):
        items_text += f"[{idx+1}] {r['title']}\n"
        if r.get("summary"):
            items_text += f"    {r['summary'][:120]}\n"
        items_text += f"    {r['url']}\n\n"

    try:
        resp = requests.post(
            DEEPSEEK_API_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": (
                        "从搜索结果中选出与用户搜索意图最相关的页面。"
                        "返回 JSON [{index, title, reason}]，最多10条。index对应搜索结果的序号。"
                    )},
                    {"role": "user", "content": (
                        f"用户搜索: {interests[0]}\n目标网站: {url}\n\n"
                        f"请选出最相关的:\n\n{items_text}"
                    )},
                ],
                "temperature": 0.3, "max_tokens": 1500,
            },
            timeout=60,
        )
        resp.raise_for_status()
        content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "[]")
        content = content.strip()
        for prefix in ["```json", "```"]:
            if content.startswith(prefix):
                content = content[len(prefix):]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        try:
            matched = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r'\[.*\]', content, re.DOTALL)
            matched = json.loads(match.group()) if match else []

        result = []
        for m in matched[:max_items]:
            idx = int(m.get("index", 0)) - 1
            if 0 <= idx < len(search_results):
                r = search_results[idx]
                result.append({
                    "title": r["title"],
                    "url": r["url"],
                    "hot": "",
                    "desc": r.get("summary", ""),
                    "rank": len(result) + 1,
                    "source_name": extract_domain(url),
                    "match_type": "web_search",
                    "summary": m.get("reason", ""),
                    "relevance": m.get("relevance", 7),
                })

        all_items.extend(result)
    except Exception as e:
        print(f"[UnknownSearch] LLM failed: {e}")
        for r in search_results[:10]:
            all_items.append({
                "title": r["title"],
                "url": r["url"],
                "hot": "",
                "desc": r.get("summary", ""),
                "rank": len(all_items) + 1,
                "source_name": extract_domain(url),
                "match_type": "web_search",
            })

    print(f"[UnknownSearch] Final: {len(all_items)} items")
    return all_items[:max_items]


# ============================================
# 主搜索接口
# ============================================

async def custom_search(
    urls: List[str],
    interests: List[str],
    max_per_source: int = 20
) -> List[CustomSearchResult]:
    """
    自定义搜索主入口

    Args:
        urls: 用户输入的网站 URL 列表
        interests: 兴趣方向关键词列表
        max_per_source: 每个来源的最大条目数

    Returns:
        搜索结果列表
    """
    results: List[CustomSearchResult] = []

    for url in urls:
        url = url.strip()
        if not url:
            continue

        # 步骤1: 域名匹配
        platform_id = match_platform(url)
        source_name = get_platform_name(platform_id) if platform_id else extract_domain(url)

        if platform_id:
            # 已知平台 → 先用现有 API 查询
            print(f"[CustomSource] {url} → 匹配平台: {source_name} ({platform_id})")

            api_items = await search_known_platform(
                platform_id, interests, max_per_source
            )

            if api_items:
                # API 有结果，直接返回
                results.append(CustomSearchResult(
                    source_url=url,
                    source_name=source_name,
                    matched_platform=platform_id,
                    is_known=True,
                    items=api_items,
                ))

            else:
                # API 无关键词匹配 → 用 LLM 对热榜数据做语义匹配
                print(f"[CustomSource] {source_name} 关键词无匹配，LLM 语义分析...")

                llm_items = await search_known_platform_with_llm(
                    platform_id, interests, max_per_source
                )

                if llm_items:
                    # B站：LLM 结果标题过滤（防"用AI工具制作"误判）
                    # 非B站：信任 LLM + 50条更大数据池（微博/知乎科技内容标题常不显式含关键词）
                    if platform_id == "bilibili":
                        llm_items = filter_items_by_interest(llm_items, interests[0] if interests else "")
                    if llm_items:
                        results.append(CustomSearchResult(
                            source_url=url,
                            source_name=source_name,
                            matched_platform=platform_id,
                            is_known=True,
                            items=llm_items,
                        ))
                    else:
                        # LLM 结果被过滤掉了 → 继续降级
                        print(f"[CustomSource] LLM 语义结果被标题过滤，降级到板块搜索...")
                        all_section_items = []
                        for interest in interests:
                            section_items = await asyncio.to_thread(
                                search_platform_section, platform_id, interest
                            )
                            all_section_items.extend(section_items)

                        # 非B站平台 Layer 3 无结果 → 网站搜索兜底
                        if not all_section_items and platform_id != "bilibili":
                            print(f"[CustomSource] {source_name} 板块搜索无结果, 网站搜索兜底...")
                            fallback = await asyncio.to_thread(
                                search_unknown_with_fallback, url, interests, max_per_source
                            )
                            all_section_items = fallback

                        results.append(CustomSearchResult(
                            source_url=url,
                            source_name=source_name,
                            matched_platform=platform_id,
                            is_known=True,
                            items=all_section_items[:max_per_source],
                            error=None if all_section_items else (
                                f"在 {source_name} 热榜和板块搜索中均未找到与 {interests} 相关的内容"
                            ),
                        ))

                else:
                    # 第三层降级：直接在平台内搜索该板块内容
                    print(f"[CustomSource] {source_name} 热榜无匹配 → 板块搜索...")

                    all_section_items = []
                    for interest in interests:
                        section_items = await asyncio.to_thread(
                            search_platform_section, platform_id, interest
                        )
                        all_section_items.extend(section_items)

                    # 非B站平台 Layer 3 无结果 → 用网站搜索兜底
                    if not all_section_items and platform_id != "bilibili":
                        print(f"[CustomSource] {source_name} 板块搜索无结果, 网站搜索兜底...")
                        fallback = await asyncio.to_thread(
                            search_unknown_with_fallback, url, interests, max_per_source
                        )
                        all_section_items = fallback

                    results.append(CustomSearchResult(
                        source_url=url,
                        source_name=source_name,
                        matched_platform=platform_id,
                        is_known=True,
                        items=all_section_items[:max_per_source],
                        error=None if all_section_items else (
                            f"在 {source_name} 热榜和板块搜索中均未找到与 {interests} 相关的内容"
                        ),
                    ))

        else:
            # 未知平台 → 网页抓取 + LLM提取 → 站内搜索兜底
            print(f"[CustomSource] {url} → 未知平台，启动多级搜索...")

            llm_items = await asyncio.to_thread(
                search_unknown_with_fallback, url, interests, max_per_source
            )

            results.append(CustomSearchResult(
                source_url=url,
                source_name=source_name,
                matched_platform=None,
                is_known=False,
                items=llm_items,
                error=None if llm_items else f"在 {source_name} 中未找到与 {interests} 相关的内容",
            ))

    # 最终保底：B站已知平台 < 3 条 → 智能拆词 + 多路搜索 + LLM 精选
    for r in results:
        if (r.is_known and r.matched_platform == "bilibili"
                and len(r.items) < 3 and interests):
            print(f"[CustomSource] B站 {r.source_name} 仅{len(r.items)}条, 触发最终保底...")
            fallback_items = await asyncio.to_thread(
                search_bilibili_final_fallback, interests[0]
            )
            if fallback_items:
                r.items = fallback_items
                r.error = None

    return results


# ============================================
# 测试代码
# ============================================
if __name__ == "__main__":
    async def test():
        # 测试域名匹配
        test_urls = [
            "https://weibo.com",
            "https://www.zhihu.com",
            "https://news.163.com",
            "https://www.example-news-site.com",
            "36kr.com",
        ]
        print("=== 域名匹配测试 ===")
        for url in test_urls:
            result = match_platform(url)
            print(f"  {url:40s} → {result or '未匹配'}")

        print("\n=== 已知平台搜索测试 ===")
        items = await search_known_platform("weibo", ["科技", "AI"])
        print(f"  微博 + 科技/AI: 找到 {len(items)} 条")
        for item in items[:3]:
            print(f"    - {item['title']}")

    asyncio.run(test())