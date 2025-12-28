"""SQLite database setup and session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from pathlib import Path

from .config import settings, DATA_DIR

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# SQLite database path
DB_PATH = DATA_DIR / "biomon.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create engine with SQLite-specific settings
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Needed for SQLite with FastAPI
    echo=False,  # Set to True for SQL debugging
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency for getting database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    # Import all models to ensure they're registered with Base
    from .models import paper, assessment, facility
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print(f"Database initialized at {DB_PATH}")

