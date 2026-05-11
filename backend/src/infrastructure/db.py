"""SQLAlchemy engine, session factory, and Base.

Reads `DATABASE_URL` from the environment. Falls back to a local MySQL URL
matching the docker-compose defaults so tests/dev can run without manual
configuration when the compose stack is up.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


_DEFAULT_URL = "mysql+pymysql://roko:rokopass@127.0.0.1:3306/roko?charset=utf8mb4"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", _DEFAULT_URL)


_engine = None
_SessionLocal = None


def engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            database_url(),
            pool_pre_ping=True,
            pool_recycle=3600,
            future=True,
        )
    return _engine


def SessionLocal():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=engine(), autoflush=False, expire_on_commit=False, future=True)
    return _SessionLocal()


class Base(DeclarativeBase):
    pass
