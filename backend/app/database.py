from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from app.config import settings

# Use psycopg driver instead of psycopg2
db_url = settings.database_url.replace("postgresql://", "postgresql+psycopg://")
engine = create_engine(
    db_url,
    poolclass=QueuePool,
    pool_size=20,           # Base connections to keep open
    max_overflow=10,        # Additional connections under load
    pool_recycle=3600,      # Recycle connections every hour
    pool_pre_ping=True,     # Verify connection is alive before using
    echo=False              # Set to True for SQL debugging
)
SessionLocal = sessionmaker(bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def close_db():
    """Close all database connections - call on shutdown"""
    engine.dispose()
