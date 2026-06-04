import os
import shlex
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY") or "django-insecure-vectorbt-sandbox-dev-key"
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
QFS_ORIGIN = os.getenv("QFS_ORIGIN", "https://qfsplatform.com")


def env_list(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def env_args(name: str, default: str = "") -> list[str]:
    return shlex.split(os.getenv(name, default))


ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    "localhost,127.0.0.1,0.0.0.0,qfsplatform.com,.qfsplatform.com",
)

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
APP_BASE_PATH = os.getenv("APP_BASE_PATH", "")
PUBLIC_BACKEND_BASE_URL = os.getenv("PUBLIC_BACKEND_BASE_URL", "")
FORCE_SCRIPT_NAME = os.getenv("FORCE_SCRIPT_NAME") or None
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
DEFAULT_CHAT_URL = os.getenv("DEFAULT_CHAT_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
DEFAULT_CHAT_MODEL = os.getenv("DEFAULT_CHAT_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
OPENAI_BASE_URL = DEFAULT_CHAT_URL
OPENAI_MODEL = DEFAULT_CHAT_MODEL
MARKET_DATA_CACHE_DIR = BASE_DIR / "cache" / "market_data"
PARSED_REQUEST_CACHE_DIR = BASE_DIR / "cache" / "parsed_requests"
CORS_ALLOWED_ORIGINS = env_list(
    "DJANGO_CORS_ALLOWED_ORIGINS",
    os.getenv(
        "CORS_ALLOWED_ORIGINS",
        f"http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000,{QFS_ORIGIN}",
    ),
)
CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    os.getenv("CSRF_TRUSTED_ORIGINS", QFS_ORIGIN),
)

MCP_ENABLED = os.getenv("MCP_ENABLED", "false").lower() == "true"
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "")
MCP_SERVER_COMMAND = os.getenv("MCP_SERVER_COMMAND", "python")
MCP_SERVER_ARGS = env_args("MCP_SERVER_ARGS")
MCP_CALL_TIMEOUT_SECONDS = int(os.getenv("MCP_CALL_TIMEOUT_SECONDS", "120"))
MCP_DEFAULT_TOOL = os.getenv("MCP_DEFAULT_TOOL", "run_strategy_research")
MCP_ALLOWED_TOOLS = set(
    env_list(
        "MCP_ALLOWED_TOOLS",
        "run_strategy_research,run_markowitz_optimization,list_stock_universe,list_sectors,list_stocks_by_sector,resolve_symbols_for_sector",
    )
)

ANALYTICS_ENABLED = os.getenv("ANALYTICS_ENABLED", "false").lower() == "true"
ANALYTICS_DB_NAME = os.getenv("ANALYTICS_DB_NAME", "analytics")
ANALYTICS_DB_USER = os.getenv("ANALYTICS_DB_USER", "analytics_writer")
ANALYTICS_DB_PASSWORD = os.getenv("ANALYTICS_DB_PASSWORD", "analytics_writer_password")
ANALYTICS_DB_HOST = os.getenv("ANALYTICS_DB_HOST", "localhost")
ANALYTICS_DB_PORT = int(os.getenv("ANALYTICS_DB_PORT", "5432"))
METABASE_URL = os.getenv("METABASE_URL", "http://localhost:3000")
