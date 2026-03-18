FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码
COPY src/ ./src/
COPY tests/ ./tests/

# 暴露端口
EXPOSE 50000-51000/tcp 50000-51000/udp 9001/tcp

# 运行服务
CMD ["python", "-m", "src.main"]
