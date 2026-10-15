"""Unit tests for app.services.subnet_calculator."""

from __future__ import annotations

import ipaddress

import pytest

from app.services.subnet_calculator import (
    SubnetCalculationError,
    calculate,
    ipv4_usable_hosts,
    is_aligned,
    is_contained,
    min_prefix_for_hosts,
    networks_overlap,
    normalize_cidr,
    parse_network,
    remaining_ranges,
    split_network,
    subnet_details,
    summarize_networks,
    wildcard_mask,
)

# --- parsing / validation --------------------------------------------------

def test_parse_valid_cidr() -> None:
    assert str(parse_network("192.168.10.0/24")) == "192.168.10.0/24"


def test_parse_normalizes_host_bits() -> None:
    assert str(parse_network("192.168.10.5/24")) == "192.168.10.0/24"


@pytest.mark.parametrize("bad", ["", "   ", "192.168.1.0", "abc", "192.168.1.0/33", "10.0.0.0/24/8", "::/129"])
def test_parse_rejects_malformed(bad: str) -> None:
    with pytest.raises(SubnetCalculationError):
        parse_network(bad)


def test_family_mismatch_rejected() -> None:
    with pytest.raises(SubnetCalculationError):
        parse_network("2001:db8::/64", family=4)
    with pytest.raises(SubnetCalculationError):
        parse_network("10.0.0.0/8", family=6)


def test_normalize_cidr() -> None:
    assert normalize_cidr("10.1.2.3/8") == "10.0.0.0/8"


# --- IPv4 details ----------------------------------------------------------

def test_ipv4_slash24_details() -> None:
    d = subnet_details(parse_network("192.168.10.0/24"))
    assert d["subnet_mask"] == "255.255.255.0"
    assert d["wildcard_mask"] == "0.0.0.255"
    assert d["broadcast_address"] == "192.168.10.255"
    assert d["first_usable"] == "192.168.10.1"
    assert d["last_usable"] == "192.168.10.254"
    assert d["total_addresses"] == 256
    assert d["usable_hosts"] == 254
    assert d["address_class"] == "C"
    assert d["address_scope"] == "private"


def test_ipv4_public_scope() -> None:
    d = subnet_details(parse_network("8.8.8.0/24"))
    assert d["address_scope"] == "global"
    assert d["address_class"] == "A"


def test_ipv4_loopback_and_multicast_scope() -> None:
    assert subnet_details(parse_network("127.0.0.0/8"))["address_scope"] == "loopback"
    assert subnet_details(parse_network("224.0.0.0/4"))["address_scope"] == "multicast"


def test_slash31_point_to_point() -> None:
    d = subnet_details(parse_network("10.0.0.0/31"))
    assert d["usable_hosts"] == 2  # RFC 3021
    assert d["first_usable"] == "10.0.0.0"
    assert d["last_usable"] == "10.0.0.1"
    assert d["usable_policy"] == "point-to-point"


def test_slash32_host_route() -> None:
    d = subnet_details(parse_network("10.0.0.1/32"))
    assert d["usable_hosts"] == 1
    assert d["first_usable"] == "10.0.0.1"
    assert d["last_usable"] == "10.0.0.1"
    assert d["broadcast_address"] == "10.0.0.1"
    assert d["usable_policy"] == "host-route"


def test_wildcard_mask() -> None:
    assert wildcard_mask(parse_network("10.0.0.0/27")) == "0.0.0.31"
    assert wildcard_mask(parse_network("10.0.0.0/24")) == "0.0.0.255"


def test_wildcard_rejects_ipv6() -> None:
    with pytest.raises(SubnetCalculationError):
        wildcard_mask(parse_network("2001:db8::/64"))


# --- IPv6 details ----------------------------------------------------------

def test_ipv6_details_have_no_broadcast() -> None:
    d = subnet_details(parse_network("2001:db8::/64"))
    assert "broadcast_address" not in d
    assert "wildcard_mask" not in d
    assert d["total_addresses"] == 2**64
    assert d["usable_hosts"] is None  # no fixed usable-host count for IPv6
    assert d["first_usable"] == "2001:db8::1"
    assert d["note"]


def test_ipv6_slash128() -> None:
    d = subnet_details(parse_network("2001:db8::1/128"))
    assert d["total_addresses"] == 1
    assert d["first_usable"] == d["last_usable"] == "2001:db8::1"


# --- prefix selection ------------------------------------------------------

@pytest.mark.parametrize(
    "hosts,prefix",
    [(1, 30), (2, 30), (6, 29), (14, 28), (15, 27), (25, 27), (26, 27), (30, 27),
     (31, 26), (50, 26), (62, 26), (63, 25), (100, 25), (254, 24), (255, 23)],
)
def test_min_prefix_conventional_lan(hosts: int, prefix: int) -> None:
    assert min_prefix_for_hosts(hosts, 4) == prefix


def test_min_prefix_point_to_point_opt_in() -> None:
    assert min_prefix_for_hosts(1, 4, allow_point_to_point=True) == 31
    assert min_prefix_for_hosts(2, 4, allow_point_to_point=True) == 31
    assert min_prefix_for_hosts(3, 4, allow_point_to_point=True) == 29  # /30 only fits 2 usable


