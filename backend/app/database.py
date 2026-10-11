from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from . import config

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Default: SQLite file under backend/data. Set DATABASE_URL in .env for MySQL/PostgreSQL, e.g.
#   mysql+pymysql://user:pass@localhost/shiptrack
DATABASE_URL = config.settings.database_url or "sqlite:///" + (DATA_DIR / "shiptrack.db").as_posix()

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
