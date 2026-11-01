# Enterprise Demo Dataset

The local dev database ships with a realistic multi-site enterprise topology
("Aurora Dynamics") so the UI models real IPAM usage out of the box.

## Reseed

```bash
cd backend
NETSPACE_SEED_ADMIN_PASSWORD='...' \
NETSPACE_SEED_OPERATOR_PASSWORD='...' \
NETSPACE_SEED_VIEWER_PASSWORD='...' \
.venv/bin/python scripts/seed_enterprise.py           # macOS/Linux
# Windows: use .venv/Scripts/python.exe with the same environment variables.
```

Passwords are supplied only through the environment and are never stored in
the repository. If a password variable is omitted, the seed generates a
one-time random password for a newly created account and prints it once;
existing accounts keep their current password unless the matching variable is
set. The seed creates or repairs the three demo accounts `admin`, `operator`
and `viewer`.

The script **backs up** the SQLite file (`netspace.bak-<timestamp>.db` next to
it), **resets** all tables, then reseeds through the real service layer, so
containment/alignment/overlap validation, computed subnet details and the
audit trail all run exactly as they would for UI-entered data. Timestamps are
deterministically backdated over ~8 weeks (fixed RNG seed) so the dashboard's
recent-activity feed looks lived-in. Idempotent: re-run any time.

## What's in it

| Area | Contents |
| --- | --- |
| Departments | 14 org units with default host counts, VLANs and sites (Sales 120 hosts, Operations 220, R&D 140…) |
| HQ Campus `10.10.0.0/16` | Users /22, voice, corp WiFi, IT services, servers /23, IoT, guest (reserved), OOB mgmt (reserved) |
| DC1 `10.20.0.0/16` | Prod compute /22 (vCenter, ESXi, SQL AG, backups), staging, dev, storage, VM mgmt, backup, cluster heartbeat (/29, reserved, non-routed) |
| Branches | Manchester, Leeds (incl. one `released` legacy CCTV subnet), Glasgow — each users /23 + voice + WiFi + IT |
| Planned branch | Nottingham `10.36.0.0/24` — network status `planned`, no subnets yet |
| DMZ `172.16.0.0/24` | Public services /26 (mail edge, VPN, WAF-reserved) + firewall transit (reserved) |
| Special-purpose | Corporate WLAN `10.40.0.0/22`, Voice/UC `10.50.0.0/25` (**fully carved → dashboard near-capacity warning**), Security & building systems `10.60.0.0/24`, Lab `10.99.0.0/16` |
| Authentication | `admin` (admin), `operator` (operator), `viewer` (viewer) — passwords supplied via `NETSPACE_SEED_*_PASSWORD` |
| Tracked IPs | 82 addresses: gateways, AD/DNS/DHCP, hypervisors, SQL nodes, CUCM, WLCs, APs, cameras, printers, scanners; mix of assigned/available/reserved/deprecated |
| Allocation plans | `Sheffield Branch Rollout — Q1` (**draft**, 10.35.0.0/22, growth 10-25%), `Bristol Branch Opening` (**active** — activated through the real engine, committed as `Plan: Bristol Branch Opening`), `DC1 Expansion Phase 2` (**archived**) |

Conventions modelled: RFC1918 site summarisation, VLAN plan per site
(10 users / 20 voice / 30 WiFi / 1xx IT / 9xx guest), `.1` gateways,
growth allowances on plan inputs, reserved infrastructure blocks, and a
decommissioned subnet/IP left for audit realism.

Validation results after seeding: **0 conflicts**, 12 networks, 42 subnets
(37 allocated, 4 reserved, 1 released), 82 IPs, 3 plans (draft/active/archived),
153 audit events.
