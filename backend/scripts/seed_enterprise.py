"""Seed the NetSpace IPAM database with a realistic enterprise topology.

Models a mid-size multi-site company ("Aurora Dynamics"): HQ campus, private
datacenter, three operating branches, one branch in rollout, DMZ, wireless,
voice, building-security and lab networks — with VLANs, gateways, tracked
device IPs, departments and allocation plans (draft / active / archived).

Everything goes through the real service layer, so containment / alignment /
overlap validation, computed details and the audit trail behave exactly as
with data entered through the UI.

Usage:
    cd backend
    .venv/bin/python scripts/seed_enterprise.py           # backup + reset + seed
    .venv/Scripts/python.exe scripts/seed_enterprise.py   # Windows venv

A timestamped copy of the SQLite file is saved next to it before the reset
(only for sqlite databases; skipped for :memory:).
"""

from __future__ import annotations

import argparse
import random
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.db.session import SessionLocal, engine  # noqa: E402
from app.services import ipam_service  # noqa: E402

NOW = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC, matches DB storage
SEED = 20261016  # deterministic backdating

# ----------------------------------------------------------------------- #
# Departments (reusable planning defaults per org unit / site)             #
# ----------------------------------------------------------------------- #
DEPARTMENTS = [
    ("Executive Office", 12, 15, "London HQ", "Directors and EA pool"),
    ("Information Technology", 85, 20, "London HQ", "Platform, network and service desk teams"),
    ("Finance", 45, 30, "London HQ", "Finance, payroll and procurement"),
    ("Human Resources", 30, 35, "London HQ", "HR and recruitment"),
    ("Sales", 120, 40, "London HQ", "Field and inside sales"),
    ("Marketing", 60, 45, "London HQ", "Brand, demand gen and events"),
    ("Research & Development", 140, 50, "London HQ", "Engineering and product teams"),
    ("Customer Support", 90, 55, "Manchester", "Tier 1/2 support desk"),
    ("Operations", 220, 60, "Manchester", "Manufacturing and operations floor"),
    ("Warehouse & Logistics", 150, 65, "Manchester", "Warehouse, fork-lift scanners, shipping"),
    ("Facilities & Maintenance", 35, 70, "London HQ", "Building services and maintenance techs"),
    ("Security", 25, 75, "London HQ", "Corporate security and reception"),
    ("Guest Services", 60, 900, "London HQ", "Visitor and contractor access"),
    ("Datacenter Platform Team", 40, 100, "London DC1", "Virtualisation, storage and backup"),
]

# ----------------------------------------------------------------------- #
# Networks (site summarised blocks, RFC1918)                               #
# ----------------------------------------------------------------------- #
NETWORKS = [
    # name, cidr, environment, site, status, description
    ("HQ Campus — LAN", "10.10.0.0/16", "production", "London HQ", "active",
     "Campus user, voice, WiFi, server and IoT addressing for the London head office"),
    ("DC1 — Compute", "10.20.0.0/16", "production", "London DC1", "active",
     "Production datacenter: compute, storage, management and backup networks"),
    ("Branch — Manchester", "10.31.0.0/16", "production", "Manchester", "active",
     "Manchester site: users, voice, WiFi and local IT"),
    ("Branch — Leeds", "10.32.0.0/16", "production", "Leeds", "active",
     "Leeds site: users, voice, WiFi and local IT"),
    ("Branch — Glasgow", "10.33.0.0/16", "production", "Glasgow", "active",
     "Glasgow site: users, voice, WiFi and local IT"),
    ("Branch — Nottingham (planned)", "10.36.0.0/24", "production", "Nottingham", "planned",
     "Reserved block for the Nottingham office opening (Q3 fit-out)"),
    ("Perimeter DMZ", "172.16.0.0/24", "production", "London DC1", "active",
     "Public-facing services behind the edge firewalls"),
    ("Corporate Wireless", "10.40.0.0/22", "production", "Multi-site", "active",
     "WLAN controllers and guest internet tunnel"),
    ("Voice & Unified Communications", "10.50.0.0/25", "production", "Multi-site", "active",
     "CUCM, SIP edge and handset DHCP pools — fully carved, renewal under review"),
    ("Security & Building Systems", "10.60.0.0/24", "production", "London HQ", "active",
     "CCTV, access control and building automation"),
    ("Lab & Development", "10.99.0.0/16", "lab", "London HQ", "active",
     "Non-production lab space: test beds, staging hardware, training kit"),
]

