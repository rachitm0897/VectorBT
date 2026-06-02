import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR.parent / ".env")
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY") or "django-insecure-vectorbt-sandbox-dev-key"
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.market_data",
    "apps.strategies",
    "apps.backtesting",
    "apps.agent",
    "apps.analytics",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.cors.SimpleCorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "UNAUTHENTICATED_USER": None,
}

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY") or ""
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or ""
OPENAI_MODEL = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
MARKET_DATA_CACHE_DIR = BASE_DIR / "cache" / "market_data"
PARSED_REQUEST_CACHE_DIR = BASE_DIR / "cache" / "parsed_requests"
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]
OPENAI_API_BASE_URL = os.getenv("OPENAI_API_BASE_URL") or "https://api.openai.com/v1"
METABASE_URL = os.getenv("METABASE_URL") or "http://localhost:3000"
MCP_ENABLED = os.getenv("MCP_ENABLED", "true").lower() == "true"
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT") or "stdio"
MCP_SERVER_COMMAND = os.getenv("MCP_SERVER_COMMAND") or "python"
MCP_SERVER_ARGS = os.getenv("MCP_SERVER_ARGS") or "standalone_mcp_server/server.py"
MCP_CALL_TIMEOUT_SECONDS = float(os.getenv("MCP_CALL_TIMEOUT_SECONDS") or "120")
MCP_DEFAULT_TOOL = os.getenv("MCP_DEFAULT_TOOL") or "run_strategy_research"
