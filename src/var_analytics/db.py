from functools import lru_cache

from sqlalchemy import Engine, create_engine

from var_analytics.config import settings


@lru_cache(maxsize=4)
def engine_for(url: str) -> Engine:
    if not url:
        raise ValueError("Database connection is not configured. Follow the setup instructions.")
    return create_engine(
        url,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"options": "-csearch_path=var,public", "connect_timeout": 10},
    )


def reader_engine() -> Engine:
    return engine_for(settings().reader_database_url)


def admin_engine() -> Engine:
    return engine_for(settings().admin_database_url)