# ----------------------------------------------------------------------- #
# Subnets per network (VLAN plan follows the 10/20/30… site convention)   #
# ----------------------------------------------------------------------- #
SUBNETS: dict[str, list[tuple]] = {
    # network name -> (subnet name, cidr, vlan, gateway, status, description)
    "HQ Campus — LAN": [
        ("HQ-Users", "10.10.0.0/22", 10, "10.10.0.1", "allocated", "Wired access switches, floors 1-4"),
        ("HQ-Voice", "10.10.4.0/24", 20, "10.10.4.1", "allocated", "IP phones (SCCP/SIP)"),
        ("HQ-WiFi-Corp", "10.10.5.0/24", 30, "10.10.5.1", "allocated", "Corporate SSID, 802.1X"),
        ("HQ-IT-Services", "10.10.10.0/24", 110, "10.10.10.1", "allocated", "IT out-of-band mgmt, test bench"),
        ("HQ-Servers", "10.10.20.0/23", 120, "10.10.20.1", "allocated", "On-prem application and file services"),
        ("HQ-IoT", "10.10.30.0/24", 130, "10.10.30.1", "allocated", "BMS, HVAC and metering"),
        ("HQ-Guest", "10.10.99.0/24", 999, "10.10.99.1", "reserved", "Internet-only guest access, no internal routing"),
        ("HQ-OOB-Management", "10.10.250.0/24", 1000, "10.10.250.1", "reserved", "Console servers, PDU and UPS management"),
    ],
    "DC1 — Compute": [
        ("DC1-Prod-Compute", "10.20.0.0/22", 200, "10.20.0.1", "allocated", "Production VM hosts and databases"),
        ("DC1-Staging", "10.20.4.0/24", 210, "10.20.4.1", "allocated", "Pre-production environment"),
        ("DC1-Dev", "10.20.5.0/24", 220, "10.20.5.1", "allocated", "Development environment"),
        ("DC1-Storage", "10.20.10.0/24", 230, "10.20.10.1", "allocated", "iSCSI / vMotion storage networks"),
        ("DC1-VM-Management", "10.20.20.0/24", 240, "10.20.20.1", "allocated", "Hypervisor management, IPMI/iDRAC"),
        ("DC1-Backup", "10.20.30.0/24", 260, "10.20.30.1", "allocated", "Backup media and repository network"),
        ("DC1-Cluster-Heartbeat", "10.20.250.0/29", 250, None, "reserved", "Non-routed cluster interconnect / heartbeat"),
    ],
    "Branch — Manchester": [
        ("MAN-Users", "10.31.0.0/23", 10, "10.31.0.1", "allocated", "Office and shop-floor wired access"),
        ("MAN-Voice", "10.31.2.0/24", 20, "10.31.2.1", "allocated", "IP phones"),
        ("MAN-WiFi", "10.31.3.0/24", 30, "10.31.3.1", "allocated", "Corporate + guest SSIDs"),
        ("MAN-IT", "10.31.10.0/24", 110, "10.31.10.1", "allocated", "Local server and switch management"),
    ],
    "Branch — Leeds": [
        ("LEEDS-Users", "10.32.0.0/23", 10, "10.32.0.1", "allocated", "Office wired access"),
        ("LEEDS-Voice", "10.32.2.0/24", 20, "10.32.2.1", "allocated", "IP phones"),
        ("LEEDS-WiFi", "10.32.3.0/24", 30, "10.32.3.1", "allocated", "Corporate SSID"),
        ("LEEDS-IT", "10.32.10.0/24", 110, "10.32.10.1", "allocated", "Local switch management"),
        ("LEEDS-Legacy-CCTV", "10.32.50.0/26", 650, None, "released", "Decommissioned analogue CCTV head-end"),
    ],
    "Branch — Glasgow": [
        ("GLA-Users", "10.33.0.0/23", 10, "10.33.0.1", "allocated", "Office wired access"),
        ("GLA-Voice", "10.33.2.0/24", 20, "10.33.2.1", "allocated", "IP phones"),
        ("GLA-WiFi", "10.33.3.0/24", 30, "10.33.3.1", "allocated", "Corporate SSID"),
        ("GLA-IT", "10.33.10.0/24", 110, "10.33.10.1", "allocated", "Local switch management"),
    ],
    "Perimeter DMZ": [
        ("DMZ-Public-Services", "172.16.0.0/26", 501, "172.16.0.1", "allocated", "Mail edge, VPN termination, public web"),
        ("DMZ-Transit", "172.16.0.64/26", 502, None, "reserved", "Firewall transit links (edge <-> core)"),
    ],
    "Corporate Wireless": [
        ("WLAN-Controllers", "10.40.0.0/28", 410, "10.40.0.1", "allocated", "WLC management and APs"),
        ("WLAN-Guest-Tunnel", "10.40.1.0/24", 420, "10.40.1.1", "allocated", "Guest traffic tunnelled to internet breakout"),
    ],
    "Voice & Unified Communications": [
        ("UC-Servers", "10.50.0.0/26", 510, "10.50.0.1", "allocated", "CUCM, CUBE, voicemail"),
        ("UC-Handset-Pool", "10.50.0.64/26", 520, "10.50.0.65", "allocated", "Dynamic handset DHCP scope"),
    ],
    "Security & Building Systems": [
        ("SEC-CCTV", "10.60.0.0/26", 610, "10.60.0.1", "allocated", "IP cameras and NVR"),
        ("SEC-Access-Control", "10.60.0.64/26", 620, "10.60.0.65", "allocated", "Door controllers and badge readers"),
    ],
    "Lab & Development": [
        ("LAB-Networks", "10.99.0.0/22", 710, "10.99.0.1", "allocated", "Sandbox vLANs for PoCs and training"),
        ("LAB-Testbed", "10.99.100.0/24", 720, "10.99.100.1", "allocated", "Vendor interop test bench"),
    ],
}

