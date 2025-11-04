import os, asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

config = context.config

DATABASE_URL_SYNC = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://aether:aetherpass@localhost:5432/aetherlink",
)
# Convert sync URL to async if needed (simple heuristic)
DATABASE_URL = DATABASE_URL_SYNC.replace("postgresql+psycopg2", "postgresql+asyncpg")

config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import your Base
try:
    from pods.customer_ops.models import Base  # adjust this path if needed
    target_metadata = Base.metadata
except Exception as e:
    target_metadata = None
    print(f"[alembic] WARN: could not import Base for autogenerate: {e}")

def include_object(object, name, type_, reflected, compare_to):
    if name == "alembic_version" and type_ == "table":
        return False
    return True

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        pool_pre_ping=True,
        future=True,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(lambda conn: context.configure(
            connection=conn,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,
            compare_server_default=True,
        ))
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
