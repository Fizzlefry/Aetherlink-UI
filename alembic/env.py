import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# ---------------------------------------------------------------------
# Alembic Config + Logging
# ---------------------------------------------------------------------
config = context.config

# Read DATABASE_URL from env; fall back to local dev default
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://aether:aetherpass@localhost:5432/aetherlink",
)

# Inject URL into alembic config so CLI commands pick it up
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------
# Target metadata (IMPORT YOUR MODELS' Base HERE)
# Adjust this import to your project structure.
# Example: from pods.customer_ops.models import Base
#          target_metadata = Base.metadata
# ---------------------------------------------------------------------
try:
    from pods.customer_ops.models import Base  # <-- update if needed

    target_metadata = Base.metadata
except Exception as e:
    # Fallback: no autogenerate if import fails
    target_metadata = None
    print(f"[alembic] WARN: could not import Base for autogenerate: {e}")


# Optional: filter objects (e.g., skip alembic_version table)
def include_object(object, name, type_, reflected, compare_to):
    if name == "alembic_version" and type_ == "table":
        return False
    return True


# ---------------------------------------------------------------------
# Offline migrations
# ---------------------------------------------------------------------
def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,  # detect column type changes
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------
# Online migrations
# ---------------------------------------------------------------------
def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# ---------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
