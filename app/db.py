from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def create_app_engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker(database_url: str):
    return sessionmaker(bind=create_engine(database_url, pool_pre_ping=True), class_=Session, expire_on_commit=False)


engine = create_app_engine()
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def get_db():
    current_sessionmaker = get_sessionmaker(get_settings().database_url)
    with current_sessionmaker() as session:
        yield session