# ----------------------------------------------------------------------- #
# Tracked IP addresses (gateways, servers, network gear, key endpoints)   #
# (subnet name, address, hostname, device, department, status, description) #
# ----------------------------------------------------------------------- #
DEPT = {
    "IT": "Information Technology",
    "DC": "Datacenter Platform Team",
    "OPS": "Operations",
    "FIN": "Finance",
    "SALES": "Sales",
    "FAC": "Facilities & Maintenance",
    "SEC": "Security",
    "CS": "Customer Support",
}

IPS: list[tuple] = [
    # -- HQ campus ------------------------------------------------------- #
    ("HQ-Users", "10.10.0.1", "gw-hq-users", "Core SW (SVI)", DEPT["IT"], "assigned", "Campus access layer gateway"),
    ("HQ-Users", "10.10.0.50", "ws-fin-014", "Dell OptiPlex", DEPT["FIN"], "assigned", "Finance desk 14"),
    ("HQ-Users", "10.10.0.88", "ws-sales-112", "Lenovo ThinkPad", DEPT["SALES"], "assigned", "Sales hot-desk"),
    ("HQ-Users", "10.10.0.200", None, None, None, "available", "DHCP dynamic pool — floors 1-2"),
    ("HQ-Voice", "10.10.4.1", "gw-hq-voice", "Core SW (SVI)", DEPT["IT"], "assigned", "Voice gateway"),
    ("HQ-Voice", "10.10.4.31", "sep00a1b2c3d4e5", "Cisco 8841 phone", DEPT["SEC"], "assigned", "Security desk handset"),
    ("HQ-WiFi-Corp", "10.10.5.1", "gw-hq-wifi", "WLC (SVI)", DEPT["IT"], "assigned", "WiFi gateway"),
    ("HQ-WiFi-Corp", "10.10.5.10", "ap-hq-lobby", "Aruba AP-515", DEPT["IT"], "assigned", "Lobby ceiling"),
    ("HQ-WiFi-Corp", "10.10.5.11", "ap-hq-floor2", "Aruba AP-515", DEPT["IT"], "assigned", "Floor 2 east"),
    ("HQ-WiFi-Corp", "10.10.5.12", "ap-hq-floor3", "Aruba AP-515", DEPT["IT"], "assigned", "Floor 3 west"),
    ("HQ-IT-Services", "10.10.10.1", "gw-hq-it", "Core SW (SVI)", DEPT["IT"], "assigned", "IT services gateway"),
    ("HQ-IT-Services", "10.10.10.10", "oob-console-01", "Opengear CM7196", DEPT["IT"], "assigned", "Out-of-band console server"),
    ("HQ-IT-Services", "10.10.10.20", "ups-nmc-01", "APC UPS NMC", DEPT["FAC"], "assigned", "Comms room UPS monitoring"),
    ("HQ-Servers", "10.10.20.1", "gw-hq-servers", "Core SW (SVI)", DEPT["IT"], "assigned", "Server farm gateway"),
    ("HQ-Servers", "10.10.20.10", "ad-dc01", "Windows Server 2022", DEPT["IT"], "assigned", "AD DS / DNS primary"),
    ("HQ-Servers", "10.10.20.11", "ad-dc02", "Windows Server 2022", DEPT["IT"], "assigned", "AD DS / DNS secondary"),
    ("HQ-Servers", "10.10.20.12", "dhcp-hq01", "Windows Server 2022", DEPT["IT"], "assigned", "DHCP failover member"),
    ("HQ-Servers", "10.10.20.20", "intranet01", "Ubuntu 24.04 LTS", DEPT["IT"], "assigned", "Staff intranet"),
    ("HQ-Servers", "10.10.20.30", "print-hq01", "Ricoh IM C6000", DEPT["FAC"], "assigned", "3rd floor MFD"),
    ("HQ-Servers", "10.10.20.100", None, None, None, "available", "Spare — application team request queue"),
    ("HQ-Servers", "10.10.20.250", "old-mail01", "Windows Server 2016", DEPT["IT"], "deprecated", "Decommissioned exchange hybrid host, pending wipe"),
    ("HQ-IoT", "10.10.30.1", "gw-hq-iot", "Core SW (SVI)", DEPT["FAC"], "assigned", "Building systems gateway"),
    ("HQ-IoT", "10.10.30.10", "bms-headend", "Tridium Niagara", DEPT["FAC"], "assigned", "BMS head end"),
    ("HQ-IoT", "10.10.30.11", "hvac-ahus-01", "AHU controller", DEPT["FAC"], "assigned", "Air handling units 1-4"),
    ("HQ-Guest", "10.10.99.1", "gw-hq-guest", "Firewall (SVI)", DEPT["IT"], "assigned", "Guest isolation gateway"),
    ("HQ-OOB-Management", "10.10.250.1", "gw-hq-oob", "OOB SW (SVI)", DEPT["IT"], "reserved", "Reserved for out-of-band fleet"),
    # -- Datacenter ------------------------------------------------------- #
    ("DC1-Prod-Compute", "10.20.0.1", "gw-dc1-prod", "Leaf SW (SVI)", DEPT["DC"], "assigned", "Prod compute gateway"),
    ("DC1-Prod-Compute", "10.20.0.10", "vcent01", "vCenter 8", DEPT["DC"], "assigned", "Virtualisation management"),
    ("DC1-Prod-Compute", "10.20.0.11", "esx01", "ESXi 8 host", DEPT["DC"], "assigned", "Rack A1"),
    ("DC1-Prod-Compute", "10.20.0.12", "esx02", "ESXi 8 host", DEPT["DC"], "assigned", "Rack A2"),
    ("DC1-Prod-Compute", "10.20.0.13", "esx03", "ESXi 8 host", DEPT["DC"], "assigned", "Rack B1"),
    ("DC1-Prod-Compute", "10.20.0.20", "sql-cluster-vip", "F5 virtual server", DEPT["DC"], "assigned", "SQL Always On listener"),
    ("DC1-Prod-Compute", "10.20.0.21", "sql-node01", "Windows Server 2022", DEPT["DC"], "assigned", "SQL node 1"),
    ("DC1-Prod-Compute", "10.20.0.22", "sql-node02", "Windows Server 2022", DEPT["DC"], "assigned", "SQL node 2"),
    ("DC1-Prod-Compute", "10.20.0.50", "backup01", "Veeam Repository", DEPT["DC"], "assigned", "Primary backup repository"),
    ("DC1-Prod-Compute", "10.20.0.180", None, None, None, "available", "Free — future ERP cluster"),
    ("DC1-Prod-Compute", "10.20.0.181", None, None, None, "available", "Free — future ERP cluster"),
    ("DC1-Staging", "10.20.4.1", "gw-dc1-stg", "Leaf SW (SVI)", DEPT["DC"], "assigned", "Staging gateway"),
    ("DC1-Staging", "10.20.4.20", "stg-app01", "Ubuntu 24.04 LTS", DEPT["DC"], "assigned", "Pre-prod app node"),
    ("DC1-Dev", "10.20.5.1", "gw-dc1-dev", "Leaf SW (SVI)", DEPT["DC"], "assigned", "Dev gateway"),
    ("DC1-Dev", "10.20.5.40", "dev-runner-01", "GitLab runner", DEPT["DC"], "assigned", "CI build agent"),
    ("DC1-Storage", "10.20.10.1", "gw-dc1-storage", "Leaf SW (SVI)", DEPT["DC"], "assigned", "Storage gateway"),
    ("DC1-Storage", "10.20.10.10", "san-a", "PowerStore A", DEPT["DC"], "assigned", "Primary array"),
    ("DC1-Storage", "10.20.10.11", "san-b", "PowerStore B", DEPT["DC"], "assigned", "Replica array"),
    ("DC1-VM-Management", "10.20.20.1", "gw-dc1-mgmt", "Leaf SW (SVI)", DEPT["DC"], "assigned", "Mgmt gateway"),
    ("DC1-VM-Management", "10.20.20.31", "idrac-esx01", "iDRAC 9", DEPT["DC"], "assigned", "Out-of-band host management"),
    ("DC1-Backup", "10.20.30.1", "gw-dc1-backup", "Leaf SW (SVI)", DEPT["DC"], "assigned", "Backup gateway"),
    # -- Manchester ------------------------------------------------------- #
    ("MAN-Users", "10.31.0.1", "gw-man-users", "Access SW (SVI)", DEPT["OPS"], "assigned", "Site gateway"),
    ("MAN-Users", "10.31.0.40", "ws-man-ops-07", "Zebra TC52 scanner dock", DEPT["OPS"], "assigned", "Line 2 scanning station"),
    ("MAN-Users", "10.31.0.90", "printer-man-01", "Zebra ZT411", DEPT["FAC"], "assigned", "Shipping label printer"),
    ("MAN-WiFi", "10.31.3.1", "gw-man-wifi", "WLC (SVI)", DEPT["IT"], "assigned", "Site WiFi gateway"),
    ("MAN-WiFi", "10.31.3.10", "ap-man-floor", "Aruba AP-505", DEPT["IT"], "assigned", "Warehouse floor"),
    ("MAN-IT", "10.31.10.1", "gw-man-it", "Access SW (SVI)", DEPT["IT"], "assigned", "Local IT gateway"),
    ("MAN-IT", "10.31.10.10", "sw-man-core01", "Catalyst 9300", DEPT["IT"], "assigned", "Site core switch"),
    # -- Leeds ------------------------------------------------------------ #
    ("LEEDS-Users", "10.32.0.1", "gw-leeds-users", "Access SW (SVI)", DEPT["CS"], "assigned", "Site gateway"),
    ("LEEDS-Users", "10.32.0.55", "ws-leeds-cs-03", "HP EliteDesk", DEPT["CS"], "assigned", "Support desk pod 3"),
    ("LEEDS-WiFi", "10.32.3.1", "gw-leeds-wifi", "WLC (SVI)", DEPT["IT"], "assigned", "Site WiFi gateway"),
    ("LEEDS-IT", "10.32.10.10", "sw-leeds-core01", "Catalyst 9200", DEPT["IT"], "assigned", "Site core switch"),
    # -- Glasgow ---------------------------------------------------------- #
    ("GLA-Users", "10.33.0.1", "gw-gla-users", "Access SW (SVI)", DEPT["CS"], "assigned", "Site gateway"),
    ("GLA-Users", "10.33.0.61", "ws-gla-cs-09", "HP EliteDesk", DEPT["CS"], "assigned", "Support desk pod 9"),
    ("GLA-WiFi", "10.33.3.10", "ap-gla-01", "Aruba AP-505", DEPT["IT"], "assigned", "Reception"),
    ("GLA-IT", "10.33.10.10", "sw-gla-core01", "Catalyst 9200", DEPT["IT"], "assigned", "Site core switch"),
    # -- DMZ -------------------------------------------------------------- #
    ("DMZ-Public-Services", "172.16.0.1", "ftg-dmz01", "FortiGate 200F", DEPT["IT"], "assigned", "DMZ interface"),
    ("DMZ-Public-Services", "172.16.0.10", "mail-edge01", "Exchange edge", DEPT["IT"], "assigned", "SMTP edge transport"),
    ("DMZ-Public-Services", "172.16.0.20", "vpn-gw01", "AnyConnect headend", DEPT["IT"], "assigned", "Remote access VPN"),
    ("DMZ-Public-Services", "172.16.0.30", "waf01", "nginx plus WAF", DEPT["IT"], "reserved", "Reserved for public API launch"),
    # -- Wireless / UC / Security / Lab ----------------------------------- #
    ("WLAN-Controllers", "10.40.0.1", "gw-wlan", "Core SW (SVI)", DEPT["IT"], "assigned", "WLAN gateway"),
    ("WLAN-Controllers", "10.40.0.10", "wlc01", "Aruba 7240XM", DEPT["IT"], "assigned", "Primary controller"),
    ("WLAN-Controllers", "10.40.0.11", "wlc02", "Aruba 7240XM", DEPT["IT"], "assigned", "Standby controller"),
    ("UC-Servers", "10.50.0.1", "gw-uc", "Core SW (SVI)", DEPT["IT"], "assigned", "UC gateway"),
    ("UC-Servers", "10.50.0.10", "cucm01", "Cisco CUCM", DEPT["IT"], "assigned", "Call manager publisher"),
    ("UC-Servers", "10.50.0.11", "cucm02", "Cisco CUCM", DEPT["IT"], "assigned", "Call manager subscriber"),
    ("UC-Servers", "10.50.0.20", "cube-edge01", "Cisco CUBE", DEPT["IT"], "assigned", "SIP trunk border"),
    ("UC-Handset-Pool", "10.50.0.70", "sep001122334455", "Cisco 7811 phone", DEPT["CS"], "assigned", "Leeds support handset"),
    ("UC-Handset-Pool", "10.50.0.90", None, None, None, "available", "DHCP scope — handsets"),
    ("SEC-CCTV", "10.60.0.1", "gw-sec-cctv", "Access SW (SVI)", DEPT["SEC"], "assigned", "CCTV gateway"),
    ("SEC-CCTV", "10.60.0.10", "nvr01", "Milestone XProtect", DEPT["SEC"], "assigned", "Recording server"),
    ("SEC-Access-Control", "10.60.0.65", "acs-controller01", "Lenel OnGuard", DEPT["SEC"], "assigned", "Door controller head end"),
    ("LAB-Networks", "10.99.0.1", "gw-lab", "Lab SW (SVI)", DEPT["IT"], "assigned", "Lab gateway"),
    ("LAB-Networks", "10.99.0.10", "lab-vmhost01", "Proxmox 8", DEPT["IT"], "assigned", "Sandbox host 1"),
    ("LAB-Networks", "10.99.0.11", "lab-vmhost02", "Proxmox 8", DEPT["IT"], "assigned", "Sandbox host 2"),
    ("LAB-Testbed", "10.99.100.20", "lab-ns3", "Ubuntu 24.04 LTS", DEPT["IT"], "deprecated", "Old network simulator, kept for legacy tests"),
]

