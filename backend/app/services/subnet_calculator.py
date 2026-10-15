"""Authoritative IPv4/IPv6 subnet calculation engine.

This module is pure: it does not touch the database or the API layer, so it is
independently testable. All address arithmetic is delegated to Python's
``ipaddress`` module — no manual string manipulation of addresses.

Design notes
------------
* IPv4 usable-host policy:
    - ``/32`` -> 1 usable address (host route).
    - ``/31`` -> 2 usable addresses (RFC 3021 point-to-point).
    - ``/30`` and shorter -> ``total - 2`` (network + broadcast reserved).
* IPv4 ``/31`` and ``/32`` are *special* allocations; the prefix-selection logic
  only picks them when explicitly allowed by the allocation policy.
* IPv6: no broadcast address and no fixed usable-host count. Capacity planning
  uses the total address count of the subnet; the first address of a subnet may
  be the subnet-router anycast address, which is documented as a note rather
  than silently subtracted.
"""

from __future__ import annotations

import ipaddress
import math
from typing import Any, Literal

IPAddressType = ipaddress.IPv4Address | ipaddress.IPv6Address
IPNetworkType = ipaddress.IPv4Network | ipaddress.IPv6Network

AddressClass = Literal["A", "B", "C", "D", "E"]


class SubnetCalculationError(ValueError):
    """Raised when input cannot be interpreted as a valid network/prefix."""

    def __init__(self, message: str, field: str = "network") -> None:
        super().__init__(message)
        self.message = message
        self.field = field


# ---------------------------------------------------------------------------
# Parsing / validation
# ---------------------------------------------------------------------------

def parse_network(value: str, family: int | None = None) -> IPNetworkType:
    """Parse a CIDR string into an ``ipaddress`` network object.

    Host bits set in the input (e.g. ``192.168.10.5/24``) are *normalized*
    (strict=False) so the calculator is forgiving, and the caller can detect
    normalization by comparing the returned network with the raw input.
    """
    if not isinstance(value, str) or not value.strip():
        raise SubnetCalculationError("A network in CIDR notation is required, e.g. 192.168.10.0/24")
    text = value.strip()
    if "/" not in text:
        raise SubnetCalculationError(
            f"'{text}' is missing a prefix length; use CIDR notation such as 192.168.10.0/24"
        )
    try:
        net = ipaddress.ip_network(text, strict=False)
    except ValueError as exc:
        raise SubnetCalculationError(f"Invalid CIDR notation '{text}': {exc}") from exc
    if family is not None:
        want = 4 if family == 4 else 6
        got = net.version
        if got != want:
            raise SubnetCalculationError(
                f"'{text}' is an IPv{got} network but IPv{want} was requested",
                field="family",
            )
    return net


def parse_address(value: str, family: int | None = None) -> IPAddressType:
    if not isinstance(value, str) or not value.strip():
        raise SubnetCalculationError("An IP address is required")
    text = value.strip()
    try:
        addr = ipaddress.ip_address(text)
    except ValueError as exc:
        raise SubnetCalculationError(f"Invalid IP address '{text}': {exc}") from exc
    if family is not None:
        want = 4 if family == 4 else 6
        if addr.version != want:
            raise SubnetCalculationError(
                f"'{text}' is an IPv{addr.version} address but IPv{want} was requested",
                field="family",
            )
    return addr


def normalize_cidr(value: str, family: int | None = None) -> str:
    """Return the canonical CIDR string for ``value``."""
    return str(parse_network(value, family=family))


def is_normalized(value: str, family: int | None = None) -> bool:
    """True when the input already had no host bits set (no normalization needed)."""
    try:
        net = parse_network(value, family=family)
    except SubnetCalculationError:
        return False
    return value.strip() == str(net)


# ---------------------------------------------------------------------------
# Capacity helpers
# ---------------------------------------------------------------------------

def ipv4_usable_hosts(prefix_length: int) -> int:
    """Usable host addresses for an IPv4 prefix under documented semantics."""
    if not 0 <= prefix_length <= 32:
        raise SubnetCalculationError(f"IPv4 prefix length must be 0..32, got {prefix_length}")
    total = 1 << (32 - prefix_length)
    if prefix_length == 32:
        return 1
    if prefix_length == 31:
        return 2  # RFC 3021 point-to-point
    return max(total - 2, 0)


