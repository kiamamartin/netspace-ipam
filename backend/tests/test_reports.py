"""Integration tests for CSV / XLSX / PDF report endpoints."""

from __future__ import annotations

import csv
import io

import pytest
from fastapi.testclient import TestClient

try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None


def _admin_token() -> str:
    from app.core.config import get_settings
    from app.core.security import encode_token, password_hash, runtime_secret
    from app.db.session import SessionLocal
    from app.models.user import User

    settings = get_settings()
    with SessionLocal() as db:
        admin = db.query(User).filter(User.username == "adminuser").first()
        if admin is None:
            admin = User(
                username="adminuser",
                role="admin",
                password_hash=password_hash("AdminPass1!"),
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
        return encode_token(
            {"uid": admin.id, "role": admin.role},
            runtime_secret(settings.auth_secret),
            expires_minutes=settings.jwt_expires_minutes,
        )


def _seed_network_with_subnets(client: TestClient, subnet_count: int = 3) -> tuple[int, list[str]]:
    import ipaddress

    token = _admin_token()

    r = client.post(
        "/api/v1/networks",
        json={"name": "HQ LAN", "cidr": "192.168.10.0/24"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    net_id = r.json()["id"]
    cidrs = ["192.168.10.0/26", "192.168.10.64/27", "192.168.10.96/27", "192.168.10.128/28"]
    names = ["Administration", "ICT", "Finance", "HR"]
    created: list[str] = []
    for i in range(subnet_count):
        gateway = str(ipaddress.ip_network(cidrs[i]).network_address + 1)
        r = client.post(
            "/api/v1/subnets",
            json={
                "network_id": net_id,
                "name": names[i],
                "cidr": cidrs[i],
                "vlan_id": 10 + i,
                "gateway": gateway,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201, r.text
        created.append(cidrs[i])
    return net_id, created


def test_network_csv(client: TestClient) -> None:
    net_id, cidrs = _seed_network_with_subnets(client)
    r = client.get(f"/api/v1/reports/networks/{net_id}/csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert 'filename="network-1-report.csv"' in r.headers["content-disposition"]
    text = r.content.decode("utf-8")
    rows = list(csv.reader(io.StringIO(text)))
    header = rows[4]  # after the metadata preamble and blank line
    assert "department" in header and "network" in header
    data_rows = [row for row in rows if row and row[0].isdigit()]
    assert len(data_rows) == len(cidrs)
    networks_in_csv = {row[header.index("network")] for row in data_rows}
    assert networks_in_csv == set(cidrs)


def test_network_xlsx(client: TestClient) -> None:
    if openpyxl is None:  # pragma: no cover
        pytest.skip("openpyxl missing")
    net_id, cidrs = _seed_network_with_subnets(client)
    r = client.get(f"/api/v1/reports/networks/{net_id}/xlsx")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert 'filename="network-1-report.xlsx"' in r.headers["content-disposition"]
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert set(wb.sheetnames) == {"Summary", "VLSM Allocation", "Remaining Ranges", "Network Metadata"}
    ws = wb["VLSM Allocation"]
    header = [c.value for c in ws[1]]
    assert "network" in header
    col = header.index("network") + 1
    nets = {ws.cell(row=row, column=col).value for row in range(2, ws.max_row + 1)}
    assert nets == set(cidrs)
    # IP addresses/CIDRs must be stored as strings
    assert all(isinstance(ws.cell(row=row, column=col).value, str) for row in range(2, ws.max_row + 1))


def test_network_pdf(client: TestClient) -> None:
    net_id, _ = _seed_network_with_subnets(client)
    r = client.get(f"/api/v1/reports/networks/{net_id}/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert 'filename="network-1-report.pdf"' in r.headers["content-disposition"]
    assert r.content[:5] == b"%PDF-"
    assert len(r.content) > 1000


def test_plan_exports_match_saved_results(client: TestClient, sample_vlsm_payload: dict) -> None:
    """All export formats must reflect the same saved allocation result."""
    admin_token = _admin_token()
    r = client.post(
        "/api/v1/allocation-plans",
        json={"name": "Export Plan", **sample_vlsm_payload},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201, r.text
    plan = r.json()
    saved = {
        a["department"]: a["network"] for a in plan["results"]["allocations"]
    }

    csv_r = client.get(f"/api/v1/reports/allocation-plans/{plan['id']}/csv")
    assert csv_r.status_code == 200
    assert 'filename="allocation-plan-1.csv"' in csv_r.headers["content-disposition"]
    text = csv_r.content.decode("utf-8")
    for dept, cidr in saved.items():
        assert dept in text
        assert cidr in text

    if openpyxl is not None:
        xlsx_r = client.get(f"/api/v1/reports/allocation-plans/{plan['id']}/xlsx")
        assert xlsx_r.status_code == 200
        wb = openpyxl.load_workbook(io.BytesIO(xlsx_r.content))
        ws = wb["VLSM Allocation"]
        values = {cell.value for row in ws.iter_rows() for cell in row}
        for cidr in saved.values():
            assert cidr in values
        rem = wb["Remaining Ranges"]
        assert any(cell.value == "192.168.10.160" for row in rem.iter_rows() for cell in row)

    pdf_r = client.get(f"/api/v1/reports/allocation-plans/{plan['id']}/pdf")
    assert pdf_r.status_code == 200
    assert pdf_r.content[:5] == b"%PDF-"
    # PDF text contains the CIDRs (streams are uncompressed by reportlab default for text)
    raw = pdf_r.content
    assert b"192.168.10.0/26" in raw


def test_zero_row_reports_are_valid(client: TestClient) -> None:
    """Exports must work with zero allocation rows."""
    admin_token = _admin_token()
    r = client.post(
        "/api/v1/networks",
        json={"name": "Empty", "cidr": "10.9.0.0/16"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    net_id = r.json()["id"]
    for fmt in ("csv", "xlsx", "pdf"):
        r = client.get(f"/api/v1/reports/networks/{net_id}/{fmt}")
        assert r.status_code == 200, fmt
        if fmt == "pdf":
            assert r.content[:5] == b"%PDF-"
        if fmt == "csv":
            assert r.content  # still contains metadata preamble


def test_single_row_report(client: TestClient) -> None:
    net_id, _ = _seed_network_with_subnets(client, subnet_count=1)
    r = client.get(f"/api/v1/reports/networks/{net_id}/csv")
    assert r.status_code == 200
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8"))))
    data_rows = [row for row in rows if row and row[0].isdigit()]
    assert len(data_rows) == 1


def test_special_characters_sanitized(client: TestClient) -> None:
    """User-controlled text with markup characters must not break report generation."""
    r = client.post(
        "/api/v1/networks",
        json={"name": "Spc", "cidr": "10.8.0.0/24"},
        headers={"Authorization": f"Bearer {_admin_token()}"},
    )
    net_id = r.json()["id"]
    r = client.post(
        "/api/v1/subnets",
        json={
            "network_id": net_id,
            "name": "R&D <script>alert(1)</script>",
            "cidr": "10.8.0.0/26",
        },
        headers={"Authorization": f"Bearer {_admin_token()}"},
    )
    assert r.status_code == 201
    for fmt in ("csv", "xlsx", "pdf"):
        r = client.get(f"/api/v1/reports/networks/{net_id}/{fmt}")
        assert r.status_code == 200, fmt


def test_report_missing_resource_404(client: TestClient) -> None:
    assert client.get("/api/v1/reports/networks/4242/csv").status_code == 404
    assert client.get("/api/v1/reports/allocation-plans/4242/pdf").status_code == 404


def test_reports_use_database_data_not_recalculation(client: TestClient) -> None:
    """Changing the inventory after saving must change the report (it renders stored rows)."""
    net_id, _ = _seed_network_with_subnets(client, subnet_count=2)
    before = client.get(f"/api/v1/reports/networks/{net_id}/csv").content
    r = client.post(
        "/api/v1/subnets",
        json={
            "network_id": net_id,
            "name": "Finance",
            "cidr": "192.168.10.96/27",
        },
        headers={"Authorization": f"Bearer {_admin_token()}"},
    )
    assert r.status_code == 201, r.text
    after = client.get(f"/api/v1/reports/networks/{net_id}/csv").content
    assert before != after
