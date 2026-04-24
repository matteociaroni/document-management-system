from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from config import settings

db_url = settings.database_url.replace("postgresql://", "postgresql+psycopg://")
engine = create_engine(
    db_url,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=5,
    pool_recycle=3600,
    pool_pre_ping=True,
    echo=False,
)
SessionLocal = sessionmaker(bind=engine)
