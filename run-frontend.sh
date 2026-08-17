#!/bin/bash
# ============================================
# 🔥 每日热榜 - 前端启动脚本
# ============================================
# 启动后浏览器访问 http://localhost:5173
# ============================================

set -e

cd "$(dirname "$0")/frontend"

echo "📦 检查依赖..."
if [ ! -d "node_modules" ]; then
    echo "⏳ 安装依赖..."
    npm install
    echo "✅ 依赖安装完成"
fi

echo ""
echo "🚀 启动开发服务器..."
echo "   👉 浏览器打开: http://localhost:5173"
echo ""

npx vite --host 0.0.0.0 --port 5173