# ----------------------------------------------------------------------- #
# Allocation plans (draft / activated / archived lifecycle)               #
# ----------------------------------------------------------------------- #
SHEFFIELD_DEPTS = [
    {"name": "Sheffield Operations", "required_hosts": 130, "vlan_id": 60, "growth_percent": 25},
    {"name": "Sheffield Warehouse", "required_hosts": 85, "vlan_id": 65, "growth_percent": 20, "additional_reserved_addresses": 4},
    {"name": "Sheffield Sales", "required_hosts": 40, "vlan_id": 40, "growth_percent": 15},
    {"name": "Sheffield IT", "required_hosts": 12, "vlan_id": 110, "growth_percent": 10},
    {"name": "Sheffield Voice", "required_hosts": 30, "vlan_id": 20, "growth_percent": 10, "additional_reserved_addresses": 5},
]

BRISTOL_DEPTS = [
    {"name": "Bristol Operations", "required_hosts": 100, "vlan_id": 60, "growth_percent": 20},
    {"name": "Bristol Sales", "required_hosts": 35, "vlan_id": 40, "growth_percent": 15},
    {"name": "Bristol Support", "required_hosts": 55, "vlan_id": 55, "growth_percent": 10},
    {"name": "Bristol IT", "required_hosts": 10, "vlan_id": 110},
]

