"""Shared test fixtures.

The environment is configured *before* importing the application so that the
settings cache picks up an isolated in-memory database.
"""

from __future__ import annotations

import os

os.environ["NETSPACE_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["NETSPACE_LOG_LEVEL"] = "WARNING"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    """A TestClient with a fresh, empty database per test."""
    Base.metadata.drop_all(bind=engine)
    init_db()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def sample_vlsm_payload() -> dict:
    """The mandatory VLSM regression scenario from the specification."""
    return {
        "base_network": "192.168.10.0/24",
        "departments": [
            {"name": "Administration", "required_hosts": 50},
            {"name": "ICT", "required_hosts": 25},
            {"name": "Finance", "required_hosts": 20},
            {"name": "Human Resources", "required_hosts": 12},
            {"name": "Guest Network", "required_hosts": 10},
        ],
    }
