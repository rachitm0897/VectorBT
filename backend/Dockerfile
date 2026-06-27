FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_DEBUG=false
ENV DJANGO_ALLOWED_HOSTS=qfsplatform.com,localhost,127.0.0.1
ENV DJANGO_CSRF_TRUSTED_ORIGINS=https://qfsplatform.com
ENV DJANGO_CORS_ALLOWED_ORIGINS=https://qfsplatform.com
ENV PUBLIC_BACKEND_BASE_URL=https://qfsplatform.com/insta_backtester
ENV APP_BASE_PATH=/insta_backtester/
ENV MCP_ENABLED=true
ENV MCP_TRANSPORT=streamable_http
ENV MCP_SERVER_URL=https://qfsplatform.com/insta_backtest_MCP_server/mcp
ENV MCP_CALL_TIMEOUT_SECONDS=120
ENV MCP_DEFAULT_TOOL=run_strategy_research
ENV LANGSMITH_TRACING=false
ENV LANGSMITH_PROJECT=finance-mcp-dev

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000", "--noreload"]
