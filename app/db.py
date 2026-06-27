from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def create_app_engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True)


engine = create_app_engine()
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def get_db():
    with SessionLocal() as session:
        yield session
