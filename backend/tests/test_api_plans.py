"""Integration tests for allocation plans: save, activate, recalculate, archive."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _save_plan(client: TestClient, name: str = "Q1 Plan", payload: dict | None = None) -> dict:
    payload = payload or {
        "base_network": "192.168.10.0/24",
        "departments": [
            {"name": "Administration", "required_hosts": 50},
            {"name": "ICT", "required_hosts": 25},
        ],
    }
    r = client.post("/api/v1/allocation-plans", json={"name": name, **payload})
    assert r.status_code == 201, r.text
    return r.json()


def test_plan_lifecycle(client: TestClient) -> None:
    plan = _save_plan(client)
    assert plan["status"] == "draft"
    assert plan["family"] == 4
    assert len(plan["results"]["allocations"]) == 2

    # activate commits subnets to a (new) network
    r = client.post(f"/api/v1/allocation-plans/{plan['id']}/activate")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["subnets_created"] == 2
    assert body["status"] == "active"
    assert body["network_id"]

    # activating twice is a conflict
    r = client.post(f"/api/v1/allocation-plans/{plan['id']}/activate")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "plan_active"

    # subnets now exist in inventory
    r = client.get("/api/v1/subnets", params={"network_id": body["network_id"]})
    assert r.json()["total"] == 2
    names = {i["name"] for i in r.json()["items"]}
    assert names == {"Administration", "ICT"}

    # archived plan cannot be activated
    r = client.post(f"/api/v1/allocation-plans/{plan['id']}/archive")
    assert r.status_code == 200
    assert r.json()["status"] == "archived"
    r = client.post(f"/api/v1/allocation-plans/{plan['id']}/archive")
    assert r.status_code == 409


def test_plan_activation_conflicts_with_existing_subnet(client: TestClient) -> None:
    """A plan that becomes stale (subnet created after preview) must not commit."""
    r = client.post("/api/v1/networks", json={"name": "HQ", "cidr": "192.168.10.0/24"})
    net_id = r.json()["id"]
    plan = _save_plan(client)

    # someone allocates .0/26 directly before the plan is activated
    r = client.post(
        "/api/v1/subnets",
        json={"network_id": net_id, "name": "Manual", "cidr": "192.168.10.0/26"},
    )
    assert r.status_code == 201

    r = client.post(f"/api/v1/allocation-plans/{plan['id']}/activate")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "overlap"

    # nothing was committed: only the manual subnet exists
    r = client.get("/api/v1/subnets", params={"network_id": net_id})
    assert r.json()["total"] == 1

    # recalculate against current inputs; the engine still returns the same
    # layout (the conflict is with the DB, not the math) and the plan can be
    # archived afterwards.
    r = client.post(f"/api/v1/allocation-plans/{plan['id']}/recalculate")
    assert r.status_code == 200
    assert len(r.json()["results"]["allocations"]) == 2
    r = client.post(f"/api/v1/allocation-plans/{plan['id']}/archive")
    assert r.status_code == 200


def test_recalculate_updates_results_without_activation(client: TestClient) -> None:
    plan = _save_plan(client)
    r = client.post(f"/api/v1/allocation-plans/{plan['id']}/recalculate")
    assert r.status_code == 200
    assert r.json()["status"] == "draft"  # still a draft: nothing committed
    r = client.get("/api/v1/subnets")
    assert r.json()["total"] == 0


def test_plan_invalid_request_422(client: TestClient) -> None:
    r = client.post(
        "/api/v1/allocation-plans",
        json={
            "name": "Bad",
            "base_network": "192.168.10.0/24",
            "departments": [{"name": "A", "required_hosts": 50}, {"name": "A", "required_hosts": 10}],
        },
    )
    assert r.status_code == 422


def test_plan_insufficient_space_409(client: TestClient) -> None:
    r = client.post(
        "/api/v1/allocation-plans",
        json={
            "name": "TooBig",
            "base_network": "192.168.10.0/26",
            "departments": [{"name": "A", "required_hosts": 50}, {"name": "B", "required_hosts": 50}],
        },
    )
    assert r.status_code == 409


def test_plan_duplicate_name_409(client: TestClient) -> None:
    _save_plan(client)
    r = client.post(
        "/api/v1/allocation-plans",
        json={
            "name": "Q1 Plan",
            "base_network": "10.0.0.0/24",
            "departments": [{"name": "A", "required_hosts": 10}],
        },
    )
    assert r.status_code == 409


def test_plan_list_and_get(client: TestClient) -> None:
    _save_plan(client, name="Plan A")
    _save_plan(
        client,
        name="Plan B",
        payload={
            "base_network": "10.0.0.0/24",
            "departments": [{"name": "X", "required_hosts": 10}],
        },
    )
    r = client.get("/api/v1/allocation-plans")
    assert r.json()["total"] == 2

    r = client.get("/api/v1/allocation-plans", params={"status": "draft"})
    assert r.json()["total"] == 2

    r = client.get("/api/v1/allocation-plans", params={"q": "Plan B"})
    assert r.json()["total"] == 1
    plan_id = r.json()["items"][0]["id"]
    assert client.get(f"/api/v1/allocation-plans/{plan_id}").status_code == 200
    assert client.get("/api/v1/allocation-plans/9999").status_code == 404


def test_plan_activation_creates_network_when_missing(client: TestClient) -> None:
    plan = _save_plan(client)
    r = client.post(f"/api/v1/allocation-plans/{plan['id']}/activate")
    assert r.status_code == 200
    network_id = r.json()["network_id"]
    r = client.get(f"/api/v1/networks/{network_id}")
    assert r.status_code == 200
    assert r.json()["cidr"] == "192.168.10.0/24"
    assert len(r.json()["subnets"]) == 2


def test_update_plan_metadata(client: TestClient) -> None:
    plan = _save_plan(client)
    r = client.patch(f"/api/v1/allocation-plans/{plan['id']}", json={"notes": "Reviewed by NOC"})
    assert r.status_code == 200
    assert r.json()["notes"] == "Reviewed by NOC"
