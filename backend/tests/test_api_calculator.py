"""Integration tests for calculator endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["algorithm_version"]


def test_subnet_calc(client: TestClient) -> None:
    r = client.post("/api/v1/calculator/subnet", json={"network": "192.168.10.0/24"})
    assert r.status_code == 200
    body = r.json()
    assert body["network"] == "192.168.10.0/24"
    assert body["subnet_mask"] == "255.255.255.0"
    assert body["wildcard_mask"] == "0.0.0.255"
    assert body["broadcast_address"] == "192.168.10.255"
    assert body["first_usable"] == "192.168.10.1"
    assert body["last_usable"] == "192.168.10.254"
    assert body["usable_hosts"] == 254
    assert body["total_addresses"] == 256


def test_subnet_calc_invalid_cidr(client: TestClient) -> None:
    r = client.post("/api/v1/calculator/subnet", json={"network": "bogus"})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "invalid_cidr"
    assert err["details"]


def test_subnet_calc_family_mismatch(client: TestClient) -> None:
    r = client.post("/api/v1/calculator/subnet", json={"network": "2001:db8::/64", "family": 4})
    assert r.status_code == 422


def test_subnet_calc_ipv6(client: TestClient) -> None:
    r = client.post("/api/v1/calculator/subnet", json={"network": "2001:db8::/64"})
    assert r.status_code == 200
    body = r.json()
    assert body["total_addresses"] == 2**64
    assert "broadcast_address" not in body
    assert body["usable_hosts"] is None


def test_subnet_calc_with_hosts(client: TestClient) -> None:
    r = client.post("/api/v1/calculator/subnet", json={"network": "192.168.10.0/24", "hosts": 50})
    assert r.status_code == 200
    assert r.json()["required_prefix_length"] == 26


def test_vlsm_mandatory_scenario(client: TestClient, sample_vlsm_payload: dict) -> None:
    r = client.post("/api/v1/calculator/vlsm", json=sample_vlsm_payload)
    assert r.status_code == 200
    body = r.json()
    nets = {a["department"]: a["network"] for a in body["allocations"]}
    assert nets == {
        "Administration": "192.168.10.0/26",
        "ICT": "192.168.10.64/27",
        "Finance": "192.168.10.96/27",
        "Human Resources": "192.168.10.128/28",
        "Guest Network": "192.168.10.144/28",
    }
    assert body["summary"]["allocated_addresses"] == 160
    assert body["summary"]["remaining_addresses"] == 96
    assert body["algorithm_version"]


def test_vlsm_insufficient_space_is_409(client: TestClient) -> None:
    r = client.post(
        "/api/v1/calculator/vlsm",
        json={
            "base_network": "192.168.10.0/26",
            "departments": [{"name": "A", "required_hosts": 50}, {"name": "B", "required_hosts": 50}],
        },
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "insufficient_space"


def test_vlsm_duplicate_names_422(client: TestClient) -> None:
    r = client.post(
        "/api/v1/calculator/vlsm",
        json={
            "base_network": "192.168.10.0/24",
            "departments": [{"name": "A", "required_hosts": 10}, {"name": "A", "required_hosts": 5}],
        },
    )
    assert r.status_code == 422


def test_vlsm_invalid_vlan_422(client: TestClient) -> None:
    r = client.post(
        "/api/v1/calculator/vlsm",
        json={
            "base_network": "192.168.10.0/24",
            "departments": [{"name": "A", "required_hosts": 10, "vlan_id": 5000}],
        },
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_vlsm_empty_departments_422(client: TestClient) -> None:
    r = client.post(
        "/api/v1/calculator/vlsm",
        json={"base_network": "192.168.10.0/24", "departments": []},
    )
    assert r.status_code == 422


def test_vlsm_malformed_body_422(client: TestClient) -> None:
    r = client.post("/api/v1/calculator/vlsm", json={})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "validation_error"


def test_split(client: TestClient) -> None:
    r = client.post("/api/v1/calculator/split", json={"network": "10.0.0.0/24", "count": 4})
    assert r.status_code == 200
    assert [s["network"] for s in r.json()["subnets"]] == [
        "10.0.0.0/26", "10.0.0.64/26", "10.0.0.128/26", "10.0.0.192/26",
    ]


def test_split_by_prefix(client: TestClient) -> None:
    r = client.post("/api/v1/calculator/split", json={"network": "10.0.0.0/24", "prefix_length": 28})
    assert r.status_code == 200
    assert r.json()["count"] == 16


def test_split_requires_count_or_prefix(client: TestClient) -> None:
    r = client.post("/api/v1/calculator/split", json={"network": "10.0.0.0/24"})
    assert r.status_code == 422


def test_summarize(client: TestClient) -> None:
    r = client.post(
        "/api/v1/calculator/summarize",
        json={"networks": ["192.168.1.0/25", "192.168.1.128/25"]},
    )
    assert r.status_code == 200
    assert [s["network"] for s in r.json()["summarized"]] == ["192.168.1.0/24"]


def test_summarize_invalid_entries(client: TestClient) -> None:
    r = client.post("/api/v1/calculator/summarize", json={"networks": ["nope"]})
    assert r.status_code == 422


def test_validate_ok_with_normalization_warning(client: TestClient) -> None:
    r = client.post("/api/v1/calculator/validate", json={"cidr": "192.168.1.5/24"})
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert body["normalized"]["cidr"] == "192.168.1.0/24"
    assert body["warnings"]


def test_validate_invalid_vlan(client: TestClient) -> None:
    r = client.post("/api/v1/calculator/validate", json={"vlan_id": 0})
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is False
    assert any(e["field"] == "vlan_id" for e in body["errors"])


def test_validate_departments(client: TestClient) -> None:
    r = client.post(
        "/api/v1/calculator/validate",
        json={
            "base_network": "192.168.10.0/24",
            "departments": [{"name": "A", "required_hosts": 50}],
        },
    )
    assert r.status_code == 200
    assert r.json()["valid"] is True
    assert r.json()["normalized"]["department_count"] == 1
