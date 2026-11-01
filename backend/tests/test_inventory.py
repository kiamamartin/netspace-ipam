"""M7 — Inventory & lifecycle management integration tests.

Covers MILESTONES.md M7 acceptance criteria M7-AC-001..007 at the API level:

* M7-AC-001: sites, departments, parent networks, child subnets are created
  and managed (the ``site`` text field is the Phase-1 contract; the ``sites``
  registry arrives in M12 and must not be built twice here).
* M7-AC-002: subnet status, owner, purpose (description), location and
  lifecycle state are tracked.
* M7-AC-003: search/filter by CIDR, department, site, status, ownership.
* M7-AC-004: utilization and remaining capacity are exposed.
* M7-AC-005: reservation and release workflows (subnets and addresses).
* M7-AC-006: allocation history survives address-space changes.
* M7-AC-007: conflicting reservations and duplicate allocations are rejected.

M7-AC-008 (concurrency) is separately verified in ``tests/concurrency/``.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _auth_admin_token(client: TestClient, admin_token: str) -> None:
    """M5 contract: inventory writes require an authenticated admin token."""
    client.headers["Authorization"] = f"Bearer {admin_token}"


def _network(client: TestClient, name: str, cidr: str, site: str | None = None) -> dict:
    r = client.post("/api/v1/networks", json={"name": name, "cidr": cidr, "site": site})
    assert r.status_code == 201, r.text
    return r.json()


def _create_subnet(client: TestClient, network_id: int, cidr: str, name: str = "Sub", **extra) -> dict:
    r = client.post(
        "/api/v1/subnets",
        json={"network_id": network_id, "name": name, "cidr": cidr, **extra},
    )
    return r


# --- M7-AC-001 ---------------------------------------------------------------


def test_ac001_create_sites_departments_networks_subnets(client: TestClient) -> None:
    r = client.post(
        "/api/v1/departments",
        json={"name": "Inventory Ops", "site": "London HQ", "default_host_requirement": 40},
    )
    assert r.status_code == 201, r.text
    assert r.json()["site"] == "London HQ"

    net = _network(client, "M7 HQ", "10.220.0.0/16", site="London HQ")
    sub = _create_subnet(client, net["id"], "10.220.0.0/24", "Office LAN", vlan_id=10)
    assert sub.status_code == 201, sub.text

    detail = client.get(f"/api/v1/networks/{net['id']}").json()
    assert [s["cidr"] for s in detail["subnets"]] == ["10.220.0.0/24"]


# --- M7-AC-002 ---------------------------------------------------------------


def test_ac002_owner_purpose_location_lifecycle_tracked(client: TestClient) -> None:
    net = _network(client, "M7 Tracking", "10.221.0.0/16", site="Leeds")
    body = _create_subnet(
        client,
        net["id"],
        "10.221.0.0/24",
        "Voice",
        vlan_id=20,
        owner="IT Voice Team",
        description="CUCM handsets — purpose: voice services",
        location="Leeds comms room A",
    ).json()
    assert body["owner"] == "IT Voice Team"
    assert body["location"] == "Leeds comms room A"
    assert body["status"] == "allocated"

    r = client.patch(
        f"/api/v1/subnets/{body['id']}",
        json={"owner": "ISEC Voice", "location": "Leeds comms room B"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["owner"] == "ISEC Voice"
    assert r.json()["location"] == "Leeds comms room B"

    detail = client.get(f"/api/v1/subnets/{body['id']}").json()
    assert detail["status"] == "allocated"
    assert detail["ip_address_count"] == 0


# --- M7-AC-003 ---------------------------------------------------------------


def test_ac003_search_and_filters(client: TestClient) -> None:
    net_a = _network(client, "M7 Filter A", "10.222.0.0/16", site="London HQ")
    net_b = _network(client, "M7 Filter B", "10.223.0.0/16", site="Manchester")
    _create_subnet(client, net_a["id"], "10.222.0.0/24", "F-A-users", owner="Team Alpha")
    _create_subnet(client, net_b["id"], "10.223.0.0/24", "F-B-users", owner="Team Beta")
    _create_subnet(client, net_b["id"], "10.223.1.0/24", "F-B-reserved", owner="Team Beta", status="reserved")

    # ownership filter
    r = client.get("/api/v1/subnets", params={"owner": "alpha"})
    assert [s["name"] for s in r.json()["items"]] == ["F-A-users"]
    # site (parent network) filter
    r = client.get("/api/v1/subnets", params={"site": "Manchester"})
    assert {s["name"] for s in r.json()["items"]} == {"F-B-users", "F-B-reserved"}
    # status filter
    r = client.get("/api/v1/subnets", params={"site": "Manchester", "status": "reserved"})
    assert [s["name"] for s in r.json()["items"]] == ["F-B-reserved"]
    # free-text query hits owner/location/cidr paths
    r = client.get("/api/v1/subnets", params={"q": "Team Beta"})
    assert {s["name"] for s in r.json()["items"]} == {"F-B-users", "F-B-reserved"}
    r = client.get("/api/v1/subnets", params={"q": "10.222.0.0"})
    assert [s["name"] for s in r.json()["items"]] == ["F-A-users"]

    # IP ownership by department filter
    dept = client.post(
        "/api/v1/departments", json={"name": "M7 Dept", "site": "London HQ"}
    ).json()
    sub = client.get("/api/v1/subnets", params={"q": "F-A-users"}).json()["items"][0]
    ip = client.post(
        "/api/v1/ip-addresses",
        json={
            "subnet_id": sub["id"],
            "address": "10.222.0.10",
            "hostname": "host-a",
            "device": "dev-host-a",
            "department_id": dept["id"],
        },
    )
    assert ip.status_code == 201, ip.text
    r = client.get("/api/v1/ip-addresses", params={"department_id": dept["id"]})
    assert [x["address"] for x in r.json()["items"]] == ["10.222.0.10"]
    r = client.get("/api/v1/ip-addresses", params={"device": "dev-host"})
    assert r.json()["items"][0]["hostname"] == "host-a"


# --- M7-AC-004 ---------------------------------------------------------------


def test_ac004_utilization_and_remaining_capacity(client: TestClient) -> None:
    net = _network(client, "M7 Util", "10.224.0.0/16", site=None)
    sub = _create_subnet(client, net["id"], "10.224.0.0/26", "Util").json()
    assert sub["ip_address_count"] == 0

    detail = client.get(f"/api/v1/subnets/{sub['id']}").json()
    util = detail["utilization"]
    assert util["total_addresses"] == 64
    assert util["usable_addresses"] == 62
    assert util["assigned_addresses"] == 0
    assert util["remaining_usable"] == 62
    assert util["ip_utilization_percent"] == 0.0

    for addr in ("10.224.0.10", "10.224.0.11", "10.224.0.12"):
        r = client.post(
            "/api/v1/ip-addresses", json={"subnet_id": sub["id"], "address": addr}
        )
        assert r.status_code == 201, r.text

    util = client.get(f"/api/v1/subnets/{sub['id']}").json()["utilization"]
    assert util["assigned_addresses"] == 3
    assert util["remaining_usable"] == 59
    assert util["ip_utilization_percent"] == 4.84  # 3/62
    # network-level utilization (dashboard read model)
    summary = client.get("/api/v1/dashboard/summary").json()
    netUtil = [n for n in summary["networks"] if n["network_id"] == net["id"]][0]
    assert netUtil["total_addresses"] == 65536
    assert netUtil["allocated_addresses"] == 64

    # the subnet list read model carries the same utilization payload so the
    # inventory table does not need one request per row
    listing = client.get(f"/api/v1/subnets?network_id={net['id']}&page_size=200").json()
    row = [s for s in listing["items"] if s["id"] == sub["id"]][0]
    assert row["ip_address_count"] == 3
    assert row["utilization"]["assigned_addresses"] == 3
    assert row["utilization"]["remaining_usable"] == 59
    assert row["utilization"]["ip_utilization_percent"] == 4.84


# --- M7-AC-005 ---------------------------------------------------------------


def test_ac005_subnet_reservation_release_workflow(client: TestClient) -> None:
    net = _network(client, "M7 Lifecycle", "10.225.0.0/16")
    sub = _create_subnet(client, net["id"], "10.225.0.0/24", "Lifec").json()

    # planned -> reserved -> allocated -> released lifecycle
    r = client.post(f"/api/v1/subnets/{sub['id']}/reserve")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "reserved"
    # reserving an already-reserved row is a conflict
    assert client.post(f"/api/v1/subnets/{sub['id']}/reserve").status_code == 409
    assert client.post(f"/api/v1/subnets/{sub['id']}/release").status_code == 200
    assert client.get(f"/api/v1/subnets/{sub['id']}").json()["status"] == "released"
    # an already-released row cannot be released again
    assert client.post(f"/api/v1/subnets/{sub['id']}/release").status_code == 409
    assert client.post(f"/api/v1/subnets/{sub['id']}/reserve").status_code == 409

    # re-allocating a released CIDR reuses the record (history is preserved)
    again = _create_subnet(client, net["id"], "10.225.0.0/24", "Lifec-reuse")
    assert again.status_code == 201, again.text
    assert again.json()["id"] == sub["id"]

    # release is blocked while addresses are assigned; force overrides
    r = client.post(
        "/api/v1/ip-addresses", json={"subnet_id": sub["id"], "address": "10.225.0.5"}
    )
    assert r.status_code == 201
    resp = client.post(f"/api/v1/subnets/{sub['id']}/release")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "subnet_not_empty"
    assert client.post(f"/api/v1/subnets/{sub['id']}/release", params={"force": "true"}).status_code == 200


def test_ac005_ip_reservation_release_workflow(client: TestClient) -> None:
    net = _network(client, "M7 IPLifec", "10.226.0.0/16")
    sub = _create_subnet(client, net["id"], "10.226.0.0/24", "IPLifec").json()

    # availability placeholder -> reserve -> release (tracking row removed)
    ip = client.post(
        "/api/v1/ip-addresses",
        json={"subnet_id": sub["id"], "address": "10.226.0.200", "status": "available"},
    ).json()
    r = client.post(f"/api/v1/ip-addresses/{ip['id']}/reserve")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "reserved"
    assert client.post(f"/api/v1/ip-addresses/{ip['id']}/reserve").status_code == 409
    assert client.post(f"/api/v1/ip-addresses/{ip['id']}/release").status_code == 204
    assert client.get(f"/api/v1/ip-addresses/{ip['id']}").status_code == 404
    # the release stays visible in the resource history
    hist = client.get(f"/api/v1/ip-addresses/{ip['id']}/history")
    assert hist.status_code == 200
    assert [e["action"] for e in hist.json()][:3] == ["release", "reserve", "create"]

    # an assigned address cannot be released directly: deprecate or delete first
    other = client.post(
        "/api/v1/ip-addresses", json={"subnet_id": sub["id"], "address": "10.226.0.205"}
    ).json()
    assert client.post(f"/api/v1/ip-addresses/{other['id']}/release").status_code == 409


# --- M7-AC-006 ---------------------------------------------------------------


def test_ac006_history_preserved_when_address_space_changes(client: TestClient) -> None:
    net = _network(client, "M7 History", "10.227.0.0/16")
    sub = _create_subnet(client, net["id"], "10.227.0.0/24", "Hist", owner="TA").json()
    client.post(f"/api/v1/subnets/{sub['id']}/reserve")
    client.post(f"/api/v1/subnets/{sub['id']}/release")
    reused = _create_subnet(client, net["id"], "10.227.0.0/24", "Hist-reused", owner="TB")
    assert reused.status_code == 201 and reused.json()["id"] == sub["id"]

    r = client.get(f"/api/v1/subnets/{sub['id']}/history")
    assert r.status_code == 200
    actions = [e["action"] for e in r.json()]
    # newest first: the re-allocation, then release, reserve, original create
    assert actions[:4] == ["create", "release", "reserve", "create"], actions
    # and the row itself carried its owner through the re-allocation update
    assert reused.json()["owner"] == "TB"


# --- M7-AC-007 ---------------------------------------------------------------


def test_ac007_conflicts_and_duplicate_allocation_rejected(client: TestClient) -> None:
    net = _network(client, "M7 Conflicts", "10.228.0.0/16")
    first = _create_subnet(client, net["id"], "10.228.0.0/24", "Conf-A")
    assert first.status_code == 201

    dup = _create_subnet(client, net["id"], "10.228.0.0/24", "Conf-Dup")
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "duplicate_cidr"

    overlap = _create_subnet(client, net["id"], "10.228.0.0/25", "Conf-Overlap")
    assert overlap.status_code == 409
    assert overlap.json()["error"]["code"] == "overlap"

    sub = client.get("/api/v1/subnets", params={"q": "Conf-A"}).json()["items"][0]
    ip = client.post(
        "/api/v1/ip-addresses", json={"subnet_id": sub["id"], "address": "10.228.0.7"}
    )
    assert ip.status_code == 201
    dup_ip = client.post(
        "/api/v1/ip-addresses", json={"subnet_id": sub["id"], "address": "10.228.0.7"}
    )
    assert dup_ip.status_code == 409
    assert dup_ip.json()["error"]["code"] == "duplicate_assignment"

    # a direct PATCH cannot bypass the release rule with an active address
    r = client.patch(f"/api/v1/subnets/{sub['id']}", json={"status": "released"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "subnet_not_empty"

    # the dashboard conflict detector stays clean after the rejections above
    summary = client.get("/api/v1/dashboard/summary").json()
    assert summary["conflicts"] == []
