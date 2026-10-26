"""Independent test vectors and a bit-math reference for the subnet calculator.

M2-AC-009 / M2-AC-010 (`MILESTONES.md`) require expected values pinned to known
test vectors and, where appropriate, an independent reference implementation —
the calculator itself builds on Python's `ipaddress` module, so asserting against
`ipaddress` alone would only make an implementation agree with itself. This
module, therefore, does its own binary arithmetic (integer shifts/masks, no
`ipaddress`) and asserts the calculator against it.

Run with: `pytest tests/test_calculator_vectors.py -v`
(documented equivalent of the roadmap's `backend/tests/unit/test_subnet_calculator.py`
path: the repository keeps tests flat under `backend/tests/`).
"""

import pytest

from app.services.subnet_calculator import (
    min_prefix_for_hosts,
    networks_overlap,
    parse_network,
    subnet_details,
)

# ---------------------------------------------------------------------------
# Independent bit-math reference (pure integer arithmetic — no ipaddress import)
# ---------------------------------------------------------------------------


def _addr_to_int4(dotted: str) -> int:
    """IPv4 dotted-decimal → unsigned 32-bit int, hand-rolled."""
    parts = dotted.split(".")
    if len(parts) != 4:
        raise ValueError(dotted)
    return sum(int(p) << (24 - 8 * i) for i, p in enumerate(parts))


def _int4_to_addr(v: int) -> str:
    return ".".join(str((v >> (24 - 8 * i)) & 0xFF) for i in range(4))