def ipv6_capacity(prefix_length: int) -> int:
    if not 0 <= prefix_length <= 128:
        raise SubnetCalculationError(f"IPv6 prefix length must be 0..128, got {prefix_length}")
    return 1 << (128 - prefix_length)


def usable_capacity(network: IPNetworkType) -> int:
    """Usable capacity of ``network`` under the documented allocation policy."""
    if network.version == 4:
        return ipv4_usable_hosts(network.prefixlen)
    return ipv6_capacity(network.prefixlen)


def min_prefix_for_hosts(
    required_hosts: int,
    family: int,
    *,
    allow_point_to_point: bool = False,
    allow_host_route: bool = False,
) -> int:
    """Smallest subnet prefix (largest prefix value = smallest block) whose usable
    capacity satisfies ``required_hosts``.

    ``/31`` is only selected when ``allow_point_to_point`` and ``/32`` only when
    ``allow_host_route``; conventional LAN allocations never silently receive a
    special-purpose prefix.
    """
    if required_hosts < 1:
        raise SubnetCalculationError("Required host count must be at least 1", field="hosts")
    if family == 4:
        for prefix in range(32, -1, -1):
            if prefix == 32 and not allow_host_route:
                continue
            if prefix == 31 and not allow_point_to_point:
                continue
            if ipv4_usable_hosts(prefix) >= required_hosts:
                return prefix
        raise SubnetCalculationError(
            "No IPv4 prefix can satisfy the requested host count", field="hosts"
        )
    if family == 6:
        for prefix in range(128, -1, -1):
            if ipv6_capacity(prefix) >= required_hosts:
                return prefix
        raise SubnetCalculationError("No IPv6 prefix can satisfy the requested size", field="hosts")
    raise SubnetCalculationError(f"Unsupported address family: {family}", field="family")


def network_for_hosts(required_hosts: int, family: int, **kwargs: Any) -> IPNetworkType:
    """Convenience: build a template network object satisfying ``required_hosts``."""
    base = "0.0.0.0" if family == 4 else "::"
    prefix = min_prefix_for_hosts(required_hosts, family, **kwargs)
    return ipaddress.ip_network(f"{base}/{prefix}")


# ---------------------------------------------------------------------------
# Details
# ---------------------------------------------------------------------------

def wildcard_mask(network: IPNetworkType) -> str:
    if network.version != 4:
        raise SubnetCalculationError("Wildcard masks apply to IPv4 only", field="family")
    return str(ipaddress.IPv4Address(int(network.netmask) ^ 0xFFFFFFFF))


def address_class(network: IPNetworkType) -> AddressClass | None:
    """Informational IPv4 class (metadata only, not used for allocation)."""
    if network.version != 4:
        return None
    first_octet = int(str(network.network_address).split(".")[0])
    if first_octet <= 127:
        return "A"
    if first_octet <= 191:
        return "B"
    if first_octet <= 223:
        return "C"
    if first_octet <= 239:
        return "D"
    return "E"


def address_scope(network: IPNetworkType) -> str:
    """Classification of the network's address space."""
    probe = network.network_address
    if probe.is_multicast:
        return "multicast"
    if probe.is_loopback:
        return "loopback"
    if probe.is_link_local:
        return "link-local"
    if probe.is_unspecified:
        return "unspecified"
    if probe.is_private:
        return "private"
    if probe.is_reserved:
        return "reserved"
    if network.version == 6 and probe.is_site_local:
        return "site-local"
    if getattr(probe, "is_global", not probe.is_private):
        return "global"
    return "other"


