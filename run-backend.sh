#!/bin/bash
# ============================================
# 🔥 每日热榜 - 后端启动脚本
# ============================================
# 启动自定义信息源搜索后端 (port 5001)
# ============================================

set -e

cd "$(dirname "$0")"
export DAILY_HOT_DATA_DIR="${DAILY_HOT_DATA_DIR:-$(pwd)/data}"
export DAILY_HOT_API_URL="${DAILY_HOT_API_URL:-http://localhost:6688}"
export ENHANCER_PORT="${ENHANCER_PORT:-5001}"

# 检测 Python 版本
if command -v python3.10 &> /dev/null; then
    PYTHON=python3.10
elif command -v python3 &> /dev/null; then
    PYTHON=python3
else
    echo "❌ 未找到 Python3"
    exit 1
fi

echo "📦 检查后端依赖..."
$PYTHON -c "import fastapi, uvicorn, bs4" 2>/dev/null || {
    echo "⏳ 安装依赖..."
    $PYTHON -m pip install -r requirements-server.txt -q
    echo "✅ 依赖安装完成"
}

echo ""
echo "🚀 启动增强后端服务..."
echo "   📡 API: http://localhost:${ENHANCER_PORT}"
echo "   📋 文档: http://localhost:${ENHANCER_PORT}/docs"
echo ""

$PYTHON custom_source/server.py
