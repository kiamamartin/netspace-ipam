"""Property-style invariant tests over randomly generated valid inputs.

The six key invariants from the specification are verified across many random
(base network, requirement list) combinations using a fixed seed for
reproducibility.
"""

from __future__ import annotations

import ipaddress
import random

from app.services.subnet_calculator import is_aligned
from app.services.vlsm_allocator import (
    AllocationPolicy,
    DepartmentRequirement,
    InsufficientSpaceError,
    allocate,
)

SEED = 20261015


def _check_invariants(base: str, depts: list[DepartmentRequirement]) -> None:
    result = allocate(base, depts, AllocationPolicy())
    parent = ipaddress.ip_network(base, strict=False)
    allocations = result["allocations"]

    nets = [ipaddress.ip_network(a["network"]) for a in allocations]

    # 1. containment
    for net in nets:
        assert net.subnet_of(parent), f"{net} not inside {parent}"

    # 2. no overlap
    for i, a in enumerate(nets):
        for b in nets[i + 1:]:
            assert not a.overlaps(b), f"{a} overlaps {b}"

    # 3. alignment
    for net in nets:
        assert is_aligned(net), f"{net} misaligned"

    # 4. usable capacity satisfies effective requirement
    for a in allocations:
        assert a["usable_capacity"] >= a["effective_hosts"], a

    # 5. nothing exceeds the parent (implied by 1+2, asserted explicitly)
    assert sum(n.num_addresses for n in nets) <= parent.num_addresses

    # 6. determinism
    assert allocate(base, depts, AllocationPolicy()) == result

    # remaining ranges account for the leftovers exactly
    remaining = parent.num_addresses - sum(n.num_addresses for n in nets)
    assert sum(r["total_addresses"] for r in result["remaining_ranges"]) == remaining


def test_random_ipv4_allocations() -> None:
    rng = random.Random(SEED)
    checked = 0
    for _ in range(300):
        parent_prefix = rng.randint(20, 28)
        parent = ipaddress.ip_network(
            f"10.{rng.randint(0, 255)}.{rng.randint(0, 255)}.0/{parent_prefix}",
            strict=False,
        )
        count = rng.randint(1, 8)
        depts: list[DepartmentRequirement] = []
        names = set()
        for i in range(count):
            name = f"Dept-{parent_prefix}-{i}-{rng.randint(0, 99999)}"
            while name in names:
                name += "x"
            names.add(name)
            # keep requirements small enough that most plans fit
            hosts = rng.randint(1, max(2, min(100, parent.num_addresses // (count * 2))))
            depts.append(DepartmentRequirement(name, hosts))
        try:
            _check_invariants(str(parent), depts)
        except InsufficientSpaceError:
            continue  # explicit error is the correct behaviour; nothing committed
        checked += 1
    assert checked > 100, f"too few successful allocations exercised: {checked}"


def test_random_ipv6_allocations() -> None:
    rng = random.Random(SEED + 1)
    for _ in range(50):
        parent_prefix = rng.randint(48, 64)
        parent = ipaddress.ip_network(f"2001:db8:{rng.randint(0, 0xFFFF):x}::/{parent_prefix}")
        count = rng.randint(1, 5)
        depts = [
            DepartmentRequirement(f"V6-{i}-{rng.randint(0, 99999)}", rng.randint(1, 4000))
            for i in range(count)
        ]
        try:
            _check_invariants(str(parent), depts)
        except InsufficientSpaceError:
            continue


def test_growth_and_reservations_keep_invariants() -> None:
    rng = random.Random(SEED + 2)
    for _ in range(100):
        parent = ipaddress.ip_network(f"172.{rng.randint(16, 31)}.{rng.randint(0, 255)}.0/24")
        count = rng.randint(1, 5)
        depts = []
        for i in range(count):
            depts.append(
                DepartmentRequirement(
                    name=f"G-{i}-{rng.randint(0, 99999)}",
                    required_hosts=rng.randint(1, 40),
                    growth_percent=rng.choice([0.0, 5.0, 10.0, 25.0]),
                    additional_reserved_addresses=rng.randint(0, 3),
                    gateway=f"{parent.network_address + rng.randint(1, 200)}" if rng.random() < 0.5 else None,
                )
            )
        try:
            _check_invariants(str(parent), depts)
        except InsufficientSpaceError:
            continue
