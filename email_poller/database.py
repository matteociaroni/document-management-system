from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from config import settings

db_url = settings.database_url.replace("postgresql://", "postgresql+psycopg://")
engine = create_engine(
    db_url,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=10,
    pool_recycle=3600,
    pool_pre_ping=True,
    echo=False,
)
SessionLocal = sessionmaker(bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def close_db() -> None:
    engine.dispose()
