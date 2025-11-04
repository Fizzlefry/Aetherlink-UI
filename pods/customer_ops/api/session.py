from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from .config import get_settings

_settings = get_settings()
DB_URL = _settings.DATABASE_URL or "sqlite:///./local.db"

engine_kwargs = {}
if DB_URL.startswith("sqlite://"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    if DB_URL in ("sqlite://", "sqlite:///:memory:", "sqlite:///:memory"):
        engine_kwargs["poolclass"] = StaticPool

engine = create_engine(DB_URL, future=True, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