def subnet_details(network: IPNetworkType) -> dict[str, Any]:
    """Full, human-readable properties of a subnet, IPv4 or IPv6.

    IPv4-specific fields (broadcast, wildcard, dotted mask) are omitted for IPv6
    instead of being faked.
    """
    total = network.num_addresses
    first = network.network_address
    last = network.broadcast_address

    details: dict[str, Any] = {
        "network": str(network),
        "network_address": str(network.network_address),
        "prefix_length": network.prefixlen,
        "family": network.version,
        "total_addresses": total,
        "address_scope": address_scope(network),
        "address_class": address_class(network),
    }

    if network.version == 4:
        usable = ipv4_usable_hosts(network.prefixlen)
        if network.prefixlen == 32:
            first_host, last_host = first, first
        elif network.prefixlen == 31:
            first_host, last_host = first, last
        else:
            first_host, last_host = first + 1, last - 1
        details.update(
            {
                "subnet_mask": str(network.netmask),
                "wildcard_mask": wildcard_mask(network),
                "broadcast_address": str(last),
                "first_usable": str(first_host),
                "last_usable": str(last_host),
                "usable_hosts": usable,
                "usable_policy": (
                    "host-route" if network.prefixlen == 32
                    else "point-to-point" if network.prefixlen == 31
                    else "conventional"
                ),
                "address_range": f"{first}-{last}",
            }
        )
        if network.prefixlen not in (31, 32) and usable == 0:
            details["usable_hosts"] = 0
    else:
        # IPv6: no broadcast address and no universally fixed usable-host count.
        if network.prefixlen == 128:
            first_host, last_host = first, first
        elif network.prefixlen == 127:
            first_host, last_host = first, last
        else:
            first_host, last_host = first + 1, last
        details.update(
            {
                "first_usable": str(first_host),
                "last_usable": str(last_host),
                "usable_hosts": None,  # intentionally unset: see module docstring
                "usable_policy": "ipv6-total",
                "address_range": f"{first}-{last}",
                "note": (
                    "IPv6 subnets have no broadcast address and no fixed usable-host count; "
                    "the first address of a subnet is often the subnet-router anycast address."
                ),
            }
        )
    return details


# ---------------------------------------------------------------------------
# Structural checks (containment / alignment / overlap)
# ---------------------------------------------------------------------------

def is_contained(child: IPNetworkType, parent: IPNetworkType) -> bool:
    if child.version != parent.version:
        return False
    return child.subnet_of(parent)


def is_aligned(network: IPNetworkType) -> bool:
    """True when the network starts on a valid boundary for its prefix length."""
    block = 1 << (network.max_prefixlen - network.prefixlen)
    return int(network.network_address) % block == 0


def networks_overlap(a: IPNetworkType, b: IPNetworkType) -> bool:
    if a.version != b.version:
        return False
    return a.overlaps(b)


def check_no_overlaps(networks: list[IPNetworkType]) -> None:
    ordered = sorted(networks, key=lambda n: (n.version, int(n.network_address), n.prefixlen))
    for prev, cur in zip(ordered, ordered[1:]):
        if networks_overlap(prev, cur):
            raise ValueError(f"Overlapping networks: {prev} and {cur}")


# ---------------------------------------------------------------------------
# Calculator / split / summarize
# ---------------------------------------------------------------------------

def calculate(
    value: str,
    family: int | None = None,
    hosts: int | None = None,
    prefix_length: int | None = None,
) -> dict[str, Any]:
    """Single-entry calculator used by ``POST /calculator/subnet``.

    ``value`` may be a full CIDR, a bare address (``/32`` or ``/128`` assumed)
    or a prefix length alone together with ``family``.
    """
    warnings: list[str] = []
    text = (value or "").strip()

    if text.isdigit():
        # bare prefix length like "24"
        fam = family or 4
        max_len = 32 if fam == 4 else 128
        plen = int(text)
        if not 0 <= plen <= max_len:
            raise SubnetCalculationError(
                f"IPv{fam} prefix length must be 0..{max_len}, got {plen}", field="prefix"
            )
        base = "0.0.0.0" if fam == 4 else "::"
        net = ipaddress.ip_network(f"{base}/{plen}")
    elif "/" not in text:
        addr = parse_address(text, family=family)
        net = ipaddress.ip_network(f"{addr}/{addr.max_prefixlen}")
        warnings.append(
            f"'{text}' is a single address; interpreted as a host route {net}"
        )
    else:
        net = parse_network(text, family=family)
        if not is_normalized(text, family=family):
            warnings.append(
                f"Input '{text}' had host bits set; normalized to network address {net}"
            )

    result: dict[str, Any] = subnet_details(net)
    result["warnings"] = warnings

    if hosts is not None:
        prefix = min_prefix_for_hosts(hosts, net.version)
        template = network_for_hosts(hosts, net.version)
        result["requested_hosts"] = hosts
        result["required_prefix_length"] = prefix
        result["required_subnet_mask"] = (
            str(template.netmask) if net.version == 4 else None
        )
        result["subnets_available"] = 1 << (prefix - net.prefixlen) if prefix >= net.prefixlen else 0
        if prefix < net.prefixlen:
            result["warnings"].append(
                f"A /{net.prefixlen} network cannot provide {hosts} usable hosts"
            )

    if prefix_length is not None:
        max_len = net.max_prefixlen
        if not 0 <= prefix_length <= max_len:
            raise SubnetCalculationError(
                f"Prefix length must be 0..{max_len} for IPv{net.version}, got {prefix_length}",
                field="prefix_length",
            )
        result["requested_prefix_length"] = prefix_length
        result["requested_network"] = str(
            ipaddress.ip_network(("0.0.0.0" if net.version == 4 else "::") + f"/{prefix_length}")
        )
    return result


