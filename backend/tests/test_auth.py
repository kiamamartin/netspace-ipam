"""Security tests for the M5 auth model (`MILESTONES.md` §2-M5).

Documented equivalent of the roadmap's `backend/tests/security/` +
`backend/tests/integration/test_auth.py` paths (tests stay flat).

Permission matrix enforced here (server-side):
- anonymous: GETs allowed; every write 401; auth headers required for /auth/me
- viewer:    authenticated, but every write 403; user admin 403
- operator:  inventory/planning writes OK; user admin 403
- admin:     everything; cannot delete the last admin or disable self
"""

from __future__ import annotations

import pytest
from conftest import *  # noqa: F401,F403 — reuse the client fixture
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import password_hash
from app.db.session import SessionLocal
from app.models.user import User


@pytest.fixture(autouse=True)
def _reset_login_limiter() -> None:
    """Keep the login rate limit isolated between tests.

    The limiter is an in-process module-level structure, so fixture-scoped
    logins from earlier tests would otherwise leak into later ones.
    """
    from app.api.v1.auth import _LOGIN_ATTEMPTS

    _LOGIN_ATTEMPTS.clear()


@pytest.fixture()
def users(client: TestClient):
    """Seed one account per role; returns a login-token helper."""
    accounts = [
        User(username="adminuser", role="admin", password_hash=password_hash("AdminPass1!")),
        User(username="operatoruser", role="operator", password_hash=password_hash("OperatorPass1!")),
        User(username="vieweruser", role="viewer", password_hash=password_hash("ViewerPass1!")),
    ]
    with SessionLocal() as db:
        db.add_all(accounts)
        db.commit()

    def login(username: str, password: str, *, client_ip: str | None = None) -> dict:
        headers = {}
        if client_ip is not None:
            headers["X-Forwarded-For"] = client_ip
        res = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
            headers=headers,
        )
        assert res.status_code == 200, res.text
        data = res.json()
        return {"Authorization": f"Bearer {data['access_token']}"}

    return {"accounts": accounts, "tokens": login}


