"""Dynamic VLSM allocation engine.

Deterministic, largest-first, aligned first-fit allocation of subnets inside a
single parent network.

Algorithm (documented optimization objective and limitations)
------------------------------------------------------------
1. Validate the base network and every department requirement.
2. Compute each department's *effective host requirement*::

       effective = ceil(required_hosts * (1 + growth_percent / 100))
                   + additional_reserved_addresses
                   + (1 if a gateway address is reserved else 0)

3. Select the smallest subnet prefix whose usable capacity satisfies the
   effective requirement (best-fit capacity calculation). IPv4 ``/31`` and
   ``/32`` are only chosen when the policy explicitly allows point-to-point or
   host-route allocations.
4. Sort candidates by descending address capacity; ties keep the caller's input
   order (stable sort), which makes the result deterministic.
5. Place each subnet at the first aligned, non-overlapping position scanning
   forward from the start of the parent network (first-fit over aligned
   boundaries).
6. If any department cannot be placed, raise ``InsufficientSpaceError`` before
   any records are committed — nothing is partially allocated.

Optimization objective: minimize total allocated address space subject to
alignment, containment and per-department capacity constraints, with a
largest-first greedy ordering.

Known limitation: largest-first + aligned first-fit is optimal for the common
contiguous single-parent case (and is what the mandatory test scenario
requires), but it is a greedy heuristic — it is not guaranteed to find the
globally least-fragmented solution for *every* exotic combination of
fixed-prefix overrides and gateway placement constraints. Alternative
strategies can be plugged in behind the same interface without changing
callers.
"""

from __future__ import annotations

import ipaddress
import math
from dataclasses import dataclass
from typing import Any

from app.services.subnet_calculator import (
    SubnetCalculationError,
    is_aligned,
    is_contained,
    min_prefix_for_hosts,
    networks_overlap,
    parse_address,
    parse_network,
    remaining_ranges,
    subnet_details,
    usable_capacity,
)