DC_PHASE2_DEPTS = [
    {"name": "DB Tier", "required_hosts": 40, "vlan_id": 275},
    {"name": "Cloud On-ramp", "required_hosts": 24, "vlan_id": 270},
    {"name": "Monitoring", "required_hosts": 20, "vlan_id": 280},
    {"name": "Logging", "required_hosts": 15, "vlan_id": 285},
]

PLANS = [
    # (name, base_network, departments, notes, post-create action)
    (
        "Sheffield Branch Rollout — Q1",
        "10.35.0.0/22",
        SHEFFIELD_DEPTS,
        "Approved in CAB 2026-09-30. Awaiting cabling completion; activate after the rack install window.",
        None,  # stays draft
    ),
    (
        "Bristol Branch Opening",
        "10.34.0.0/22",
        BRISTOL_DEPTS,
        "Bristol office fit-out complete — activated and committed to the inventory.",
        "activate",
    ),
    (
        "DC1 Expansion Phase 2",
        "10.20.64.0/22",
        DC_PHASE2_DEPTS,
        "Superseded by the cloud-first initiative; kept for audit history.",
        "archive",
    ),
]

POLICY = {"growth_percent": 10.0, "utilization_warning_threshold": 80.0}


# ----------------------------------------------------------------------- #
# Seeding helpers                                                          #
# ----------------------------------------------------------------------- #
RESET_ORDER = ("ip_addresses", "subnets", "allocation_plans", "networks", "departments", "audit_events")


