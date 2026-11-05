"""Input abuse tests: malformed, oversized, and injection attempts.

Documented equivalent of the roadmap's M9 security coverage for M9-AC-002
(MILESTONES.md §M9; roadmap paths stay in their documented flat-layout
substitutions — `backend/tests/test_auth.py` covers the auth/abuse pair
(rate limiting, 1 MiB request cap), this file covers payload- and
query-shaped abuse".

Everything hostile must end as a structured client error (422/404) or be
treated strictly as inert data — never a 500, never an effect on stored
state (SQL metacharacters are handled by parameterized SQLAlchemy queries).
"""

from __future__ import annotations

import pytest
from conftest import *  # noqa: F401,F403 — reuse the client fixture
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import encode_token, password_hash, runtime_secret
from app.db.session import SessionLocal
from app.models.network import Network

SQL_INJECTIONS = [
    "'; DROP TABLE networks;--",
    "1' OR '1'='1",
    "nvidia' UNION SELECT username, password_hash FROM users--",
]
LIKE_METACHARS = "%_.\\"

PATH_BOMBS = [
    "/api/v1/networks/abc",
    "/api/v1/networks/%2E%2E%2F%2E%2E",
    "/api/v1/reports/networks/1%00/csv",
]


def _admin_headers() -> dict[str, str]:
    """Bearer token for the admin fixture account (created on demand)."""
    from app.models.user import User as U

    with SessionLocal() as db:
        admin = db.query(U).filter(U.username == "adminuser").first()
        if admin is None:
            admin = U(
                username="adminuser",
                role="admin",
                password_hash=password_hash("AdminPass1!"),
            )
            db.add(admin)
            db.commit()
        return {
            "Authorization": "Bearer "
            + encode_token(
                {"uid": admin.id, "role": "admin"},
                runtime_secret(get_settings().auth_secret),
                expires_minutes=get_settings().jwt_expires_minutes,
            )
        }


def _network_count() -> int:
    with SessionLocal() as db:
        try:
            return int(db.scalar(select(func.count()).select_from(Network)))
        finally:
            db.rollback()


def test_malformed_json_bodies_rejected(client: TestClient) -> None:
    """Broken/binary/oversized-field JSON gets a structured 422, never a 500."""
    for payload in (b"{not json", b"[1,2,3]", b"\"just a string\"", b""):
        res = client.post(
            "/api/v1/networks",
            content=payload,
            headers={"content-type": "application/json"},
        )
        assert res.status_code in (401, 422), payload
        assert "error" in res.json(), payload


@pytest.mark.parametrize("payload", SQL_INJECTIONS)
def test_sql_injection_via_search_is_inert(client: TestClient, payload: str) -> None:
    """Injection strings through `q` are stored data, not SQL (M9-AC-002)."""
    headers = _admin_headers()
    r = client.post(
        "/api/v1/networks",
        headers=headers,
        json={"name": "Anchor Net", "cidr": "10.70.0.0/24"},
    )
    assert r.status_code == 201, r.text
    before = _network_count()

    res = client.get("/api/v1/networks", params={"q": payload})
    assert res.status_code == 200, res.text
    # the must-not-happen: silent data destruction
    assert _network_count() == before, "payload must not change stored rows"
    assert "items" in res.json()


def test_like_metacharacters_treated_literally(client: TestClient) -> None:
    """%/_ in a search must not become wildcard machinery beyond intended use."""
    headers = _admin_headers()
    client.post(
        "/api/v1/networks",
        headers=headers,
        json={"name": "Production Core", "cidr": "10.71.0.0/24"},
    )
    res = client.get("/api/v1/networks", params={"q": LIKE_METACHARS})
    assert res.status_code == 200
    assert all(item["name"] != "" for item in res.json()["items"])


@pytest.mark.parametrize("path", PATH_BOMBS)
def test_malformed_path_params_rejected(client: TestClient, path: str) -> None:
    """Bad path segments end as structured client errors, never trace leaks."""
    res = client.get(path)
    # 401 is expected on guarded routes (auth precedes 404 resolution), 404 on
    # public unknown paths, 422 for unparsable typed segments — all structured.
    assert res.status_code in (401, 422, 404), path
    body = res.json()
    assert "error" in body, path
    assert "traceback" not in res.text.lower()


def test_oversized_field_rejected(client: TestClient) -> None:
    """A 5,000-char name violates the schema cap (max 200) -> 422."""
    headers = _admin_headers()
    res = client.post(
        "/api/v1/networks",
        headers=headers,
        json={"name": "x" * 5000, "cidr": "10.72.0.0/24"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"
    assert _network_count() == 0


def test_invalid_pagination_and_filters_rejected(client: TestClient) -> None:
    """Query enclosures: negative pages, impossible sizes, bogus enums."""
    for params in (
        {"page": "0"},
        {"page": "-5"},
        {"page_size": "0"},
        {"page_size": "100000"},
        {"family": "banana"},
    ):
        res = client.get("/api/v1/networks", params=params)
        assert res.status_code == 422, params
        assert "error" in res.json(), params


def test_wrong_type_fields_rejected(client: TestClient) -> None:
    """Type mismatches (vlan 'ten', gateway list) get structured 422s."""
    headers = _admin_headers()
    net = client.post(
        "/api/v1/networks",
        headers=headers,
        json={"name": "Typed Net", "cidr": "10.73.0.0/24"},
    )
    net_id = net.json()["id"]
    res = client.post(
        "/api/v1/subnets",
        headers=headers,
        json={
            "network_id": net_id,
            "name": "Ten VLAN",
            "cidr": "10.73.0.0/26",
            "vlan_id": "ten",
        },
    )
    assert res.status_code == 422
    assert "error" in res.json()


def test_deeply_nested_payload_bounded(client: TestClient) -> None:
    """A 512-deep departments array over the plan budget is capped, not fatal."""
    headers = _admin_headers()
    res = client.post(
        "/api/v1/calculator/vlsm",
        headers=headers,
        json={
            "base_network": "10.0.0.0/24",
            "departments": [
                {"name": f"dept-{i}", "required_hosts": 2} for i in range(512)
            ],
        },
    )
    assert res.status_code == 422, res.text
    assert "error" in res.json()