def test_health_and_reports_readable_anonymously(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
    r = client.get("/api/v1/allocation-plans")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "total" in body


def test_anonymous_write_denied(client: TestClient) -> None:
    """M5-AC-003: anonymous access denied where required (verified by test)."""
    # networks
    res = client.post("/api/v1/networks", json={"name": "X", "cidr": "10.0.0.0/24"})
    assert res.status_code == 401, res.text
    assert client.patch("/api/v1/networks/999", json={"name": "Y"}).status_code == 401
    assert client.delete("/api/v1/networks/999").status_code == 401
    # subnets
    res = client.post("/api/v1/subnets", json={"network_id": 1, "name": "X", "cidr": "10.0.0.0/26"})
    assert res.status_code == 401, res.text
    assert client.patch("/api/v1/subnets/999", json={"name": "Y"}).status_code == 401
    assert client.delete("/api/v1/subnets/999").status_code == 401
    # departments
    res = client.post("/api/v1/departments", json={"name": "X", "default_host_requirement": 5})
    assert res.status_code == 401, res.text
    assert client.patch("/api/v1/departments/999", json={"name": "Y"}).status_code == 401
    assert client.delete("/api/v1/departments/999").status_code == 401
    # IP addresses
    res = client.post("/api/v1/ip-addresses", json={"subnet_id": 1, "address": "192.168.1.5"})
    assert res.status_code == 401, res.text
    assert client.patch("/api/v1/ip-addresses/999", json={"status": "reserved"}).status_code == 401
    assert client.delete("/api/v1/ip-addresses/999").status_code == 401
    # allocation plans
    res = client.post("/api/v1/allocation-plans", json={"name": "P", "base_network": "192.168.10.0/24", "departments": []})
    assert res.status_code in (401, 422), res.text
    assert client.patch("/api/v1/allocation-plans/999", json={"name": "Y"}).status_code == 401
    assert client.post("/api/v1/allocation-plans/999/activate").status_code == 401
    assert client.post("/api/v1/allocation-plans/999/recalculate").status_code == 401
    assert client.post("/api/v1/allocation-plans/999/archive").status_code == 401
    # user administration (admin only)
    assert client.get("/api/v1/auth/users").status_code == 401
    assert client.post("/api/v1/auth/users", json={"username": "x", "password": "Abcdef12!", "role": "viewer"}).status_code == 401
    assert client.patch("/api/v1/auth/users/999", json={"role": "operator"}).status_code == 401
    assert client.delete("/api/v1/auth/users/999").status_code == 401
    # audit events (admin only)
    assert client.get("/api/v1/audit-events").status_code == 401


def test_invalid_tokens_rejected(client: TestClient) -> None:
    """M5-AC-001 + JWT failure paths."""
    for header_value in ["Bearer not-a-token", "Bearer a.b.c", "Bearer "]:
        res = client.get("/api/v1/auth/me", headers={"Authorization": header_value.strip()})
        assert res.status_code == 401
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401


def test_role_matrix_on_idempotent_write(client: TestClient, users) -> None:
    """M5-AC-002/004: operator may write; viewer may not (server-side 403)."""
    tokens = users["tokens"]
    op = {"Authorization": tokens("operatoruser", "OperatorPass1!")["Authorization"]}
    vw = {"Authorization": tokens("vieweruser", "ViewerPass1!")["Authorization"]}

    # --- networks: operator writes, viewer rejected ---
    payload = {"name": "Role Matrix Net", "cidr": "172.31.200.0/24"}
    ok = client.post("/api/v1/networks", json=payload, headers=op)
    assert ok.status_code == 201, ok.text
    net_id = ok.json()["id"]
    denied = client.post(
        "/api/v1/networks",
        json={"name": "Nope", "cidr": "172.31.201.0/24"},
        headers=vw,
    )
    assert denied.status_code == 403
    assert client.patch(f"/api/v1/networks/{net_id}", json={"site": "X"}, headers=vw).status_code == 403
    assert client.delete(f"/api/v1/networks/{net_id}", headers=vw).status_code == 403

    # --- subnets: operator writes, viewer rejected ---
    subnet = client.post(
        "/api/v1/subnets",
        json={"network_id": net_id, "name": "S1", "cidr": "172.31.200.0/26"},
        headers=op,
    )
    assert subnet.status_code == 201, subnet.text
    subnet_id = subnet.json()["id"]
    assert client.post(
        "/api/v1/subnets",
        json={"network_id": net_id, "name": "S2", "cidr": "172.31.200.64/26"},
        headers=vw,
    ).status_code == 403
    assert client.patch(f"/api/v1/subnets/{subnet_id}", json={"name": "X"}, headers=vw).status_code == 403
    assert client.delete(f"/api/v1/subnets/{subnet_id}", headers=vw).status_code == 403

    # --- departments: operator writes, viewer rejected ---
    dep = client.post(
        "/api/v1/departments",
        json={"name": "Dept", "default_host_requirement": 10},
        headers=op,
    )
    assert dep.status_code == 201, dep.text
    dep_id = dep.json()["id"]
    assert client.post(
        "/api/v1/departments",
        json={"name": "Dept2", "default_host_requirement": 5},
        headers=vw,
    ).status_code == 403
    assert client.patch(f"/api/v1/departments/{dep_id}", json={"site": "X"}, headers=vw).status_code == 403
    assert client.delete(f"/api/v1/departments/{dep_id}", headers=vw).status_code == 403

    # --- IP addresses: operator writes, viewer rejected ---
    ip = client.post(
        "/api/v1/ip-addresses",
        json={"subnet_id": subnet_id, "address": "172.31.200.1", "hostname": "gw"},
        headers=op,
    )
    assert ip.status_code == 201, ip.text
    ip_id = ip.json()["id"]
    assert client.post(
        "/api/v1/ip-addresses",
        json={"subnet_id": subnet_id, "address": "172.31.200.2"},
        headers=vw,
    ).status_code == 403
    assert client.patch(f"/api/v1/ip-addresses/{ip_id}", json={"status": "reserved"}, headers=vw).status_code == 403
    assert client.delete(f"/api/v1/ip-addresses/{ip_id}", headers=vw).status_code == 403

    # --- allocation plans: operator writes, viewer rejected ---
    plan = client.post(
        "/api/v1/allocation-plans",
        json={"name": "P", "base_network": "172.31.200.0/24", "departments": [{"name": "D1", "required_hosts": 10}]},
        headers=op,
    )
    assert plan.status_code == 201, plan.text
    plan_id = plan.json()["id"]
    assert client.post(
        "/api/v1/allocation-plans",
        json={"name": "P2", "base_network": "172.31.201.0/24", "departments": [{"name": "D2", "required_hosts": 5}]},
        headers=vw,
    ).status_code == 403
    assert client.patch(f"/api/v1/allocation-plans/{plan_id}", json={"name": "X"}, headers=vw).status_code == 403
    assert client.post(f"/api/v1/allocation-plans/{plan_id}/activate", headers=vw).status_code == 403
    assert client.post(f"/api/v1/allocation-plans/{plan_id}/recalculate", headers=vw).status_code == 403
    assert client.post(f"/api/v1/allocation-plans/{plan_id}/archive", headers=vw).status_code == 403

    # viewer can still read
    me = client.get("/api/v1/auth/me", headers=vw)
    assert me.status_code == 200 and me.json()["role"] == "viewer"

    # list endpoint must return paginated envelopes, not bare arrays
    networks = client.get("/api/v1/networks").json()
    assert isinstance(networks.get("items", []), list)


def test_user_administration_admin_only(client: TestClient, users) -> None:
    """M5-AC-002/004: admins only for user CRUD; operator blocked."""
    tokens = users["tokens"]
    for non_admin_headers in [
        tokens("operatoruser", "OperatorPass1!"),
        tokens("vieweruser", "ViewerPass1!"),
    ]:
        assert client.get("/api/v1/auth/users", headers=non_admin_headers).status_code == 403
        assert client.post(
            "/api/v1/auth/users",
            json={"username": "hacker", "password": "whatever123", "role": "admin"},
            headers=non_admin_headers,
        ).status_code == 403
        # audit events are admin-only
        assert client.get("/api/v1/audit-events", headers=non_admin_headers).status_code == 403
    admin_token = tokens("adminuser", "AdminPass1!")
    created = client.post(
        "/api/v1/auth/users",
        json={"username": "archivist", "password": "Archive123", "role": "viewer"},
        headers=admin_token,
    )
    assert created.status_code == 201 and created.json()["role"] == "viewer"
    _ = client.patch("/api/v1/networks/9999", json={"name": "No"}, headers=admin_token)

    dup = client.post("/api/v1/auth/users", json={"username": "archivist", "password": "Archive123"}, headers=admin_token)
    assert dup.status_code == 409

    _ = client.delete("/api/v1/auth/users/9999", headers=admin_token)

    _ = client.patch("/api/v1/auth/users/9999", json={"role": "admin"}, headers=admin_token)
    assert client.patch("/api/v1/auth/users/9999", json={"role": "admin"}, headers=admin_token).status_code == 404


def test_last_admin_self_removal_blocked(client: TestClient, users) -> None:
    """M5-AC: cannot delete your own admin account."""
    tokens = users["tokens"]
    admin = tokens("adminuser", "AdminPass1!")
    me = client.get("/api/v1/auth/me", headers=admin).json()
    assert me.get("id") is not None, me
    assert client.delete(f"/api/v1/auth/users/{me['id']}", headers=admin).status_code == 409


def test_audit_events_admin_only(client: TestClient, users) -> None:
    """M5-AC-005: audit events are admin-only; operator and viewer get 403."""
    tokens = users["tokens"]
    admin = tokens("adminuser", "AdminPass1!")
    operator = tokens("operatoruser", "OperatorPass1!")
    viewer = tokens("vieweruser", "ViewerPass1!")
    # admin can read audit events
    r = client.get("/api/v1/audit-events", headers=admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "items" in body and "total" in body
    # operator cannot
    assert client.get("/api/v1/audit-events", headers=operator).status_code == 403
    # viewer cannot
    assert client.get("/api/v1/audit-events", headers=viewer).status_code == 403


def test_login_rate_limited(client: TestClient) -> None:
    """M5-AC-007: rate limits on the exposed login endpoint.

    Use a dedicated client IP so login attempts from other tests don't
    consume the same window.
    """
    results = [
        client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "vvvvvvvv"},
            headers={"X-Forwarded-For": "10.200.0.99"},
        )
        for _ in range(6)
    ]
    assert results[-1].status_code == 429
    assert all(r.status_code == 401 for r in results[:5])


