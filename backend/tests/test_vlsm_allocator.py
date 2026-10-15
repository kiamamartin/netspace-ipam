"""Unit tests for the VLSM allocation engine, including the mandatory
regression scenario from the specification."""

from __future__ import annotations

import pytest

from app.services.vlsm_allocator import (
    AllocationPolicy,
    DepartmentRequirement,
    InsufficientSpaceError,
    VLSMError,
    allocate,
    effective_hosts,
)

MANDATORY = [
    DepartmentRequirement("Administration", 50),
    DepartmentRequirement("ICT", 25),
    DepartmentRequirement("Finance", 20),
    DepartmentRequirement("Human Resources", 12),
    DepartmentRequirement("Guest Network", 10),
]


def _by_dept(result: dict) -> dict[str, dict]:
    return {a["department"]: a for a in result["allocations"]}


# --- mandatory scenario ----------------------------------------------------

def test_mandatory_vlsm_scenario(client) -> None:  # noqa: ARG001 - fixture ensures env
    result = allocate("192.168.10.0/24", MANDATORY, AllocationPolicy())
    depts = _by_dept(result)

    assert depts["Administration"]["network"] == "192.168.10.0/26"
    assert depts["Administration"]["subnet_mask"] == "255.255.255.192"
    assert depts["Administration"]["usable_capacity"] == 62
    assert depts["ICT"]["network"] == "192.168.10.64/27"
    assert depts["ICT"]["subnet_mask"] == "255.255.255.224"
    assert depts["ICT"]["usable_capacity"] == 30
    assert depts["Finance"]["network"] == "192.168.10.96/27"
    assert depts["Finance"]["usable_capacity"] == 30
    assert depts["Human Resources"]["network"] == "192.168.10.128/28"
    assert depts["Human Resources"]["subnet_mask"] == "255.255.255.240"
    assert depts["Human Resources"]["usable_capacity"] == 14
    assert depts["Guest Network"]["network"] == "192.168.10.144/28"
    assert depts["Guest Network"]["usable_capacity"] == 14

    # 160 of 256 addresses allocated, 96 remaining starting at .160
    summary = result["summary"]
    assert summary["allocated_addresses"] == 160
    assert summary["parent_total_addresses"] == 256
    assert summary["remaining_addresses"] == 96
    assert summary["overall_utilization_percent"] == 62.5
    assert result["remaining_ranges"][0]["start"] == "192.168.10.160"
    assert result["remaining_ranges"][0]["total_addresses"] == 96


def test_mandatory_scenario_ipv4_semantics() -> None:
    result = allocate("192.168.10.0/24", MANDATORY, AllocationPolicy())
    for a in result["allocations"]:
        assert a["broadcast_address"] is not None
        assert a["wildcard_mask"] is not None
        assert a["first_usable"] and a["last_usable"]
        assert a["usable_capacity"] >= a["effective_hosts"]


def test_deterministic_output() -> None:
    r1 = allocate("192.168.10.0/24", MANDATORY, AllocationPolicy())
    r2 = allocate("192.168.10.0/24", MANDATORY, AllocationPolicy())
    assert r1 == r2


def test_tie_break_preserves_input_order() -> None:
    # 25 and 20 hosts both need /27; ICT is listed before Finance and must get
    # the earlier block.
    result = allocate(
        "192.168.10.0/24",
        [
            DepartmentRequirement("ICT", 25),
            DepartmentRequirement("Finance", 20),
        ],
        AllocationPolicy(),
    )
    assert result["allocations"][0]["network"] == "192.168.10.0/27"
    assert result["allocations"][1]["network"] == "192.168.10.32/27"


# --- capacity / exhaustion -------------------------------------------------

def test_insufficient_capacity_raises() -> None:
    with pytest.raises(InsufficientSpaceError) as exc:
        allocate(
            "192.168.10.0/26",
            [DepartmentRequirement("A", 50), DepartmentRequirement("B", 50)],
            AllocationPolicy(),
        )
    assert exc.value.code == "insufficient_space"
    assert exc.value.details[0]["department"] == "B"
    assert exc.value.details[0]["required_prefix"] == 26


def test_parent_too_small_for_many_departments() -> None:
    depts = [DepartmentRequirement(f"D{i}", 10) for i in range(1, 40)]
    with pytest.raises(InsufficientSpaceError):
        allocate("10.0.0.0/24", depts, AllocationPolicy())


def test_exact_fit_succeeds() -> None:
    result = allocate(
        "192.168.10.0/26",
        [DepartmentRequirement("A", 30), DepartmentRequirement("B", 30)],
        AllocationPolicy(),
    )
    assert result["summary"]["remaining_addresses"] == 0
    assert any("fully allocated" in w for w in result["summary"]["warnings"])


