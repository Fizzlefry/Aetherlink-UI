from os import getenv

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# Build DB URL from environment with sensible defaults matching docker-compose.dev.yml
DB_USER = getenv("POSTGRES_USER", "aether")
DB_PASS = getenv("POSTGRES_PASSWORD", "devpass")
DB_HOST = getenv("DB_HOST", "db")
DB_PORT = getenv("DB_PORT", "5432")
DB_NAME = getenv("POSTGRES_DB", "aetherlink")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)
