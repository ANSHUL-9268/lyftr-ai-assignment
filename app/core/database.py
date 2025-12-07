"""
Database connection and session management.
"""
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session, declarative_base

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Create base class for models
Base = declarative_base()

# Engine and session factory (initialized lazily)
_engine = None
_SessionLocal = None


def get_engine():
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        
        # SQLite specific settings
        connect_args = {}
        if settings.database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            
            # Extract file path from sqlite:///./path/to/db.db and ensure directory exists
            db_path = settings.database_url.replace("sqlite:///", "")
            if db_path.startswith("./"):
                db_path = db_path[2:]
            db_dir = Path(db_path).parent
            if db_dir and not db_dir.exists():
                db_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created database directory: {db_dir}")
        
        _engine = create_engine(
            settings.database_url,
            connect_args=connect_args,
            echo=settings.debug,
            pool_pre_ping=True,
        )
        
        # Enable foreign keys for SQLite
        if settings.database_url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
        
        logger.info("Database engine created", extra={"extra_data": {"database_url": settings.database_url}})
    
    return _engine


def get_session_factory():
    """Get or create the session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine()
        )
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager to get database session."""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables."""
    from app.models import message  # noqa: F401 - Import to register models
    
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")


def check_db_connection() -> bool:
    """Check if database is reachable."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False
