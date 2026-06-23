from sqlmodel import SQLModel, create_engine, Session
from pathlib import Path

DB_FILE = Path(__file__).parent.parent / "data" / "bio_maintain.db"
DB_FILE.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{DB_FILE.as_posix()}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    return Session(engine)