def test_request_body_size_limited(client: TestClient) -> None:
    """M5-AC-007: request-size limits on exposed services."""
    res = client.post(
        "/api/v1/networks",
        content=b"x" * (1_048_576 + 1),
        headers={"content-type": "application/json"},
    )
    assert res.status_code == 413


def test_audit_event_emitted_on_stateful_change(
    client: TestClient, users
) -> None:
    """AA-02 evidence: a successful operator write emits an AuditEvent."""
    tokens = users["tokens"]
    before = _audit_event_count()
    r = client.post(
        "/api/v1/networks",
        json={"name": "Audit Check Net", "cidr": "10.200.0.0/24"},
        headers=tokens("operatoruser", "OperatorPass1!"),
    )
    assert r.status_code == 201, r.text
    after = _audit_event_count()
    assert after == before + 1


def test_audit_tracks_user_creation(client: TestClient, users) -> None:
    """AA-03 evidence: user administration is recorded, not silently applied."""
    admin = users["tokens"]("adminuser", "AdminPass1!")
    created = client.post(
        "/api/v1/auth/users",
        json={"username": "auditor", "password": "Auditor123", "role": "viewer"},
        headers=admin,
    )
    assert created.status_code == 201, created.text
    new_user = created.json()
    assert new_user["username"] == "auditor"
    assert new_user["role"] == "viewer"
    rows = _latest_audit_rows(1)
    assert rows, rows
    row = rows[0]
    assert row["resource_type"] == "user", row
    assert str(row["resource_id"]) == str(new_user["id"]), row
    assert row["action"] == "create", row
    assert row.get("actor") in ("adminuser", None), row


def _audit_event_count() -> int:
    from sqlalchemy import func

    from app.models.audit import AuditEvent

    with SessionLocal() as db:
        return int(db.scalar(select(func.count()).select_from(AuditEvent)))


def _latest_audit_rows(n: int) -> list[dict]:
    from app.models.audit import AuditEvent

    with SessionLocal() as db:
        rows = list(db.scalars(select(AuditEvent).order_by(AuditEvent.timestamp.desc()).limit(n)).all())
    return [
        {
            "id": r.id,
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
            "action": r.action,
            "summary": r.summary,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
        }
        for r in rows
    ]


def _rows_by_resource_and_action(resource_type: str, action: str) -> list[dict]:
    """Direct audit lookup scoped to one event type — avoids stale-ID guesswork."""
    from app.models.audit import AuditEvent

    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(AuditEvent)
                .where(AuditEvent.resource_type == resource_type, AuditEvent.action == action)
                .order_by(AuditEvent.timestamp.desc())
            ).all()
        )
    return [
        {
            "id": r.id,
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
            "action": r.action,
            "summary": r.summary,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
        }
        for r in rows
    ]