def test_boundary_requirements() -> None:
    result = allocate("10.0.0.0/24", [DepartmentRequirement("Edge", 62)], AllocationPolicy())
    assert result["allocations"][0]["network"] == "10.0.0.0/26"  # 62 usable exactly
    result = allocate("10.0.0.0/24", [DepartmentRequirement("Edge", 63)], AllocationPolicy())
    assert result["allocations"][0]["network"] == "10.0.0.0/25"  # needs /25


# --- growth allowance ------------------------------------------------------

def test_growth_percent_included_in_effective_requirement() -> None:
    dept = DepartmentRequirement("Ops", 50, growth_percent=50.0)
    assert effective_hosts(dept, AllocationPolicy()) == 75
    result = allocate("10.0.0.0/24", [dept], AllocationPolicy())
    assert result["allocations"][0]["network"] == "10.0.0.0/25"
    assert result["allocations"][0]["effective_hosts"] == 75
    assert result["allocations"][0]["requested_hosts"] == 50
    assert any("growth allowance" in w for w in result["summary"]["warnings"])


def test_policy_level_growth_applies_by_default() -> None:
    policy = AllocationPolicy(growth_percent=100.0)
    result = allocate("10.0.0.0/24", [DepartmentRequirement("X", 10)], policy)
    assert result["allocations"][0]["effective_hosts"] == 20


# --- reservations / gateways ----------------------------------------------

def test_gateway_counts_toward_reservation() -> None:
    dept = DepartmentRequirement("GW Net", 60, gateway="10.0.0.1")
    assert effective_hosts(dept, AllocationPolicy()) == 61
    result = allocate("10.0.0.0/24", [dept], AllocationPolicy())
    alloc = result["allocations"][0]
    assert alloc["gateway"] == "10.0.0.1"
    assert alloc["reserved_addresses"] == 1
    assert alloc["network"] == "10.0.0.0/26"
    assert alloc["usable_capacity"] >= alloc["effective_hosts"]


def test_additional_reserved_addresses() -> None:
    dept = DepartmentRequirement("R", 10, additional_reserved_addresses=4)
    assert effective_hosts(dept, AllocationPolicy()) == 14
    result = allocate("10.0.0.0/24", [dept], AllocationPolicy())
    assert result["allocations"][0]["network"] == "10.0.0.0/28"  # 14 usable exactly


def test_gateway_as_network_address_rejected() -> None:
    with pytest.raises(VLSMError) as exc:
        allocate(
            "10.0.0.0/24",
            [DepartmentRequirement("Bad", 10, gateway="10.0.0.0")],
            AllocationPolicy(),
        )
    assert "network or broadcast" in exc.value.message


def test_gateway_outside_parent_rejected() -> None:
    """A gateway outside the parent network cannot be honoured by placement."""
    with pytest.raises(VLSMError) as exc:
        allocate(
            "10.0.0.0/24",
            [DepartmentRequirement("Bad", 10, gateway="10.9.9.1")],
            AllocationPolicy(),
        )
    assert "outside" in exc.value.message


def test_gateway_family_mismatch_rejected() -> None:
    with pytest.raises(VLSMError):
        allocate(
            "10.0.0.0/24",
            [DepartmentRequirement("Bad", 10, gateway="2001:db8::1")],
            AllocationPolicy(),
        )


# --- validation ------------------------------------------------------------

def test_duplicate_department_names_rejected() -> None:
    with pytest.raises(VLSMError) as exc:
        allocate(
            "10.0.0.0/24",
            [DepartmentRequirement("Sales", 10), DepartmentRequirement("sales", 5)],
            AllocationPolicy(),
        )
    assert any("Duplicate department name" in d.get("message", "") for d in exc.value.details)


def test_zero_hosts_rejected() -> None:
    with pytest.raises(VLSMError):
        allocate("10.0.0.0/24", [DepartmentRequirement("Zero", 0)], AllocationPolicy())


def test_empty_departments_rejected() -> None:
    with pytest.raises(VLSMError):
        allocate("10.0.0.0/24", [], AllocationPolicy())


@pytest.mark.parametrize("vlan", [0, 4095, -1])
def test_invalid_vlan_rejected(vlan: int) -> None:
    with pytest.raises(VLSMError) as exc:
        allocate(
            "10.0.0.0/24",
            [DepartmentRequirement("V", 10, vlan_id=vlan)],
            AllocationPolicy(),
        )
    assert any("VLAN" in d.get("message", "") for d in exc.value.details)


