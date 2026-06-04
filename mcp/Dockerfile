FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV MCP_SERVER_HOST=0.0.0.0
ENV MCP_SERVER_PORT=8000
ENV MCP_TRANSPORT=streamable_http
ENV MCP_BASE_PATH=/mcp
ENV MCP_PROXY_PREFIX=/insta_backtest_MCP_server
ENV MCP_PUBLIC_BASE_URL=https://qfsplatform.com/insta_backtest_MCP_server
ENV MCP_CACHE_DIR=/app/cache
ENV MCP_US_STOCK_UNIVERSE_PATH=/app/us_stocks_only_universe.json

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY tools ./tools
COPY server.py ./
COPY us_stocks_only_universe.json ./

RUN pip install --no-cache-dir .

EXPOSE 8000 8001

CMD ["python", "server.py"]