def split_network(parent: IPNetworkType, count: int | None = None, prefix_length: int | None = None) -> list[dict[str, Any]]:
    """Split ``parent`` into ``count`` equal subnets, or into all subnets of ``prefix_length``."""
    if prefix_length is not None:
        target = prefix_length
        if target < parent.prefixlen:
            raise SubnetCalculationError(
                f"/{target} is larger than the parent /{parent.prefixlen}", field="prefix_length"
            )
        if target > parent.max_prefixlen:
            raise SubnetCalculationError(
                f"Prefix length /{target} is invalid for IPv{parent.version}",
                field="prefix_length",
            )
        return [subnet_details(sub) for sub in parent.subnets(new_prefix=target)]

    if count is None:
        raise SubnetCalculationError("Either count or prefix_length must be supplied")
    if count < 2:
        raise SubnetCalculationError("count must be at least 2", field="count")
    if count > parent.num_addresses:
        raise SubnetCalculationError(
            f"Cannot split {parent} into {count} subnets: only "
            f"{parent.num_addresses} addresses are available",
            field="count",
        )
    new_prefix = min(
        parent.prefixlen + math.ceil(math.log2(count)),
        parent.max_prefixlen,
    )
    subnets = list(parent.subnets(new_prefix=new_prefix))
    if len(subnets) < count:
        raise SubnetCalculationError(
            f"Cannot split {parent} into {count} equal subnets", field="count"
        )
    return [subnet_details(sub) for sub in subnets[:count]]


def summarize_networks(values: list[str], family: int | None = None) -> dict[str, Any]:
    """Collapse a list of CIDRs into the smallest covering set of networks."""
    networks: list[IPNetworkType] = []
    errors: list[dict[str, Any]] = []
    for i, value in enumerate(values):
        try:
            networks.append(parse_network(value, family=family))
        except SubnetCalculationError as exc:
            errors.append({"field": f"networks[{i}]", "message": exc.message})
    if errors:
        exc = SubnetCalculationError("One or more networks are invalid", field="networks")
        exc.details = errors  # type: ignore[attr-defined]
        raise exc
    collapsed = list(ipaddress.collapse_addresses(networks))
    return {
        "input_count": len(networks),
        "summarized": [subnet_details(n) for n in collapsed],
        "summarized_count": len(collapsed),
        "total_addresses": sum(n.num_addresses for n in collapsed),
    }


def remaining_ranges(base: IPNetworkType, allocated: list[IPNetworkType]) -> list[dict[str, Any]]:
    """Free address ranges of ``base`` not covered by ``allocated`` subnets."""
    base_start = int(base.network_address)
    base_end = int(base.broadcast_address)
    blocks = sorted(allocated, key=lambda n: int(n.network_address))
    ranges: list[tuple[int, int]] = []
    cursor = base_start
    for block in blocks:
        start = int(block.network_address)
        end = int(block.broadcast_address)
        if start > base_end:
            continue
        if start > cursor:
            ranges.append((cursor, start - 1))
        cursor = max(cursor, end + 1)
        if cursor > base_end:
            break
    if cursor <= base_end:
        ranges.append((cursor, base_end))

    addr_cls = ipaddress.IPv4Address if base.version == 4 else ipaddress.IPv6Address
    out: list[dict[str, Any]] = []
    for start, end in ranges:
        first_addr, last_addr = addr_cls(start), addr_cls(end)
        cidrs = list(ipaddress.summarize_address_range(first_addr, last_addr))
        out.append(
            {
                "start": str(first_addr),
                "end": str(last_addr),
                "total_addresses": end - start + 1,
                "cidrs": [str(c) for c in cidrs],
                "usable_hosts": sum(usable_capacity(c) for c in cidrs),
            }
        )
    return out