def test_duplicate_vlan_rejected() -> None:
    with pytest.raises(VLSMError) as exc:
        allocate(
            "10.0.0.0/24",
            [
                DepartmentRequirement("A", 10, vlan_id=100),
                DepartmentRequirement("B", 10, vlan_id=100),
            ],
            AllocationPolicy(),
        )
    assert any("already used" in d.get("message", "") for d in exc.value.details)


def test_invalid_base_network_rejected() -> None:
    with pytest.raises(VLSMError):
        allocate("10.0.0.0/33", [DepartmentRequirement("A", 10)], AllocationPolicy())


def test_too_many_departments_rejected() -> None:
    policy = AllocationPolicy(max_departments=5)
    depts = [DepartmentRequirement(f"D{i}", 1) for i in range(6)]
    with pytest.raises(VLSMError):
        allocate("10.0.0.0/16", depts, policy)


# --- explicit prefix overrides ---------------------------------------------

def test_prefix_override_used() -> None:
    result = allocate(
        "10.0.0.0/24",
        [DepartmentRequirement("Big", 10, prefix_length=26)],
        AllocationPolicy(),
    )
    assert result["allocations"][0]["network"] == "10.0.0.0/26"


def test_prefix_override_too_small_rejected() -> None:
    with pytest.raises(VLSMError) as exc:
        allocate(
            "10.0.0.0/24",
            [DepartmentRequirement("Big", 50, prefix_length=28)],
            AllocationPolicy(),
        )
    assert "usable" in exc.value.message


def test_prefix_override_shorter_than_parent_rejected() -> None:
    with pytest.raises(VLSMError):
        allocate(
            "10.0.0.0/24",
            [DepartmentRequirement("Big", 10, prefix_length=16)],
            AllocationPolicy(),
        )


# --- special prefixes ------------------------------------------------------

def test_point_to_point_policy_allocates_slash31() -> None:
    policy = AllocationPolicy(allow_point_to_point=True)
    result = allocate(
        "10.0.0.0/24",
        [DepartmentRequirement("Link A", 2), DepartmentRequirement("Link B", 2)],
        policy,
    )
    nets = [a["network"] for a in result["allocations"]]
    assert nets == ["10.0.0.0/31", "10.0.0.2/31"]


def test_host_route_policy_allocates_slash32() -> None:
    policy = AllocationPolicy(allow_host_route=True)
    result = allocate("10.0.0.0/24", [DepartmentRequirement("Host", 1)], policy)
    assert result["allocations"][0]["network"] == "10.0.0.0/32"
    assert result["allocations"][0]["usable_capacity"] == 1


def test_conventional_policy_never_uses_special_prefixes() -> None:
    result = allocate("10.0.0.0/24", [DepartmentRequirement("Tiny", 1)], AllocationPolicy())
    assert result["allocations"][0]["network"] == "10.0.0.0/30"


# --- IPv6 ------------------------------------------------------------------

def test_ipv6_allocation() -> None:
    result = allocate(
        "2001:db8::/48",
        [DepartmentRequirement("NetA", 1000), DepartmentRequirement("NetB", 4)],
        AllocationPolicy(),
    )
    nets = [a["network"] for a in result["allocations"]]
    assert nets == ["2001:db8::/118", "2001:db8::400/126"]
    for a in result["allocations"]:
        assert a["broadcast_address"] is None  # no IPv4 semantics for IPv6
        assert a["wildcard_mask"] is None
        assert a["usable_capacity"] == a["total_addresses"]
        assert a["note"]


def test_ipv6_family_mismatch_gateway_rejected() -> None:
    with pytest.raises(VLSMError):
        allocate(
            "2001:db8::/48",
            [DepartmentRequirement("N", 10, gateway="10.0.0.1")],
            AllocationPolicy(),
        )


# --- utilization metrics ---------------------------------------------------

def test_utilization_fields() -> None:
    result = allocate("10.0.0.0/24", [DepartmentRequirement("A", 50)], AllocationPolicy())
    alloc = result["allocations"][0]
    assert alloc["unused_usable_capacity"] == 12  # 62 usable - 50 required
    # utilization = effective requirement / usable capacity
    assert alloc["utilization_percent"] == pytest.approx(80.65, abs=0.01)
    assert alloc["space_utilization_percent"] == 25.0  # 64 of 256 addresses


def test_high_utilization_warning() -> None:
    policy = AllocationPolicy(utilization_warning_threshold=50.0)
    result = allocate("10.0.0.0/24", [DepartmentRequirement("A", 200)], policy)
    assert any("utilization" in w.lower() for w in result["summary"]["warnings"])
