"""M3 mandatory regression scenario (`MILESTONES.md` §2-M3).

Base network `192.168.10.0/24`, host-requirement driven allocation —
largest-first with correct CIDR alignment, no overlap, full containment:

| Department     | Required hosts | Expected allocation | Usable |
|----------------|----------------|---------------------|--------|
| Administration | 100            | /25 — 126 usable    |
| ICT            | 50             | /26 — 62 usable     |
| Finance        | 25             | /27 — 30 usable     |
| Management     | 10             | /28 — 14 usable     |
"""

import ipaddress

import pytest

from app.services.vlsm_allocator import (
    DepartmentRequirement,
    VLSMError,
    allocate,
)

BASE = "192.168.10.0/24"

DEPARTMENTS = [
    DepartmentRequirement("Administration", 100),
    DepartmentRequirement("ICT", 50),
    DepartmentRequirement("Finance", 25),
    DepartmentRequirement("Management", 10),
]

# department -> (network, broadcast, first_usable, last_usable)
EXPECTED = {
    "Administration": ("192.168.10.0/25", "192.168.10.127", "192.168.10.1", "192.168.10.126"),
    "ICT": ("192.168.10.128/26", "192.168.10.191", "192.168.10.129", "192.168.10.190"),
    "Finance": ("192.168.10.192/27", "192.168.10.223", "192.168.10.193", "192.168.10.222"),
    "Management": ("192.168.10.224/28", "192.168.10.239", "192.168.10.225", "192.168.10.238"),
}

EXPECTED_PREFIXES = {
    "Administration": 25,
    "ICT": 26,
    "Finance": 27,
    "Management": 28,
}


@pytest.fixture(scope="module")
def plan() -> dict:
    return allocate(BASE, DEPARTMENTS)


def test_departments_allocated(plan: dict) -> None:
    allocations = {a["department"]: a for a in plan["allocations"]}
    assert set(allocations) == {d.name for d in DEPARTMENTS}


def test_expected_prefixes(plan: dict) -> None:
    """M3-AC-001: smallest valid prefix for each host count."""
    for a in plan["allocations"]:
        assert a["prefix_length"] == EXPECTED_PREFIXES[a["department"]]
        assert a["total_addresses"] == 2 ** (32 - a["prefix_length"])


def test_allocation_table(plan: dict) -> None:
    """Every allocation lands exactly on the expected block (network, broadcast)."""
    for dept, (network, broadcast, first, last) in EXPECTED.items():
        allocation = next(a for a in plan["allocations"] if a["department"] == dept)
        assert allocation["network"] == network
        assert allocation["network_address"] == network.split("/")[0]
        assert allocation["broadcast_address"] == broadcast
        assert allocation["first_usable"] == first
        assert allocation["last_usable"] == last


def test_network_broadcast_semantics(plan: dict) -> None:
    """M3-AC-002: network + broadcast reserved on every conventional block."""
    for a in plan["allocations"]:
        size = 2 ** (32 - a["prefix_length"])
        net_int = int(ipaddress.ip_address(a["network_address"]))
        bc_int = int(ipaddress.ip_address(a["broadcast_address"]))
        # correct CIDR alignment (M3-AC-004)
        assert net_int % size == 0
        assert bc_int - net_int == size - 1
        # first_usable / last_usable exclude network + broadcast
        assert int(ipaddress.ip_address(a["first_usable"])) == net_int + 1
        assert int(ipaddress.ip_address(a["last_usable"])) == bc_int - 1
        assert a["usable_capacity"] == size - 2


def test_capacity_covers_requirements(plan: dict) -> None:
    """M3-AC: usable capacity >= effective requirement for each department."""
    requirements = {d.name: d.required_hosts for d in DEPARTMENTS}
    for a in plan["allocations"]:
        assert a["usable_capacity"] >= requirements[a["department"]]


def test_prefix_aligned_and_contained(plan: dict) -> None:
    """M3-AC-004 / M3-AC-006: strict alignment and parent containment."""
    parent = ipaddress.ip_network(BASE, strict=True)
    for a in plan["allocations"]:
        child = ipaddress.ip_network(a["network"], strict=True)
        assert child.subnet_of(parent)


def test_no_overlaps(plan: dict) -> None:
    """M3-AC-005: pairwise integer-range check over allocated blocks."""
    ranges = sorted(
        (int(ipaddress.ip_address(a["network_address"])), int(ipaddress.ip_address(a["broadcast_address"])))
        for a in plan["allocations"]
    )
    for (_, end_a), (start_b, _) in zip(ranges, ranges[1:]):
        assert start_b > end_a


def test_summary_counts_and_remainder(plan: dict) -> None:
    """M3-AC-010: summary of consumed, remaining, utilization."""
    summary = plan["summary"]
    allocated = sum(a["total_addresses"] for a in plan["allocations"])
    assert summary["allocated_addresses"] == allocated == 240
    assert summary["parent_total_addresses"] == 256
    assert summary["remaining_addresses"] == 16
    remaining_ranges = plan["remaining_ranges"]
    assert sum(r["total_addresses"] for r in remaining_ranges) == 16
    assert remaining_ranges[0]["start"] == "192.168.10.240"


def test_identical_input_identical_output() -> None:
    """M3-AC-009: full determinism for repeated identical inputs."""
    first = allocate(BASE, DEPARTMENTS)
    second = allocate(BASE, DEPARTMENTS)
    assert first == second
    # determinism must not depend on the input order: largest-first wins
    reordered = allocate(BASE, list(reversed([d for d in DEPARTMENTS])))
    assert {a["department"]: a["network"] for a in first["allocations"]} == {
        a["department"]: a["network"] for a in reordered["allocations"]
    }


def test_insufficient_capacity_rejected() -> None:
    """M3-AC-007 / M3-AC-008: impossible allocations are rejected upfront."""
    too_big = [DepartmentRequirement("A", 200), DepartmentRequirement("B", 200)]
    with pytest.raises(VLSMError):
        allocate(BASE, too_big)
    # three 60-host workloads need 3 x /26 = 192 addresses; a /25 has only 128
    cramped = [
        DepartmentRequirement("A", 60),
        DepartmentRequirement("B", 60),
        DepartmentRequirement("C", 60),
    ]
    with pytest.raises(VLSMError):
        allocate("192.168.10.0/25", cramped)


def test_structured_error_message() -> None:
    """M3-AC-008: structured error payload raised with a real message."""
    with pytest.raises(VLSMError) as excinfo:
        allocate(BASE, [DepartmentRequirement("A", 300), DepartmentRequirement("B", 300)])
    assert len(str(excinfo.value)) > 0