IPNetworkType = ipaddress.IPv4Network | ipaddress.IPv6Network


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class VLSMError(ValueError):
    """Base error for the allocation engine."""

    def __init__(
        self, code: str, message: str, details: list[dict[str, Any]] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or []


class InsufficientSpaceError(VLSMError):
    def __init__(self, message: str, details: list[dict[str, Any]] | None = None) -> None:
        super().__init__("insufficient_space", message, details)


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

@dataclass
class DepartmentRequirement:
    name: str
    required_hosts: int
    department_id: str | None = None
    description: str | None = None
    vlan_id: int | None = None
    gateway: str | None = None
    additional_reserved_addresses: int = 0
    growth_percent: float | None = None
    prefix_length: int | None = None  # explicit override
    allow_point_to_point: bool | None = None
    allow_host_route: bool | None = None


@dataclass
class AllocationPolicy:
    allow_point_to_point: bool = False
    allow_host_route: bool = False
    growth_percent: float = 0.0
    utilization_warning_threshold: float = 80.0
    max_departments: int = 256


VLAN_MIN, VLAN_MAX = 1, 4094


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_departments(
    departments: list[DepartmentRequirement], policy: AllocationPolicy
) -> None:
    if not departments:
        raise VLSMError("validation_error", "At least one department requirement is required")
    if len(departments) > policy.max_departments:
        raise VLSMError(
            "validation_error",
            f"Too many departments: {len(departments)} > limit {policy.max_departments}",
        )
    seen_names: set[str] = set()
    seen_ids: set[str] = set()
    seen_vlans: dict[int, str] = {}
    problems: list[dict[str, Any]] = []
    for idx, dept in enumerate(departments):
        name = (dept.name or "").strip()
        if not name:
            problems.append({"field": f"departments[{idx}].name", "message": "Name is required"})
        elif name.lower() in seen_names:
            problems.append(
                {"field": f"departments[{idx}].name", "message": f"Duplicate department name '{name}'"}
            )
        seen_names.add(name.lower())

        if dept.department_id:
            if dept.department_id in seen_ids:
                problems.append(
                    {
                        "field": f"departments[{idx}].department_id",
                        "message": f"Duplicate department identifier '{dept.department_id}'",
                    }
                )
            seen_ids.add(dept.department_id)

        if dept.required_hosts < 1:
            problems.append(
                {
                    "field": f"departments[{idx}].required_hosts",
                    "message": "Required hosts must be a positive integer",
                }
            )
        if dept.vlan_id is not None and not VLAN_MIN <= dept.vlan_id <= VLAN_MAX:
            problems.append(
                {
                    "field": f"departments[{idx}].vlan_id",
                    "message": f"VLAN ID must be between {VLAN_MIN} and {VLAN_MAX}",
                }
            )
        elif dept.vlan_id is not None:
            if dept.vlan_id in seen_vlans:
                problems.append(
                    {
                        "field": f"departments[{idx}].vlan_id",
                        "message": (
                            f"VLAN {dept.vlan_id} is already used by "
                            f"'{seen_vlans[dept.vlan_id]}'"
                        ),
                    }
                )
            seen_vlans[dept.vlan_id] = name
        if dept.additional_reserved_addresses < 0:
            problems.append(
                {
                    "field": f"departments[{idx}].additional_reserved_addresses",
                    "message": "Reserved addresses cannot be negative",
                }
            )
        if dept.growth_percent is not None and dept.growth_percent < 0:
            problems.append(
                {
                    "field": f"departments[{idx}].growth_percent",
                    "message": "Growth allowance cannot be negative",
                }
            )
    if problems:
        raise VLSMError("validation_error", "Department requirements are invalid", problems)


def effective_hosts(dept: DepartmentRequirement, policy: AllocationPolicy) -> int:
    """Effective host requirement including growth and reservations."""
    growth = policy.growth_percent if dept.growth_percent is None else dept.growth_percent
    grown = math.ceil(dept.required_hosts * (1 + growth / 100.0))
    reserved = dept.additional_reserved_addresses + (1 if dept.gateway else 0)
    return grown + reserved


# ---------------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------------

def allocate(
    base_network: str | IPNetworkType,
    departments: list[DepartmentRequirement],
    policy: AllocationPolicy | None = None,
) -> dict[str, Any]:
    """Run the full VLSM allocation and return the plan as a plain dict."""
    policy = policy or AllocationPolicy()
    warnings: list[str] = []

    # 1. base network
    try:
        base = (
            base_network
            if isinstance(base_network, (ipaddress.IPv4Network, ipaddress.IPv6Network))
            else parse_network(base_network)
        )
    except SubnetCalculationError as exc:
        raise VLSMError("validation_error", exc.message, [{"field": "base_network", "message": exc.message}]) from exc
    family = base.version

    # 2. department validation
    _validate_departments(departments, policy)

    # 3. effective requirements + prefix selection
    candidates: list[dict[str, Any]] = []
    for idx, dept in enumerate(departments):
        eff = effective_hosts(dept, policy)
        allow_p2p = (
            policy.allow_point_to_point if dept.allow_point_to_point is None
            else dept.allow_point_to_point
        )
        allow_hr = (
            policy.allow_host_route if dept.allow_host_route is None
            else dept.allow_host_route
        )
        if dept.prefix_length is not None:
            prefix = dept.prefix_length
            max_len = base.max_prefixlen
            if not 0 <= prefix <= max_len:
                raise VLSMError(
                    "validation_error",
                    f"Prefix length /{prefix} is invalid for IPv{family}",
                    [{"field": f"departments[{idx}].prefix_length", "message": f"must be 0..{max_len}"}],
                )
            if prefix < base.prefixlen:
                raise VLSMError(
                    "validation_error",
                    f"Requested /{prefix} is larger than the parent {base}",
                    [
                        {
                            "field": f"departments[{idx}].prefix_length",
                            "message": f"must be >= /{base.prefixlen}",
                        }
                    ],
                )
            probe = ipaddress.ip_network(
                (base.network_address, prefix)
            )
            if usable_capacity(probe) < eff:
                raise VLSMError(
                    "validation_error",
                    f"'{dept.name}': a /{prefix} provides {usable_capacity(probe)} usable "
                    f"addresses but {eff} are required",
                    [{"field": f"departments[{idx}].prefix_length", "message": "too small for requirement"}],
                )
        else:
            try:
                prefix = min_prefix_for_hosts(
                    eff, family, allow_point_to_point=allow_p2p, allow_host_route=allow_hr
                )
            except SubnetCalculationError as exc:
                raise VLSMError(
                    "validation_error",
                    f"'{dept.name}': {exc.message}",
                    [{"field": f"departments[{idx}].required_hosts", "message": exc.message}],
                ) from exc
        capacity = 1 << (base.max_prefixlen - prefix)
        candidates.append(
            {
                "index": idx,
                "dept": dept,
                "effective_hosts": eff,
                "prefix": prefix,
                "capacity": capacity,
            }
        )

    # gateway validation (family) — containment checked after placement
    for cand in candidates:
        dept = cand["dept"]
        if dept.gateway:
            try:
                gw = parse_address(dept.gateway, family=family)
            except SubnetCalculationError as exc:
                raise VLSMError(
                    "validation_error",
                    f"'{dept.name}': {exc.message}",
                    [{"field": f"departments[{cand['index']}].gateway", "message": exc.message}],
                ) from exc
            cand["gateway_addr"] = gw

    # 4. sort: descending capacity, stable (input order breaks ties)
    candidates.sort(key=lambda c: -c["capacity"])

    # 5. aligned first-fit placement
    base_start = int(base.network_address)
    base_end = int(base.broadcast_address)
    placed: list[IPNetworkType] = []

    # 5a. a department gateway pins its subnet to the block containing the
    # gateway address (growing the block when the gateway would otherwise be
    # the network/broadcast address). Reserve those blocks up-front so that
    # free first-fit cannot steal them.
    reserved: list[tuple[int, int]] = []
    for cand in candidates:
        gw = cand.get("gateway_addr")
        if gw is None:
            continue
        gw_int = int(gw)
        if not base_start <= gw_int <= base_end:
            raise VLSMError(
                "validation_error",
                f"'{cand['dept'].name}': gateway {gw} is outside the parent network {base}",
                [
                    {
                        "field": f"departments[{cand['index']}].gateway",
                        "message": "gateway must be inside the parent network",
                    }
                ],
            )
        size = cand["capacity"]
        start = gw_int & ~(size - 1)
        while True:
            in_base = start >= base_start and start + size - 1 <= base_end
            usable = family != 4 or size <= 2 or gw_int not in (start, start + size - 1)
            if in_base and usable:
                break
            if not in_base or size >= base.num_addresses:
                raise VLSMError(
                    "validation_error",
                    f"'{cand['dept'].name}': gateway {gw} equals the network or broadcast "
                    f"address of every possible subnet inside {base}",
                    [
                        {
                            "field": f"departments[{cand['index']}].gateway",
                            "message": "gateway cannot be the network or broadcast address",
                        }
                    ],
                )
            size <<= 1
            start = gw_int & ~(size - 1)
        cand["fixed_place"] = (start, size)
        reserved.append((start, size))

    for cand in candidates:
        block = cand["capacity"]
        if "fixed_place" in cand:
            start, size = cand["fixed_place"]
            prefix = base.max_prefixlen - (size.bit_length() - 1)
            network = ipaddress.ip_network((start, prefix))
            if any(networks_overlap(network, p) for p in placed):
                raise InsufficientSpaceError(
                    f"Parent network {base} cannot satisfy the gateway placement of "
                    f"'{cand['dept'].name}' — the required block is already allocated",
                    [
                        {
                            "department": cand["dept"].name,
                            "required_prefix": prefix,
                            "required_addresses": size,
                            "effective_hosts": cand["effective_hosts"],
                        }
                    ],
                )
            chosen = network
        else:
            cursor = base_start
            chosen = None
            while cursor + block - 1 <= base_end:
                aligned_start = ((cursor + block - 1) // block) * block
                if aligned_start + block - 1 > base_end:
                    break
                network = ipaddress.ip_network((aligned_start, cand["prefix"]))
                net_start = int(network.network_address)
                net_end = int(network.broadcast_address)
                overlaps = any(networks_overlap(network, p) for p in placed) or any(
                    net_start <= r_end and r_start <= net_end for r_start, r_end in reserved
                )
                if not overlaps:
                    chosen = network
                    break
                cursor = aligned_start + block
            if chosen is None:
                raise InsufficientSpaceError(
                    f"Parent network {base} cannot accommodate "
                    f"{len(candidates)} department subnets; "
                    f"'{cand['dept'].name}' requires a /{cand['prefix']} "
                    f"({cand['capacity']} addresses) which does not fit in the remaining space",
                    [
                        {
                            "department": cand["dept"].name,
                            "required_prefix": cand["prefix"],
                            "required_addresses": cand["capacity"],
                            "effective_hosts": cand["effective_hosts"],
                        }
                    ],
                )
        # structural invariants (defensive — placement guarantees them)
        assert is_aligned(chosen) and is_contained(chosen, base)
        cand["network"] = chosen
        placed.append(chosen)

    # 6. build output
    allocations: list[dict[str, Any]] = []
    for seq, cand in enumerate(sorted(candidates, key=lambda c: c["index"]), start=1):
        dept: DepartmentRequirement = cand["dept"]
        net: IPNetworkType = cand["network"]
        details = subnet_details(net)
        usable = usable_capacity(net)
        unused = usable - cand["effective_hosts"]
        # Utilization = share of the allocated usable capacity that is actually
        # required (effective requirement / usable capacity).
        util = 100.0 * cand["effective_hosts"] / usable if usable else 0.0
        utilization = round(100.0 * net.num_addresses / base.num_addresses, 4)

        reserved = dept.additional_reserved_addresses + (1 if dept.gateway else 0)
        gateway_value: str | None = None
        if dept.gateway:
            gw = cand["gateway_addr"]
            if not is_contained(ipaddress.ip_network((gw, gw.max_prefixlen)), net):
                raise VLSMError(
                    "validation_error",
                    f"'{dept.name}': gateway {gw} is outside the allocated subnet {net}",
                    [
                        {
                            "field": f"departments[{cand['index']}].gateway",
                            "message": "gateway must be inside the allocated subnet",
                        }
                    ],
                )
            if family == 4 and net.prefixlen <= 30:
                if gw in (net.network_address, net.broadcast_address):
                    raise VLSMError(
                        "validation_error",
                        f"'{dept.name}': gateway {gw} equals the network or broadcast "
                        f"address of {net}",
                        [
                            {
                                "field": f"departments[{cand['index']}].gateway",
                                "message": "gateway cannot be the network or broadcast address",
                            }
                        ],
                    )
            gateway_value = str(gw)

        alloc: dict[str, Any] = {
            "sequence": seq,
            "department": dept.name,
            "department_id": dept.department_id,
            "description": dept.description,
            "vlan_id": dept.vlan_id,
            "requested_hosts": dept.required_hosts,
            "effective_hosts": cand["effective_hosts"],
            "network": str(net),
            "prefix_length": net.prefixlen,
            "total_addresses": net.num_addresses,
            "usable_capacity": usable,
            "unused_usable_capacity": unused,
            "utilization_percent": round(util, 2),
            "space_utilization_percent": utilization,
            "gateway": gateway_value,
            "reserved_addresses": reserved,
            "status": "allocated",
            "growth_percent": (
                policy.growth_percent if dept.growth_percent is None else dept.growth_percent
            ),
        }
        for key in (
            "network_address",
            "first_usable",
            "last_usable",
            "address_range",
            "address_class",
            "address_scope",
        ):
            alloc[key] = details.get(key)
        if family == 4:
            alloc["subnet_mask"] = details.get("subnet_mask")
            alloc["wildcard_mask"] = details.get("wildcard_mask")
            alloc["broadcast_address"] = details.get("broadcast_address")
        else:
            alloc["subnet_mask"] = None
            alloc["wildcard_mask"] = None
            alloc["broadcast_address"] = None
            alloc["note"] = details.get("note")
        allocations.append(alloc)

        if dept.growth_percent:
            warnings.append(
                f"{dept.name}: growth allowance of {dept.growth_percent:g}% raises the "
                f"effective requirement from {dept.required_hosts} to {cand['effective_hosts']} hosts"
            )

    # 7. summary
    remaining = remaining_ranges(base, placed)
    allocated_total = sum(n.num_addresses for n in placed)
    allocated_usable = sum(usable_capacity(n) for n in placed)
    parent_total = base.num_addresses
    overall_util = round(100.0 * allocated_total / parent_total, 4) if parent_total else 0.0
    remaining_total = parent_total - allocated_total
    requested_total = sum(d.required_hosts for d in departments)

    if overall_util >= policy.utilization_warning_threshold:
        warnings.append(
            f"Parent network utilization is {overall_util:.1f}% "
            f"(threshold {policy.utilization_warning_threshold:g}%)"
        )
    if remaining_total == 0:
        warnings.append("Parent network is fully allocated; no free address space remains")
    vlan_usage: dict[int, list[str]] = {}
    for alloc in allocations:
        if alloc["vlan_id"] is not None:
            vlan_usage.setdefault(alloc["vlan_id"], []).append(alloc["department"])
    for vlan, names in vlan_usage.items():
        if len(names) > 1:
            warnings.append(f"VLAN {vlan} is shared by: {', '.join(names)}")

    return {
        "base_network": str(base),
        "family": family,
        "algorithm_version_hint": None,  # filled by the service layer with the configured version
        "policy": {
            "allow_point_to_point": policy.allow_point_to_point,
            "allow_host_route": policy.allow_host_route,
            "growth_percent": policy.growth_percent,
            "allocation_strategy": "largest-first aligned first-fit",
        },
        "allocations": allocations,
        "remaining_ranges": remaining,
        "summary": {
            "parent_total_addresses": parent_total,
            "allocated_addresses": allocated_total,
            "allocated_usable_capacity": allocated_usable,
            "remaining_addresses": remaining_total,
            "remaining_usable_capacity": sum(r["usable_hosts"] for r in remaining),
            "total_requested_hosts": requested_total,
            "total_effective_hosts": sum(a["effective_hosts"] for a in allocations),
            "overall_utilization_percent": overall_util,
            "department_count": len(allocations),
            "success": True,
            "warnings": warnings,
            "errors": [],
        },
    }


def validate_plan_inputs(
    base_network: str,
    departments: list[DepartmentRequirement],
    policy: AllocationPolicy | None = None,
) -> list[dict[str, Any]]:
    """Validate without allocating; returns a list of problems (empty when valid)."""
    try:
        allocate(base_network, departments, policy)
    except VLSMError as exc:
        return [{"code": exc.code, "message": exc.message, "details": exc.details}]
    return []
