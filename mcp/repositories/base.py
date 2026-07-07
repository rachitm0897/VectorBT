from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from app.settings import ResearchSettings, get_settings


@contextmanager
def analytics_connection(settings: ResearchSettings | None = None) -> Iterator:
    settings = settings or get_settings()
    import psycopg

    with psycopg.connect(
        dbname=settings.analytics_db_name,
        user=settings.analytics_db_user,
        password=settings.analytics_db_password,
        host=settings.analytics_db_host,
        port=settings.analytics_db_port,
        connect_timeout=3,
    ) as conn:
        yield conn

