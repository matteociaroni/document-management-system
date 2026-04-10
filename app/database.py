from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings

# Use psycopg driver instead of psycopg2
db_url = settings.database_url.replace("postgresql://", "postgresql+psycopg://")
engine = create_engine(db_url)
SessionLocal = sessionmaker(bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
