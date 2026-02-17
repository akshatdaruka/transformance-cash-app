from sqlmodel import SQLModel, create_engine, Session
import os

# Get DB URL from environment variable (defined in docker-compose)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/transformance")

engine = create_engine(DATABASE_URL, echo=True)

def init_db():
    """Creates the tables if they don't exist."""
    SQLModel.metadata.create_all(engine)

def get_session():
    """Dependency for FastAPI endpoints."""
    with Session(engine) as session:
        yield session