#!/bin/bash
# ============================================
# 🔥 每日热榜 - 一键启动脚本
# ============================================
#
# 用法:
#   ./run.sh                    交互式菜单
#   ./run.sh weibo              查询微博热搜
#   ./run.sh --cross-platform   跨平台聚合 TOP10
#   ./run.sh --list             列出所有 54 个平台
#   ./run.sh --monitor "AI"     舆情监控关键词
#   ./run.sh --digest "科技"     热点摘要（按标签）
#   ./run.sh --industry "汽车"   行业热榜
#   ./run.sh --personalized "AI游戏"  个性化订阅
#
# ============================================

set -e

# 进入项目目录
cd "$(dirname "$0")"

# 环境变量
export DAILY_HOT_API_URL="${DAILY_HOT_API_URL:-http://localhost:6688}"
export DAILY_HOT_DATA_DIR="${DAILY_HOT_DATA_DIR:-$(pwd)/data}"
export DAILY_HOT_CACHE_TTL="${DAILY_HOT_CACHE_TTL:-3600}"
export DAILY_HOT_MAX_ITEMS="${DAILY_HOT_MAX_ITEMS:-20}"
export DAILY_HOT_TIMEOUT="${DAILY_HOT_TIMEOUT:-10}"

# 检测 Python 版本（优先使用 3.10）
if command -v python3.10 &> /dev/null; then
    PYTHON=python3.10
elif command -v python3 &> /dev/null; then
    PYTHON=python3
else
    echo "❌ 未找到 Python3，请安装 Python 3.10+"
    exit 1
fi

# 检查依赖
echo "📦 检查依赖..."
$PYTHON -c "import aiohttp, requests" 2>/dev/null || {
    echo "⏳ 安装依赖..."
    $PYTHON -m pip install -r requirements.txt --quiet
    echo "✅ 依赖安装完成"
}
echo "✅ 依赖已就绪"
echo ""

# 检查后端服务（用 /weibo 端点检测，根路径无静态页会返回404）
echo "🔍 检查后端服务 ${DAILY_HOT_API_URL}..."
$PYTHON -c "
import aiohttp, asyncio
async def check():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get('${DAILY_HOT_API_URL}/weibo', timeout=aiohttp.ClientTimeout(total=3)) as r:
                return r.status == 200
    except:
        return False
ok = asyncio.run(check())
print('✅ 后端服务连接成功' if ok else '⚠️  后端服务未响应，请确认 DailyHotApi 已启动')
" 2>/dev/null || echo "⚠️  无法检查后端服务状态"

echo ""
echo "=============================="

# 解析参数
if [ $# -eq 0 ]; then
    # 无参数 → 交互式主菜单
    echo "🔥 启动每日热榜..."
    $PYTHON -c "
import os, sys, asyncio
os.environ['DAILY_HOT_DATA_DIR'] = '${DAILY_HOT_DATA_DIR}'
sys.path.insert(0, '.')
from daily_hot_news import create_skill
async def main():
    skill = await create_skill()
    result = await skill.handle_request('帮助')
    print(result['message'])
    # 同时展示平台列表
    print()
    from formatter import formatter
    print(formatter.format_all_sources())
asyncio.run(main())
"

elif [ "$1" = "--list" ]; then
    $PYTHON -c "
import os, sys
os.environ['DAILY_HOT_DATA_DIR'] = '${DAILY_HOT_DATA_DIR}'
sys.path.insert(0, '.')
from formatter import formatter
print(formatter.format_all_sources())
"

elif [ "$1" = "--cross-platform" ]; then
    $PYTHON -c "
import os, sys, asyncio
os.environ['DAILY_HOT_DATA_DIR'] = '${DAILY_HOT_DATA_DIR}'
sys.path.insert(0, '.')
from cross_platform import create_cross_platform
async def main():
    cp = await create_cross_platform()
    result = await cp.process_user_request()
    print(result['message'])
asyncio.run(main())
"

elif [ "$1" = "--monitor" ]; then
    shift
    KEYWORD="${*:-AI}"
    $PYTHON -c "
import os, sys, asyncio
os.environ['DAILY_HOT_DATA_DIR'] = '${DAILY_HOT_DATA_DIR}'
sys.path.insert(0, '.')
from sentiment_monitor import create_sentiment_monitor
async def main():
    sm = await create_sentiment_monitor()
    result = await sm.process_user_request('${KEYWORD}')
    print(result['message'])
asyncio.run(main())
"

elif [ "$1" = "--digest" ]; then
    shift
    TAG="${*:-科技}"
    $PYTHON -c "
import os, sys, asyncio
os.environ['DAILY_HOT_DATA_DIR'] = '${DAILY_HOT_DATA_DIR}'
sys.path.insert(0, '.')
from news_digest import create_digest
async def main():
    nd = await create_digest()
    result = await nd.process_user_request('${TAG}')
    print(result['message'])
asyncio.run(main())
"

elif [ "$1" = "--industry" ]; then
    shift
    IND="${*:-汽车}"
    $PYTHON -c "
import os, sys, asyncio
os.environ['DAILY_HOT_DATA_DIR'] = '${DAILY_HOT_DATA_DIR}'
sys.path.insert(0, '.')
from industry_hot import create_industry_hot
async def main():
    ih = await create_industry_hot()
    result = await ih.process_user_request('${IND}')
    print(result['message'])
asyncio.run(main())
"

elif [ "$1" = "--personalized" ]; then
    shift
    PREF="${*:-AI}"
    $PYTHON -c "
import os, sys, asyncio
os.environ['DAILY_HOT_DATA_DIR'] = '${DAILY_HOT_DATA_DIR}'
sys.path.insert(0, '.')
from personalized import create_personalized
async def main():
    ps = await create_personalized()
    result = await ps.process_user_request('${PREF}')
    print(result['message'])
asyncio.run(main())
"

elif [ "$1" = "--history" ]; then
    shift
    SOURCE="${1:-weibo}"
    $PYTHON storage.py
    echo ""
    echo "📂 查看 $SOURCE 历史:"
    $PYTHON -c "
import os, sys
os.environ['DAILY_HOT_DATA_DIR'] = '${DAILY_HOT_DATA_DIR}'
sys.path.insert(0, '.')
from storage import storage
from formatter import formatter

source_id = '${SOURCE}'
hot_list = storage.load_hot_list(source_id)
if hot_list:
    items = hot_list[:10]
    print(f'\n🔥 {source_id} 最近保存的热榜:')
    for i, item in enumerate(items, 1):
        title = item.get('title', '')
        hot = item.get('hot', '')
        print(f'  {i}. {title}  {hot}')
else:
    print(f'  暂无 ${SOURCE} 的历史数据')
"

else
    # 直接查询指定平台
    PLATFORM="${1:-weibo}"
    echo "🔥 获取 $PLATFORM 热榜..."
    $PYTHON -c "
import os, sys, asyncio
os.environ['DAILY_HOT_DATA_DIR'] = '${DAILY_HOT_DATA_DIR}'
sys.path.insert(0, '.')
from api_client import api_client
from storage import storage
from formatter import formatter

async def main():
    data = await api_client.fetch_hot_list('${PLATFORM}')
    if data:
        print(formatter.format_hot_list(data))
        # 检查历史
        dates = storage.get_saved_dates('${PLATFORM}')
        if dates:
            print(f'\n📂 已保存 {len(dates)} 天历史记录: {dates[0]} ~ {dates[-1]}')
    else:
        print('❌ 未找到平台: ${PLATFORM}')
        print('\n💡 使用 --list 查看所有支持的热榜源')

asyncio.run(main())
"
fi