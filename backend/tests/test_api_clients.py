from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.db.session as db_session
from app.core.config import get_settings
from app.main import app


def test_create_client_normalizes_country_code(monkeypatch, tmp_path):
    settings = get_settings()
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'clients-test.db').as_posix()}"
    engine = create_async_engine(database_url, echo=False, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    monkeypatch.setattr(settings, "storage_root", tmp_path / "storage")
    monkeypatch.setattr(db_session, "engine", engine)
    monkeypatch.setattr(db_session, "AsyncSessionLocal", session_factory)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/clients",
                json={
                    "name": "Safran",
                    "country": "fr",
                    "activity_description": "Aeronautique",
                    "product_families": [],
                    "product_characteristics": {},
                    "program_names": [],
                    "naming_conventions": {},
                    "classification_history": [],
                },
            )
    finally:
        asyncio.run(engine.dispose())

    assert response.status_code == 201
    payload = response.json()
    assert payload["country"] == "FR"
    assert payload["regulatory_scope"] == ["FR_ML", "EU_DU"]


def test_create_client_rejects_non_iso_country_code(monkeypatch, tmp_path):
    settings = get_settings()
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'clients-invalid-country.db').as_posix()}"
    engine = create_async_engine(database_url, echo=False, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    monkeypatch.setattr(settings, "storage_root", tmp_path / "storage")
    monkeypatch.setattr(db_session, "engine", engine)
    monkeypatch.setattr(db_session, "AsyncSessionLocal", session_factory)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/clients",
                json={
                    "name": "Safran",
                    "country": "France",
                    "activity_description": "Aeronautique",
                    "product_families": [],
                    "product_characteristics": {},
                    "program_names": [],
                    "naming_conventions": {},
                    "classification_history": [],
                },
            )
    finally:
        asyncio.run(engine.dispose())

    assert response.status_code == 422
