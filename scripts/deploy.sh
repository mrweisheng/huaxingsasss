#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "=== 部署开始 $(date '+%Y-%m-%d %H:%M:%S') ==="
echo "项目目录: $PROJECT_DIR"

# 安装后端依赖
echo ">>> 安装后端依赖..."
cd "$PROJECT_DIR/backend"
uv sync

# 重启服务（pm2）
echo ">>> 重启服务..."
pm2 restart backend || pm2 start "uv run uvicorn app.main:app --host 0.0.0.0 --port 8000" --name backend
pm2 restart celery-worker || pm2 start "uv run celery -A app.tasks.celery_app worker --loglevel=info" --name celery-worker

echo "=== 部署完成 ==="
