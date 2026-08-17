#!/bin/bash
# ============================================
# 🔥 每日热榜 - 一键启动全部服务
# ============================================
# 启动: hot-api (Node :6688) + 后端 (Python :5001) + 前端 (React :5173)
# ============================================

cd "$(dirname "$0")"

PID_DIR=".pids"
mkdir -p "$PID_DIR"

check_port() {
    lsof -ti ":$1" >/dev/null 2>&1 && return 0 || return 1
}

start_service() {
    local name="$1" port="$2" pidfile="$3"
    shift 3

    if check_port "$port"; then
        echo "  ⏭️  $name 已在运行 (端口 $port)"
        return 1
    fi

    echo "  🚀 启动 $name (端口 $port)..."
    nohup "$@" > ".logs/$name.log" 2>&1 &
    echo $! > "$PID_DIR/$pidfile"
    return 0
}

mkdir -p .logs

echo "========================================"
echo "🔥 每日热榜 - 一键启动"
echo "========================================"

# 1. hot-api (Node.js 热榜API)
echo "[1/3] Node 热榜 API"
if [ ! -d "hot-api/node_modules" ]; then
    echo "  ⏳ 首次运行，安装 hot-api 依赖..."
    (cd hot-api && npm install) || {
        echo "  ❌ npm install 失败，可尝试镜像源: npm config set registry https://registry.npmmirror.com"
        exit 1
    }
fi
start_service "hot-api" 6688 "hot-api.pid" \
    bash -c "cd hot-api && NODE_ENV=development npx tsx watch --no-cache src/index.ts"

# 2. Python 后端
echo "[2/3] Python 后端"
if command -v python3.10 >/dev/null 2>&1; then
    PYTHON=python3.10
else
    PYTHON=python3
fi
export DAILY_HOT_DATA_DIR="$(pwd)/data"
export DAILY_HOT_API_URL="http://localhost:6688"
start_service "backend" 5001 "backend.pid" \
    "$PYTHON" custom_source/server.py

# 3. React 前端
echo "[3/3] React 前端"
if [ ! -d "frontend/node_modules" ]; then
    echo "  ⏳ 首次运行，安装前端依赖..."
    (cd frontend && npm install) || exit 1
fi
start_service "frontend" 5173 "frontend.pid" \
    bash -c "cd frontend && npx vite --host 0.0.0.0 --port 5173"

echo ""
echo "========================================"
sleep 3

# 状态检查
echo "📊 服务状态:"
for name in "热榜API:6688" "后端API:5001" "前端:5173"; do
    svc="${name%%:*}"
    port="${name##*:}"
    if check_port "$port"; then
        echo "  ✅ $svc → http://localhost:$port"
    else
        echo "  ❌ $svc 未启动"
    fi
done

echo ""
echo "🌐 浏览器打开: http://localhost:5173"
echo "🛑 停止全部:   ./stop-all.sh"
echo "========================================"