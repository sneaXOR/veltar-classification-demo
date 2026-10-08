from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Dummy credentials for mocked tests only; no funded provider credentials required.
os.environ["OPENROUTER_API_KEY"] = "test-only-not-a-secret"
os.environ["LLM_API_KEY"] = "test-only-not-a-secret"

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/test-classifier.db")


@pytest.fixture(autouse=True)
def _disable_recovery_jobs(monkeypatch):
    async def _noop_recover_jobs(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr("app.main.recover_incomplete_jobs", _noop_recover_jobs)
