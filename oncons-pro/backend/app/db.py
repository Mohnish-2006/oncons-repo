from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

def _database_url():
    url=settings.DATABASE_URL
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url

engine = create_engine(_database_url(), connect_args={"check_same_thread": False} if _database_url().startswith("sqlite") else {}, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()