def backup_sqlite() -> Path | None:
    """Copy the SQLite file aside before wiping (no-op for other backends)."""
    database = engine.url.database
    if not database or ":memory:" in str(database):
        return None
    path = Path(str(database)).resolve()
    if not path.exists():
        return None
    stamp = NOW.strftime("%Y%m%d-%H%M%S")
    target = path.with_name(f"{path.stem}.bak-{stamp}{path.suffix}")
    shutil.copy2(path, target)
    return target


def reset_all(db) -> None:
    for table in RESET_ORDER:
        db.execute(text(f"DELETE FROM {table}"))
    db.commit()


def backdate(db) -> None:
    """Spread timestamps over the last ~8 weeks so the data feels lived-in."""
    rng = random.Random(SEED)

    def when(days: float) -> datetime:
        return NOW - timedelta(minutes=rng.uniform(0, days * 24 * 60))

    for table in ("departments", "networks"):
        rows = db.execute(text(f"SELECT id FROM {table}")).scalars().all()
        for rid in rows:
            t = when(60)
            db.execute(
                text(f"UPDATE {table} SET created_at = :t, updated_at = :t2 WHERE id = :i"),
                {"t": t, "t2": t + timedelta(minutes=rng.uniform(0, 240)), "i": rid},
            )
    sub_ids = db.execute(text("SELECT id FROM subnets ORDER BY id")).scalars().all()
    for rid in sub_ids:
        t = when(50)
        db.execute(
            text("UPDATE subnets SET created_at = :t, updated_at = :t2 WHERE id = :i"),
            {"t": t, "t2": t + timedelta(minutes=rng.uniform(0, 300)), "i": rid},
        )
    ip_ids = db.execute(text("SELECT id FROM ip_addresses ORDER BY id")).scalars().all()
    for rid in ip_ids:
        t = when(40)
        db.execute(
            text("UPDATE ip_addresses SET created_at = :t, updated_at = :t2 WHERE id = :i"),
            {"t": t, "t2": t + timedelta(minutes=rng.uniform(0, 120)), "i": rid},
        )
    plan_ids = db.execute(text("SELECT id FROM allocation_plans ORDER BY id")).scalars().all()
    for rid in plan_ids:
        t = when(30)
        db.execute(
            text("UPDATE allocation_plans SET created_at = :t, updated_at = :t2 WHERE id = :i"),
            {"t": t, "t2": t + timedelta(minutes=rng.uniform(0, 480)), "i": rid},
        )
    # Audit trail: monotonically increasing over the window, newest last.
    audit_ids = db.execute(text("SELECT id FROM audit_events ORDER BY id")).scalars().all()
    start = NOW - timedelta(days=55)
    span = (NOW - start).total_seconds() / max(len(audit_ids), 1)
    for offset, rid in enumerate(audit_ids):
        t = start + timedelta(seconds=span * offset + rng.uniform(0, span * 0.9))
        db.execute(text("UPDATE audit_events SET timestamp = :t WHERE id = :i"), {"t": t, "i": rid})
    db.commit()