def test_min_prefix_host_route_opt_in() -> None:
    assert min_prefix_for_hosts(1, 4, allow_host_route=True) == 32


def test_min_prefix_ipv6() -> None:
    assert min_prefix_for_hosts(1, 6) == 128
    assert min_prefix_for_hosts(2, 6) == 127
    assert min_prefix_for_hosts(1000, 6) == 118
    assert min_prefix_for_hosts(2**16, 6) == 112


def test_min_prefix_rejects_zero_hosts() -> None:
    with pytest.raises(SubnetCalculationError):
        min_prefix_for_hosts(0, 4)


# --- structural checks -----------------------------------------------------

def test_alignment_and_containment() -> None:
    parent = parse_network("10.0.0.0/16")
    good = parse_network("10.0.1.0/24")
    assert is_aligned(good)
    assert is_contained(good, parent)
    # a network object built from a raw (address, prefix) pair can be misaligned
    # build a deliberately misaligned network object (strict construction rejects it)
    misaligned = ipaddress.ip_network("10.0.1.0/23", strict=False)
    misaligned.network_address = ipaddress.ip_address("10.0.1.128")
    assert not is_aligned(misaligned)
    outside = parse_network("10.2.0.0/16")
    assert not is_contained(outside, parent)


def test_overlap_detection() -> None:
    a = parse_network("192.168.1.0/25")
    b = parse_network("192.168.1.128/25")
    c = parse_network("192.168.1.64/26")
    assert not networks_overlap(a, b)
    assert networks_overlap(a, c)


# --- calculate / split / summarize -----------------------------------------

def test_calculate_with_hosts_requirement() -> None:
    result = calculate("192.168.10.0/24", hosts=50)
    assert result["required_prefix_length"] == 26
    assert result["required_subnet_mask"] == "255.255.255.192"
    assert result["subnets_available"] == 4


def test_calculate_warns_on_normalization() -> None:
    result = calculate("192.168.10.5/24")
    assert result["network"] == "192.168.10.0/24"
    assert any("host bits" in w for w in result["warnings"])


def test_calculate_bare_address() -> None:
    result = calculate("10.0.0.5")
    assert result["network"] == "10.0.0.5/32"
    assert any("host route" in w for w in result["warnings"])


def test_calculate_bare_prefix() -> None:
    result = calculate("26", family=4)
    assert result["network"] == "0.0.0.0/26"


def test_split_by_count() -> None:
    subnets = split_network(parse_network("10.0.0.0/24"), count=4)
    assert [s["network"] for s in subnets] == ["10.0.0.0/26", "10.0.0.64/26", "10.0.0.128/26", "10.0.0.192/26"]


def test_split_non_power_of_two() -> None:
    subnets = split_network(parse_network("10.0.0.0/24"), count=3)
    assert len(subnets) == 3  # splits into 4, returns the requested 3


def test_split_by_prefix() -> None:
    subnets = split_network(parse_network("10.0.0.0/24"), prefix_length=28)
    assert len(subnets) == 16


def test_split_rejects_invalid_count() -> None:
    with pytest.raises(SubnetCalculationError):
        split_network(parse_network("10.0.0.0/30"), count=100)


def test_summarize_collapses_adjacent() -> None:
    result = summarize_networks(["192.168.1.0/25", "192.168.1.128/25"])
    assert [s["network"] for s in result["summarized"]] == ["192.168.1.0/24"]


def test_summarize_reports_invalid_entries() -> None:
    with pytest.raises(SubnetCalculationError) as exc:
        summarize_networks(["192.168.1.0/25", "not-a-network"])
    assert exc.value.details


# --- remaining ranges ------------------------------------------------------

def test_remaining_ranges_after_vlsm_layout() -> None:
    base = parse_network("192.168.10.0/24")
    allocated = [
        parse_network("192.168.10.0/26"),
        parse_network("192.168.10.64/27"),
        parse_network("192.168.10.96/27"),
        parse_network("192.168.10.128/28"),
        parse_network("192.168.10.144/28"),
    ]
    ranges = remaining_ranges(base, allocated)
    assert len(ranges) == 1
    assert ranges[0]["start"] == "192.168.10.160"
    assert ranges[0]["end"] == "192.168.10.255"
    assert ranges[0]["total_addresses"] == 96


def test_remaining_ranges_multiple_gaps() -> None:
    base = parse_network("10.0.0.0/24")
    allocated = [parse_network("10.0.0.32/28"), parse_network("10.0.0.96/28")]
    ranges = remaining_ranges(base, allocated)
    assert [r["total_addresses"] for r in ranges] == [32, 48, 144]


def test_remaining_ranges_none_left() -> None:
    base = parse_network("10.0.0.0/25")
    allocated = [parse_network("10.0.0.0/26"), parse_network("10.0.0.64/26")]
    assert remaining_ranges(base, allocated) == []


def test_usable_capacity_policy() -> None:
    assert ipv4_usable_hosts(24) == 254
    assert ipv4_usable_hosts(31) == 2
    assert ipv4_usable_hosts(32) == 1
