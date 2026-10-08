from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.core.config import get_settings
from app.db.base import Base


settings = get_settings()

engine = create_async_engine(settings.database_url, echo=settings.debug, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_compat_schema)


def _ensure_compat_schema(sync_conn) -> None:
    inspector = inspect(sync_conn)
    document_columns = {column["name"] for column in inspector.get_columns("documents")}
    if "client_profile_id" not in document_columns:
        column_type = "UUID" if sync_conn.dialect.name == "postgresql" else "CHAR(36)"
        sync_conn.execute(text(f"ALTER TABLE documents ADD COLUMN client_profile_id {column_type}"))
    if "relative_path" not in document_columns:
        sync_conn.execute(text("ALTER TABLE documents ADD COLUMN relative_path VARCHAR(1024)"))
    if "artifact_status" not in document_columns:
        sync_conn.execute(text("ALTER TABLE documents ADD COLUMN artifact_status VARCHAR(32) NOT NULL DEFAULT 'none'"))
    sync_conn.execute(
        text(
            """
            UPDATE documents
            SET artifact_status = LOWER(artifact_status)
            WHERE artifact_status IS NOT NULL
            """
        )
    )
    if "artifact_version" not in document_columns:
        sync_conn.execute(text("ALTER TABLE documents ADD COLUMN artifact_version INTEGER NOT NULL DEFAULT 0"))
    if "original_snapshot_path" not in document_columns:
        sync_conn.execute(text("ALTER TABLE documents ADD COLUMN original_snapshot_path TEXT"))
    if "marked_artifact_path" not in document_columns:
        sync_conn.execute(text("ALTER TABLE documents ADD COLUMN marked_artifact_path TEXT"))
    if "artifact_error" not in document_columns:
        sync_conn.execute(text("ALTER TABLE documents ADD COLUMN artifact_error TEXT"))
    if "marking_duration_ms" not in document_columns:
        sync_conn.execute(text("ALTER TABLE documents ADD COLUMN marking_duration_ms INTEGER"))

    classification_result_columns = {column["name"] for column in inspector.get_columns("classification_results")}
    if "pipeline_version" not in classification_result_columns:
        sync_conn.execute(text("ALTER TABLE classification_results ADD COLUMN pipeline_version VARCHAR(10) NOT NULL DEFAULT 'v1'"))
    if "lifecycle_phase" not in classification_result_columns:
        sync_conn.execute(text("ALTER TABLE classification_results ADD COLUMN lifecycle_phase VARCHAR(100)"))
    if "tangible_description" not in classification_result_columns:
        sync_conn.execute(text("ALTER TABLE classification_results ADD COLUMN tangible_description TEXT"))
    if "tangible_category" not in classification_result_columns:
        sync_conn.execute(text("ALTER TABLE classification_results ADD COLUMN tangible_category VARCHAR(50)"))

    if sync_conn.dialect.name != "postgresql":
        return

    foreign_keys = {foreign_key["name"] for foreign_key in inspector.get_foreign_keys("documents")}
    constraint_name = "fk_documents_client_profile_id_client_profiles"
    if constraint_name not in foreign_keys:
        sync_conn.execute(
            text(
                """
                ALTER TABLE documents
                ADD CONSTRAINT fk_documents_client_profile_id_client_profiles
                FOREIGN KEY (client_profile_id) REFERENCES client_profiles (id)
                """
            )
        )
