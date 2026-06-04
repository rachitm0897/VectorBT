from dataclasses import dataclass
from typing import Any

from django.conf import settings


FINNHUB_API_KEY_HEADER = "X-Finnhub-API-Key"
CHAT_API_KEY_HEADER = "X-Chat-API-Key"
CHAT_URL_HEADER = "X-Chat-URL"
CHAT_MODEL_HEADER = "X-Chat-Model"
OPENAI_API_KEY_HEADER = "X-OpenAI-API-Key"
OPENAI_BASE_URL_HEADER = "X-OpenAI-Base-URL"
OPENAI_MODEL_HEADER = "X-OpenAI-Model"


@dataclass(frozen=True)
class RequestApiKeys:
    chat_url: str = ""
    chat_api_key: str = ""
    model: str = ""
    finnhub_api_key: str = ""

    @property
    def openai_api_key(self) -> str:
        return self.chat_api_key

    @property
    def openai_base_url(self) -> str:
        return self.chat_url

    @property
    def openai_model(self) -> str:
        return self.model


def api_keys_from_request(request: Any) -> RequestApiKeys:
    data = getattr(request, "data", {}) or {}
    return RequestApiKeys(
        chat_url=_clean(request.headers.get(CHAT_URL_HEADER))
        or _clean(request.headers.get(OPENAI_BASE_URL_HEADER))
        or _first_clean(data, "chat_url", "openai_base_url", "chatUrl", "openaiBaseUrl")
        or _clean(settings.DEFAULT_CHAT_URL),
        chat_api_key=_clean(request.headers.get(CHAT_API_KEY_HEADER))
        or _clean(request.headers.get(OPENAI_API_KEY_HEADER))
        or _first_clean(data, "chat_api_key", "openai_api_key", "chatApiKey", "openaiKey", "apiKey"),
        model=_clean(request.headers.get(CHAT_MODEL_HEADER))
        or _clean(request.headers.get(OPENAI_MODEL_HEADER))
        or _first_clean(data, "model", "openai_model", "chatModel", "openaiModel")
        or _clean(settings.DEFAULT_CHAT_MODEL),
        finnhub_api_key=_clean(request.headers.get(FINNHUB_API_KEY_HEADER))
        or _first_clean(data, "finnhub_api_key", "finnhubKey", "finnhubApiKey"),
    )


def resolve_chat_api_key(value: str | None = None) -> str:
    return _clean(value)


def resolve_chat_url(value: str | None = None) -> str:
    return _clean(value) or _clean(settings.DEFAULT_CHAT_URL)


def resolve_chat_model(value: str | None = None) -> str:
    return _clean(value) or _clean(settings.DEFAULT_CHAT_MODEL)


def resolve_openai_api_key(value: str | None = None) -> str:
    return resolve_chat_api_key(value)


def resolve_finnhub_api_key(value: str | None = None) -> str:
    return _clean(value) or _clean(settings.FINNHUB_API_KEY)


def _clean(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _first_clean(data: Any, *names: str) -> str:
    if not isinstance(data, dict):
        return ""
    for name in names:
        value = _clean(data.get(name))
        if value:
            return value
    return ""