def seed() -> None:
    db = SessionLocal()
    try:
        # 1. departments --------------------------------------------------
        dept_ids: dict[str, int] = {}
        for name, hosts, vlan, site, description in DEPARTMENTS:
            obj = ipam_service.create_department(
                db,
                {
                    "name": name,
                    "description": description,
                    "default_host_requirement": hosts,
                    "vlan_id": vlan,
                    "site": site,
                },
            )
            dept_ids[obj.name] = obj.id
        print(f"departments: {len(dept_ids)}")

        # 2. networks -----------------------------------------------------
        net_ids: dict[str, int] = {}
        for name, cidr, environment, site, status, description in NETWORKS:
            obj = ipam_service.create_network(
                db,
                {
                    "name": name,
                    "cidr": cidr,
                    "environment": environment,
                    "site": site,
                    "status": status,
                    "description": description,
                },
            )
            net_ids[obj.name] = obj.id
        print(f"networks:    {len(net_ids)}")

        # 3. subnets ------------------------------------------------------
        subnet_ids: dict[str, int] = {}
        for net_name, entries in SUBNETS.items():
            for name, cidr, vlan, gateway, status, description in entries:
                obj = ipam_service.create_subnet(
                    db,
                    {
                        "network_id": net_ids[net_name],
                        "name": name,
                        "cidr": cidr,
                        "vlan_id": vlan,
                        "gateway": gateway,
                        "status": status,
                        "description": description,
                    },
                )
                subnet_ids[obj.name] = obj.id
        print(f"subnets:     {len(subnet_ids)}")

        # 4. ip addresses --------------------------------------------------
        for subnet_name, address, hostname, device, dept, status, description in IPS:
            ipam_service.create_ip_address(
                db,
                {
                    "subnet_id": subnet_ids[subnet_name],
                    "address": address,
                    "hostname": hostname,
                    "device": device,
                    "department_id": dept_ids.get(dept),
                    "status": status,
                    "description": description,
                },
            )
        print(f"ip addresses:{len(IPS):>4}")

        # 5. allocation plans ----------------------------------------------
        for name, base, departments, notes, action in PLANS:
            plan = ipam_service.create_plan(
                db,
                {
                    "name": name,
                    "base_network": base,
                    "departments": departments,
                    "policy": POLICY,
                    "notes": notes,
                },
            )
            if action == "activate":
                res = ipam_service.activate_plan(db, plan.id)
                # tag the auto-created parent network with the branch site
                if res.get("network_id"):
                    ipam_service.update_network(
                        db, res["network_id"], {"site": "Bristol"}
                    )
                print(f"plan '{name}': activated, {res['subnets_created']} subnet(s) committed")
            elif action == "archive":
                ipam_service.archive_plan(db, plan.id)
                print(f"plan '{name}': archived")
            else:
                print(f"plan '{name}': saved as draft")

        # 6. lived-in timestamps --------------------------------------------
        backdate(db)
        print("timestamps: backdated over the last 8 weeks")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-backup", action="store_true", help="skip the SQLite backup copy")
    args = parser.parse_args()

    if not args.no_backup:
        backup = backup_sqlite()
        print(f"backup:     {backup}" if backup else "backup:     skipped (no sqlite file)")

    db = SessionLocal()
    try:
        reset_all(db)
    finally:
        db.close()
    print("reset:      all tables cleared")

    seed()
    print("done — reload the UI to explore the Aurora Dynamics topology")


if __name__ == "__main__":
    main()
