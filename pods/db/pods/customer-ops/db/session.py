from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# IMPORTANT:
# These credentials MUST match what you set in docker-compose.dev.yml
# under the "db" service (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB).
#
# The hostname "db" here is the docker service name, NOT localhost.
DATABASE_URL = "postgresql://user:password@db:5432/aetherlink"

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)