def _mask4(prefix: int) -> int:
    return (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF


def _addr_to_int6(hext: str) -> int:
    """IPv6 (compressed or expanded) → unsigned 128-bit int, hand-rolled."""
    value = 0
    if "::" in hext:
        left, right = hext.split("::", 1)
        left_groups = [int(g, 16) for g in left.split(":")] if left else []
        right_groups = [int(g, 16) for g in right.split(":")] if right else []
        missing = 8 - len(left_groups) - len(right_groups)
        if missing < 1 or "::" in right:  # only one "::" allowed per address
            raise ValueError(hext)
        groups = left_groups + [0] * missing + right_groups
    else:
        groups = [int(g, 16) for g in hext.split(":")]
    if len(groups) != 8:
        raise ValueError(hext)
    for g in groups:
        if not 0 <= g <= 0xFFFF:
            raise ValueError(hext)
        value = (value << 16) | g
    return value


def reference_details(cidr: str, family: int) -> dict[str, object]:
    """Compute the same properties via plain bit arithmetic."""
    text, _, prefix_text = cidr.partition("/")
    prefix = int(prefix_text)
    if family == 4:
        addr = _addr_to_int4(text)
        mask = _mask4(prefix)
        net = addr & mask
        broadcast = net | (~mask & 0xFFFFFFFF)
        total = 1 << (32 - prefix)
        out: dict[str, object] = {
            "network_address": _int4_to_addr(net),
            "subnet_mask": _int4_to_addr(mask),
            "broadcast_address": _int4_to_addr(broadcast),
            "total_addresses": total,
            "prefix_length": prefix,
        }
        if prefix == 32:
            first_h = last_h = net
        elif prefix == 31:
            first_h, last_h = net, broadcast
        else:
            first_h, last_h = net + 1, broadcast - 1
        out["first_usable"] = _int4_to_addr(first_h)
        out["last_usable"] = _int4_to_addr(last_h)
        out["usable_hosts"] = total if prefix in (31, 32) else max(total - 2, 0)
        return out
    addr = _addr_to_int6(text)
    netmask = ((1 << prefix) - 1) << (128 - prefix)
    net = addr & netmask
    last = net | ((1 << (128 - prefix)) - 1)
    total = 1 << (128 - prefix)
    if prefix == 128:
        first_h = last_h = net
    elif prefix == 127:
        first_h, last_h = net, last
    else:
        first_h, last_h = net + 1, last
    return {
        "network_address": _addr_to_int6_string(net),
        "total_addresses": total,
        "prefix_length": prefix,
        "first_usable": _addr_to_int6_string(first_h),
        "last_usable": _addr_to_int6_string(last_h),
        "usable_hosts": None,
    }


def _addr_to_int6_string(v: int) -> str:
    return ":".join(f"{(v >> ((7 - i) * 16)) & 0xFFFF:04x}" for i in range(8))


# ---------------------------------------------------------------------------
# Known vectors: hardcoded expected values, cross-checked against the reference
# ---------------------------------------------------------------------------

VECTORS_V4 = [
    # cidr, network, mask, broadcast, first_usable, last_usable, total, usable
    ("192.168.10.0/24", "192.168.10.0", "255.255.255.0", "192.168.10.255", "192.168.10.1", "192.168.10.254", 256, 254),
    ("10.1.2.3/31", "10.1.2.2", "255.255.255.254", "10.1.2.3", "10.1.2.2", "10.1.2.3", 2, 2),
    ("172.16.0.9/32", "172.16.0.9", "255.255.255.255", "172.16.0.9", "172.16.0.9", "172.16.0.9", 1, 1),
    ("203.0.113.128/26", "203.0.113.128", "255.255.255.192", "203.0.113.191", "203.0.113.129", "203.0.113.190", 64, 62),
    ("0.0.0.0/0", "0.0.0.0", "0.0.0.0", "255.255.255.255", "0.0.0.1", "255.255.255.254", 2**32, 2**32 - 2),
]

VECTORS_V6 = [
    # cidr, network, first_usable, last_usable, total
    ("2001:db8::/64", "2001:db8:0000:0000:0000:0000:0000:0000", "2001:db8:0000:0000:0000:0000:0000:0001", "2001:db8:0000:0000:ffff:ffff:ffff:ffff", 2**64),
    ("2001:db8::0/127", "2001:db8:0000:0000:0000:0000:0000:0000", "2001:db8:0000:0000:0000:0000:0000:0000", "2001:db8:0000:0000:0000:0000:0000:0001", 2),
    ("2001:db8::1/128", "2001:db8:0000:0000:0000:0000:0000:0001", "2001:db8:0000:0000:0000:0000:0000:0001", "2001:db8:0000:0000:0000:0000:0000:0001", 1),
]


# Addresses are compared as parsed binary values, since the engine returns
# compressed IPv6 strings and this reference returns the expanded form.
def _v6(text: str) -> int:
    return _addr_to_int6(text)


@pytest.mark.parametrize(
    "cidr,network,mask,broadcast,first,last,total,usable",
    VECTORS_V4,
    ids=[v[0] for v in VECTORS_V4],
)
def test_ipv4_vector(cidr, network, mask, broadcast, first, last, total, usable) -> None:
    d = subnet_details(parse_network(cidr))
    ref = reference_details(cidr, 4)
    assert d["network_address"] == network == ref["network_address"]
    assert d["subnet_mask"] == mask == ref["subnet_mask"]
    assert d["broadcast_address"] == broadcast == ref["broadcast_address"]
    assert d["first_usable"] == first == ref["first_usable"]
    assert d["last_usable"] == last == ref["last_usable"]
    assert d["total_addresses"] == total == ref["total_addresses"]
    assert d["usable_hosts"] == usable == ref["usable_hosts"]
    assert d["prefix_length"] == int(cidr.split("/")[1])


@pytest.mark.parametrize(
    "cidr,network,first,last,total", VECTORS_V6, ids=[v[0] for v in VECTORS_V6]
)
def test_ipv6_vector(cidr, network, first, last, total) -> None:
    d = subnet_details(parse_network(cidr))
    ref = reference_details(cidr, 6)
    assert int(d["total_addresses"]) == total == int(ref["total_addresses"])  # type: ignore[arg-type]
    assert _v6(d["network_address"]) == _v6(network) == _v6(str(ref["network_address"]))
    assert _v6(d["first_usable"]) == _v6(first) == _v6(str(ref["first_usable"]))
    assert _v6(d["last_usable"]) == _v6(last) == _v6(str(ref["last_usable"]))
    assert ref["usable_hosts"] is None and d["usable_hosts"] is None
    assert "broadcast_address" not in d and "wildcard_mask" not in d


# ---------------------------------------------------------------------------
# Boundary behavior (M2-AC-003/004/007): /31, /32, /127, /128, /0 — without
# overflow or impractical enumeration
# ---------------------------------------------------------------------------


def test_ipv4_slash0_boundary() -> None:
    d = subnet_details(parse_network("0.0.0.0/0"))
    assert d["total_addresses"] == 2**32
    assert d["broadcast_address"] == "255.255.255.255"
    assert d["first_usable"] == "0.0.0.1" and d["last_usable"] == "255.255.255.254"
    assert d["usable_hosts"] == 2**32 - 2


def test_ipv6_slash0_boundary() -> None:
    d = subnet_details(parse_network("::/0"))
    assert d["total_addresses"] == 2**128  # arbitrary-precision int; no overflow
    assert d["usable_hosts"] is None
    assert "broadcast_address" not in d


def test_slash127_point_to_point() -> None:
    """M2-AC-004: IPv6 /127 behaves as point-to-point — both addresses usable."""
    d = subnet_details(parse_network("2001:db8::2/127"))
    assert d["total_addresses"] == 2
    assert d["first_usable"] == "2001:db8::2"
    assert d["last_usable"] == "2001:db8::3"


def test_min_prefix_ipv6_point_to_point() -> None:
    # IPv6 capacity policy: 2 hosts fit in /127, 1 address in /128
    assert min_prefix_for_hosts(2, 6) == 127
    assert min_prefix_for_hosts(1, 6) == 128


def test_min_prefix_v4_specials_never_selected_by_default() -> None:
    # conventional LAN selection must never pick /31 or /32
    assert min_prefix_for_hosts(2, 4) == 30
    assert min_prefix_for_hosts(1, 4) == 30
    assert min_prefix_for_hosts(2, 4, allow_point_to_point=True) == 31
    assert min_prefix_for_hosts(1, 4, allow_host_route=True) == 32


def test_overlap_misaligned_crosscheck() -> None:
    """M2-AC-006: containment/overlap checked against reference arithmetic."""
    a = parse_network("10.0.0.0/28")
    assert not networks_overlap(a, parse_network("10.0.0.16/28"))
    assert networks_overlap(a, parse_network("10.0.0.8/29"))
    # reference cross-check via integer ranges of the same networks
    for x, y, expected in [(a, parse_network("10.0.0.16/28"), False),
                           (a, parse_network("10.0.0.8/29"), True)]:
        xs, xe = int(x.network_address), int(x.broadcast_address)
        ys, ye = int(y.network_address), int(y.broadcast_address)
        assert (xs <= ye and ys <= xe) == expected
