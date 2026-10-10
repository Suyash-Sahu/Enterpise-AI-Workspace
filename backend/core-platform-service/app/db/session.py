"""
Session factory.

Re-exports from app.db.database so there is exactly one SessionLocal bound to
one engine. There used to be a second sessionmaker defined here, so different
modules got different session factories depending on which import they reached
for.
"""

from app.db.database import SessionLocal, engine, get_db  # noqa: F401

__all__ = ["SessionLocal", "engine", "get_db"]
