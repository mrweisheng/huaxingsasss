FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY pyproject.toml poetry.lock* ./

# 安装Poetry和依赖
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-root --no-interaction --no-ansi

# 复制应用代码
COPY . .

# 创建上传目录
RUN mkdir -p /data/contract-system/{contracts,receipts,screenshots,temp}

# 暴露端口
EXPOSE 8000

# 启动命令（开发环境带--reload，生产环境请移除--reload并使用gunicorn）
# 生产环境推荐: CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
