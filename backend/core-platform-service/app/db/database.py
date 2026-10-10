import logging
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Re-exported so the historical `from app.db.database import Base` imports keep
# working. It is the *same* object as app.db.base.Base — there used to be two
# separate declarative bases, which split the model registry: Alembic saw one
# set of tables and `create_all` saw the other, so neither had the full schema.
from app.db.base import Base  # noqa: F401

logger = logging.getLogger(__name__)


def _build_engine():
    """
    Build the database engine.

    A failed connection is fatal by default. The SQLite fallback is opt-in via
    ALLOW_SQLITE_FALLBACK because silently rebinding to a local file means the
    app comes up healthy and accepts writes that go somewhere nobody is
    watching — a transient Postgres blip was enough to trigger it.
    """
    db_url = settings.DATABASE_URL
    connect_args = {"connect_timeout": 3} if "postgresql" in db_url else {}

    try:
        engine = create_engine(
            db_url,
            echo=False,
            connect_args=connect_args,
            pool_pre_ping=True,
        )

        with engine.connect() as conn:
            if "postgresql" in db_url:
                try:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                    conn.commit()
                    logger.info("pgvector extension verified/enabled.")
                except Exception as exc:
                    # Requires superuser on some hosts; RAG features degrade
                    # but the rest of the app is fine.
                    logger.warning("Could not enable pgvector extension: %s", exc)

        return engine

    except Exception as err:
        if not settings.ALLOW_SQLITE_FALLBACK:
            logger.error("Database connection failed: %s", err)
            raise RuntimeError(
                f"Could not connect to the database at the configured "
                f"DATABASE_URL: {err}. Set ALLOW_SQLITE_FALLBACK=true to fall "
                f"back to a local SQLite file for development only."
            ) from err

        logger.warning(
            "PostgreSQL connection failed (%s). ALLOW_SQLITE_FALLBACK is on, "
            "falling back to sqlite:///./fallback.db — data written from here "
            "will NOT reach PostgreSQL.",
            err,
        )
        return create_engine(
            "sqlite:///./fallback.db",
            echo=False,
            connect_args={"check_same_thread": False},
        )


engine = _build_engine()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
