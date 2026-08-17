#!/bin/bash
# ============================================
# 🔥 每日热榜 - 一键停止全部服务
# ============================================

set -e
cd "$(dirname "$0")"

PID_DIR=".pids"

echo "========================================"
echo "🛑 停止每日热榜全部服务"
echo "========================================"

# 1. 按 PID 文件停止
for pidfile in hot-api.pid backend.pid frontend.pid; do
    if [ -f "$PID_DIR/$pidfile" ]; then
        pid=$(cat "$PID_DIR/$pidfile")
        name="${pidfile%.pid}"
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null
            echo "  ✅ 停止 $name (PID $pid)"
        fi
        rm -f "$PID_DIR/$pidfile"
    fi
done

# 2. 兜底：按端口清理残留进程（含 tsx watch 的子进程）
for port in 6688 5001 5173; do
    pids=$(lsof -ti ":$port" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        # 也杀掉 tsx watch 的父进程组
        for pid in $pids; do
            kill "$pid" 2>/dev/null || true
        done
        echo "  ✅ 端口 $port 清理完成"
    fi
done

# 清理 esbuild 服务进程（tsx 会残留）
pkill -f "esbuild --service" 2>/dev/null || true

sleep 1
echo ""
echo "📊 剩余服务检查:"
for name in "热榜API:6688" "后端API:5001" "前端:5173"; do
    svc="${name%%:*}"
    port="${name##*:}"
    if lsof -ti ":$port" >/dev/null 2>&1; then
        echo "  ⚠️  $svc 仍在运行 (端口 $port)"
    else
        echo "  ✅ $svc 已停止"
    fi
done
echo "========================================"