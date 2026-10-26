"""Integration tests for network/subnet/IP-address inventory endpoints.

Since M5 the inventory write endpoints require an authenticated operator/admin
bearer token (401 otherwise). An autouse fixture injects the shared admin token
into this module's TestClient so the endpoint tests exercise the same contract.
Anonymous/role-rejection behavior is covered by ``test_auth.py``.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _auth_admin_token(client: TestClient, admin_token: str) -> None:
    """Default Authorization header for every request in this module (M5 AAA)."""
    client.headers["Authorization"] = f"Bearer {admin_token}"


def _create_network(client: TestClient, name: str = "HQ LAN", cidr: str = "192.168.10.0/24", *, role: str = "admin") -> dict:
    from app.core.config import get_settings
    from app.core.security import encode_token, password_hash, runtime_secret
    from app.db.session import SessionLocal
    from app.models.user import User

    settings = get_settings()
    with SessionLocal() as db:
        admin = db.query(User).filter(User.username == "adminuser").first()
        if admin is None:
            admin = User(
                username="adminuser",
                role=role,
                password_hash=password_hash("AdminPass1!"),
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
        token = encode_token(
            {"uid": admin.id, "role": admin.role},
            runtime_secret(settings.auth_secret),
            expires_minutes=settings.jwt_expires_minutes,
        )
    r = client.post(
        "/api/v1/networks",
        json={"name": name, "cidr": cidr, "site": "HQ"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()


# --- networks ---------------------------------------------------------------

def test_network_crud(client: TestClient) -> None:
    net = _create_network(client)
    assert net["cidr"] == "192.168.10.0/24"
    assert net["family"] == 4

    r = client.get(f"/api/v1/networks/{net['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["details"]["broadcast_address"] == "192.168.10.255"

    r = client.patch(f"/api/v1/networks/{net['id']}", json={"site": "Branch-1"})
    assert r.status_code == 200
    assert r.json()["site"] == "Branch-1"

    r = client.delete(f"/api/v1/networks/{net['id']}")
    assert r.status_code == 204
    assert client.get(f"/api/v1/networks/{net['id']}").status_code == 404


def test_network_duplicate_name_409(client: TestClient) -> None:
    _create_network(client)
    r = client.post("/api/v1/networks", json={"name": "hq lan", "cidr": "10.0.0.0/24"})
    assert r.status_code == 409


def test_network_duplicate_cidr_409(client: TestClient) -> None:
    _create_network(client)
    r = client.post("/api/v1/networks", json={"name": "Other", "cidr": "192.168.10.0/24"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "duplicate_cidr"


def test_network_invalid_cidr_422(client: TestClient) -> None:
    r = client.post("/api/v1/networks", json={"name": "Bad", "cidr": "999.0.0.0/24"})
    assert r.status_code == 422


def test_network_list_filters_and_pagination(client: TestClient) -> None:
    for i in range(5):
        _create_network(client, name=f"Net {i}", cidr=f"10.{i}.0.0/16")
    r = client.get("/api/v1/networks", params={"page": 2, "page_size": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 5
    assert body["pages"] == 3
    assert len(body["items"]) == 2

    r = client.get("/api/v1/networks", params={"q": "Net 3"})
    assert r.json()["total"] == 1

    r = client.get("/api/v1/networks", params={"family": 6})
    assert r.json()["total"] == 0


def test_network_missing_404(client: TestClient) -> None:
    assert client.get("/api/v1/networks/999").status_code == 404


# --- subnets ----------------------------------------------------------------

def test_subnet_create_and_overlap_conflict(client: TestClient) -> None:
    net = _create_network(client)
    r = client.post(
        "/api/v1/subnets",
        json={"network_id": net["id"], "name": "Admin", "cidr": "192.168.10.0/26", "vlan_id": 10},
    )
    assert r.status_code == 201, r.text
    subnet = r.json()
    assert subnet["details"]["subnet_mask"] == "255.255.255.192"

    # overlapping subnet is rejected
    r = client.post(
        "/api/v1/subnets",
        json={"network_id": net["id"], "name": "Overlap", "cidr": "192.168.10.32/27"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "overlap"

    # non-overlapping is fine
    r = client.post(
        "/api/v1/subnets",
        json={"network_id": net["id"], "name": "ICT", "cidr": "192.168.10.64/27"},
    )
    assert r.status_code == 201


def test_subnet_outside_parent_422(client: TestClient) -> None:
    net = _create_network(client)
    r = client.post(
        "/api/v1/subnets",
        json={"network_id": net["id"], "name": "Outside", "cidr": "10.1.0.0/24"},
    )
    assert r.status_code == 422


def test_subnet_misaligned_422(client: TestClient) -> None:
    net = _create_network(client)
    # 192.168.10.32/26 is a valid address but not a /26 network boundary
    r = client.post(
        "/api/v1/subnets",
        json={"network_id": net["id"], "name": "Misaligned", "cidr": "192.168.10.32/26"},
    )
    assert r.status_code == 422


def test_subnet_invalid_gateway_422(client: TestClient) -> None:
    net = _create_network(client)
    r = client.post(
        "/api/v1/subnets",
        json={
            "network_id": net["id"],
            "name": "GW",
            "cidr": "192.168.10.0/26",
            "gateway": "192.168.10.0",  # network address
        },
    )
    assert r.status_code == 422


def test_subnet_duplicate_vlan_ok_but_duplicate_cidr_409(client: TestClient) -> None:
    net = _create_network(client)
    r = client.post(
        "/api/v1/subnets",
        json={"network_id": net["id"], "name": "A", "cidr": "192.168.10.0/26"},
    )
    assert r.status_code == 201
    r = client.post(
        "/api/v1/subnets",
        json={"network_id": net["id"], "name": "B", "cidr": "192.168.10.0/26"},
    )
    assert r.status_code == 409


def test_subnet_release_allows_reuse(client: TestClient) -> None:
    net = _create_network(client)
    r = client.post(
        "/api/v1/subnets",
        json={"network_id": net["id"], "name": "Temp", "cidr": "192.168.10.0/26"},
    )
    sid = r.json()["id"]
    assert client.patch(f"/api/v1/subnets/{sid}", json={"status": "released"}).status_code == 200
    r = client.post(
        "/api/v1/subnets",
        json={"network_id": net["id"], "name": "New", "cidr": "192.168.10.0/26"},
    )
    assert r.status_code == 201


def test_network_delete_blocked_with_active_subnets(client: TestClient) -> None:
    net = _create_network(client)
    client.post(
        "/api/v1/subnets",
        json={"network_id": net["id"], "name": "A", "cidr": "192.168.10.0/26"},
    )
    r = client.delete(f"/api/v1/networks/{net['id']}")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "network_not_empty"


def test_subnet_list_filters(client: TestClient) -> None:
    net = _create_network(client)
    client.post(
        "/api/v1/subnets",
        json={"network_id": net["id"], "name": "Admin", "cidr": "192.168.10.0/26", "vlan_id": 10},
    )
    client.post(
        "/api/v1/subnets",
        json={"network_id": net["id"], "name": "ICT", "cidr": "192.168.10.64/27", "vlan_id": 20},
    )
    r = client.get("/api/v1/subnets", params={"vlan_id": 20})
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["name"] == "ICT"
    r = client.get("/api/v1/subnets", params={"network_id": net["id"], "q": "Admin"})
    assert r.json()["total"] == 1
    r = client.get("/api/v1/subnets", params={"network_id": net["id"]})
    assert r.json()["total"] == 2
    r = client.get("/api/v1/subnets", params={"family": 4})
    assert r.json()["total"] == 2


# --- IP addresses -----------------------------------------------------------

def _subnet_id(client: TestClient, net: dict) -> int:
    r = client.post(
        "/api/v1/subnets",
        json={"network_id": net["id"], "name": "Admin", "cidr": "192.168.10.0/26"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_ip_address_crud(client: TestClient) -> None:
    net = _create_network(client)
    sid = _subnet_id(client, net)
    r = client.post(
        "/api/v1/ip-addresses",
        json={"subnet_id": sid, "address": "192.168.10.1", "hostname": "gw-hq", "device": "core-sw"},
    )
    assert r.status_code == 201, r.text
    addr = r.json()
    assert addr["family"] == 4

    r = client.patch(f"/api/v1/ip-addresses/{addr['id']}", json={"status": "deprecated"})
    assert r.status_code == 200
    assert r.json()["status"] == "deprecated"

    # deprecated address can be re-registered
    r = client.post(
        "/api/v1/ip-addresses",
        json={"subnet_id": sid, "address": "192.168.10.1"},
    )
    assert r.status_code == 201

    # the deprecated record was reused for the re-registration, so it is
    # assigned again and cannot be deleted until deprecated once more
    r = client.delete(f"/api/v1/ip-addresses/{addr['id']}")
    assert r.status_code == 409
    client.patch(f"/api/v1/ip-addresses/{addr['id']}", json={"status": "deprecated"})
    assert client.delete(f"/api/v1/ip-addresses/{addr['id']}").status_code == 204


def test_duplicate_ip_assignment_409(client: TestClient) -> None:
    net = _create_network(client)
    sid = _subnet_id(client, net)
    client.post("/api/v1/ip-addresses", json={"subnet_id": sid, "address": "192.168.10.5"})
    r = client.post("/api/v1/ip-addresses", json={"subnet_id": sid, "address": "192.168.10.5"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "duplicate_assignment"


def test_ip_outside_subnet_422(client: TestClient) -> None:
    net = _create_network(client)
    sid = _subnet_id(client, net)
    r = client.post("/api/v1/ip-addresses", json={"subnet_id": sid, "address": "192.168.10.200"})
    assert r.status_code == 422


def test_ip_network_broadcast_rejected(client: TestClient) -> None:
    net = _create_network(client)
    sid = _subnet_id(client, net)
    r = client.post("/api/v1/ip-addresses", json={"subnet_id": sid, "address": "192.168.10.0"})
    assert r.status_code == 422
    r = client.post("/api/v1/ip-addresses", json={"subnet_id": sid, "address": "192.168.10.63"})
    assert r.status_code == 422


def test_assigned_ip_cannot_be_deleted(client: TestClient) -> None:
    net = _create_network(client)
    sid = _subnet_id(client, net)
    r = client.post("/api/v1/ip-addresses", json={"subnet_id": sid, "address": "192.168.10.10"})
    aid = r.json()["id"]
    r = client.delete(f"/api/v1/ip-addresses/{aid}")
    assert r.status_code == 409
    client.patch(f"/api/v1/ip-addresses/{aid}", json={"status": "available"})
    assert client.delete(f"/api/v1/ip-addresses/{aid}").status_code == 204


def test_subnet_delete_blocked_by_addresses_unless_forced(client: TestClient) -> None:
    net = _create_network(client)
    sid = _subnet_id(client, net)
    client.post("/api/v1/ip-addresses", json={"subnet_id": sid, "address": "192.168.10.10"})
    r = client.delete(f"/api/v1/subnets/{sid}")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "subnet_not_empty"
    assert client.delete(f"/api/v1/subnets/{sid}", params={"force": True}).status_code == 204


# --- departments ------------------------------------------------------------

def test_department_crud(client: TestClient) -> None:
    r = client.post(
        "/api/v1/departments",
        json={"name": "Finance", "default_host_requirement": 20, "vlan_id": 30},
    )
    assert r.status_code == 201, r.text
    did = r.json()["id"]

    r = client.post(
        "/api/v1/departments",
        json={"name": "finance", "default_host_requirement": 5},
    )
    assert r.status_code == 409

    assert client.patch(f"/api/v1/departments/{did}", json={"site": "HQ"}).json()["site"] == "HQ"
    assert client.get("/api/v1/departments", params={"q": "fin"}).json()["total"] == 1
    assert client.delete(f"/api/v1/departments/{did}").status_code == 204


def test_department_invalid_vlan_422(client: TestClient) -> None:
    r = client.post("/api/v1/departments", json={"name": "X", "vlan_id": 4095})
    assert r.status_code == 422


# --- dashboard / audit ------------------------------------------------------

def test_dashboard_and_audit(client: TestClient, sample_vlsm_payload: dict) -> None:
    _create_network(client)
    client.post("/api/v1/allocation-plans", json={"name": "P1", **sample_vlsm_payload})
    r = client.get("/api/v1/dashboard/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["total_networks"] == 1
    assert body["total_plans"] == 1
    assert body["conflicts"] == []
    assert isinstance(body["networks"], list)

    r = client.get("/api/v1/audit-events")
    assert r.status_code == 200
    assert r.json()["total"] >= 2
    actions = {item["action"] for item in r.json()["items"]}
    assert "create" in actions
