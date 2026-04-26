import os
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool

# Build URL directly from env vars — no app imports needed
def get_url():
    return (
        f"postgresql+psycopg2://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
        f"@{os.environ.get('POSTGRES_HOST','postgres')}:{os.environ.get('POSTGRES_PORT','5432')}"
        f"/{os.environ['POSTGRES_DB']}"
    )

config = context.config
config.set_main_option("sqlalchemy.url", get_url())

if config.config_file_name:
    fileConfig(config.config_file_name)

# Import Base/models for autogenerate — use sys.path trick instead of app import
import sys
sys.path.insert(0, "/app")
from app.database import Base
from app.models import Analysis  # noqa: F401
target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(url=get_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()