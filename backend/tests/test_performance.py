"""Query performance tests against the documented M9 targets.

Documented equivalent of the roadmap's `backend/tests/performance/` for
M9-AC-005/-007 (MILESTONES.md §M9). Targets and environment are recorded in
`docs/quality/performance-targets.md`; the budgets asserted here are padded
ceilings (roughly 3x the observed medians) so a shared CI box cannot flake
while a runaway regression still fails the gate.

Dataset: deterministic seed over the API itself (8 networks x 8 subnets).
"""

from __future__ import annotations

import time

from conftest import *  # noqa: F401,F403 — reuse the client fixture
from fastapi.testclient import TestClient

# Documented targets (median of 3 runs must stay under these ceilings).
TARGETS_MS = {
    "subnets-list": 800,
    "dashboard-summary": 800,
    "network-csv-export": 1500,
    "subnet-detail": 800,
}


def _admin_headers() -> dict[str, str]:
    '''Bearer token for the admin fixture account (created on demand).'''
    from app.core.config import get_settings
    from app.core.security import encode_token, password_hash, runtime_secret
    from app.db.session import SessionLocal
    from app.models.user import User

    with SessionLocal() as db:
        admin = db.query(User).filter(User.username == "adminuser").first()
        if admin is None:
            admin = User(
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


def _seed_dataset(client: TestClient) -> dict[int, int]:
    """Create 8 networks with 8 subnets each through the real API."""
    import ipaddress

    from app.core.config import get_settings
    from app.core.security import encode_token, password_hash, runtime_secret
    from app.db.session import SessionLocal
    from app.models.user import User

    with SessionLocal() as db:
        admin = db.query(User).filter(User.username == "adminuser").first()
        if admin is None:
            admin = User(
                username="adminuser",
                role="admin",
                password_hash=password_hash("AdminPass1!"),
            )
            db.add(admin)
            db.commit()
        token = encode_token(
            {"uid": admin.id, "role": "admin"},
            runtime_secret(get_settings().auth_secret),
            expires_minutes=get_settings().jwt_expires_minutes,
        )
    headers = {"Authorization": f"Bearer {token}"}

    first_subnet_id: int | None = None
    net_ids: dict[int, int] = {}
    for n in range(8):
        r = client.post(
            "/api/v1/networks",
            headers=headers,
            json={"name": f"Perf Net {n}", "cidr": f"10.{n}.0.0/24"},
        )
        assert r.status_code == 201, r.text
        net_ids[n] = r.json()["id"]
        for s in range(8):
            cidr = str(ipaddress.ip_network(f"10.{n}.0.0/24").network_address + s * 32) + "/27"
            gateway = str(ipaddress.ip_network(cidr).network_address + 1)
            r = client.post(
                "/api/v1/subnets",
                headers=headers,
                json={
                    "network_id": net_ids[n],
                    "name": f"Perf Subnet {n}-{s}",
                    "cidr": cidr,
                    "gateway": gateway,
                },
            )
            assert r.status_code == 201, r.text
            if first_subnet_id is None:
                first_subnet_id = r.json()["id"]
    return {"first_subnet_id": first_subnet_id or 0, "any_network_id": net_ids[0]}


def _median_ms(samples_ms: list[float]) -> float:
    ordered = sorted(samples_ms)
    return ordered[len(ordered) // 2]


def _measure(
    client: TestClient, path: str, runs: int = 3, **params: str
) -> float:
    """Median wall-clock time of `runs` identical authenticated requests, ms."""
    headers = _admin_headers()
    for _ in range(2):  # warm the route (compile path, connections) off the clock
        assert client.get(path, params=params, headers=headers).status_code == 200
    samples: list[float] = []
    for _ in range(runs):
        start = time.perf_counter()
        res = client.get(path, params=params, headers=headers)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert res.status_code == 200, res.text
        samples.append(elapsed_ms)
    return _median_ms(samples)


def test_query_performance_meets_documented_targets(client: TestClient) -> None:
    """M9-AC-005/-007: defined read-model targets hold on the seeded dataset."""
    ids = _seed_dataset(client)

    measurements = {
        "subnets-list": _measure(client, "/api/v1/subnets", page="1", page_size="200"),
        "dashboard-summary": _measure(client, "/api/v1/dashboard/summary"),
        "subnet-detail": _measure(
            client, f"/api/v1/subnets/{ids['first_subnet_id']}"
        ),
        "network-csv-export": _measure(
            client, f"/api/v1/reports/networks/{ids['any_network_id']}/csv"
        ),
    }

    slow = {k: v for k, v in measurements.items() if v > TARGETS_MS[k]}
    report = ", ".join(f"{k}={v:.0f}ms (target {TARGETS_MS[k]}ms)" for k, v in measurements.items())
    assert not slow, f"performance gate exceeded — {report}"
