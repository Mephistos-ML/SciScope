"""Alembic environment configuration."""

from __future__ import annotations

from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.database.base import Base
from app.database.records import (
    ExploreSearchEventRecordModel,
    OAuthAccountRecordModel,
    RepositoryCheckpointRecordModel,
    RepositoryRecordModel,
    SeenSignalRecordModel,
    SubscriptionRecordModel,
    UserRecordModel,
    UserSessionRecordModel,
)

REGISTERED_MODELS = (
    UserRecordModel,
    OAuthAccountRecordModel,
    UserSessionRecordModel,
    SeenSignalRecordModel,
    RepositoryRecordModel,
    RepositoryCheckpointRecordModel,
    SubscriptionRecordModel,
    ExploreSearchEventRecordModel,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_database_url() -> str:
    return os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""

    context.configure(
        url=_get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode."""

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _get_database_url()
    connectable = engine_from_config(
        configuration,
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
