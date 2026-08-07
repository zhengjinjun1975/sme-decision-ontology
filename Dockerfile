# sme-decision-ontology API 镜像
# 构建: docker build -t sme-decision-api .
# 运行: docker compose up -d   (见 docker-compose.yml)
FROM python:3.11-slim

WORKDIR /app
COPY codes/ ./codes/
COPY data/ ./data/
COPY config/ ./config/
COPY web/ ./web/
WORKDIR /app/codes

# 运行时依赖(API + 前端托管; 决策规则引擎是纯标准库零依赖)
RUN pip install --no-cache-dir fastapi uvicorn[standard]

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=3)" || exit 1

EXPOSE 8000
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
