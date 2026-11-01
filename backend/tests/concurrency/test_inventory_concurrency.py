"""M7-AC-008 — concurrent allocation changes must not silently conflict.

Runs the real application (uvicorn subprocess) against a file-backed SQLite
database so multiple threads issue genuinely independent HTTP requests, then
races:

* identical subnet CIDR allocations  -> exactly one 201, the rest clean 409
* identical IP address registrations -> exactly one 201, the rest clean 409
* overlapping-but-distinct subnets   -> no overlapping pair ever survives

Note (recorded like every milestone): SQLite serialises writers; PostgreSQL
concurrency evidence becomes mandatory later (roadmap R-08, M9/M12).
"""

from __future__ import annotations

import ipaddress
import itertools
import json
import os
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ADMINUSER = "cnc"
ADMINPASS = "ConcTest1!"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _bootstrap_db(db_file: Path) -> None:
    """Create the schema and the test admin on the file-backed DB."""
    code = (
        "from app.db.session import init_db, SessionLocal;"
        "from app.models.user import User;"
        "from app.core.security import password_hash;"
        "init_db();"
        "db = SessionLocal();"
        "db.add(User(username='" + ADMINUSER + "', role='admin', "
        "password_hash=password_hash('" + ADMINPASS + "')));"
        "db.commit();"
        "print('bootstrapped')"
    )
    env = dict(os.environ, NETSPACE_DATABASE_URL=f"sqlite:///{db_file}", NETSPACE_AUTH_SECRET="conc-test-secret")
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_ROOT,
        env=env,
        check=True,
        capture_output=True,
        timeout=60,
    )


@pytest.fixture(scope="module")
def server() -> str:
    db_file = Path("/tmp") / f"netspace-conc-{time.time_ns()}" / "conc.db"
    db_file.parent.mkdir(parents=True, exist_ok=True)
    _bootstrap_db(db_file)
    port = _free_port()
    env = dict(
        os.environ,
        NETSPACE_DATABASE_URL=f"sqlite:///{db_file}",
        NETSPACE_AUTH_SECRET="conc-test-secret",
        NETSPACE_LOG_LEVEL="WARNING",
    )
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--log-level", "warning"],
        cwd=BACKEND_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        last_error: Exception | None = None
        for _ in range(80):
            try:
                if httpx.get(f"{base}/health", timeout=1).status_code == 200:
                    break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
            time.sleep(0.25)
        else:
            raise RuntimeError(f"server did not become healthy: {last_error}")
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
    db_file.unlink(missing_ok=True)
    db_file.parent.rmdir()


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login(base: str) -> str:
    r = httpx.post(
        f"{base}/api/v1/auth/login",
        json={"username": ADMINUSER, "password": ADMINPASS},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _race(base: str, token: str, path: str, payloads: list[dict]) -> list[httpx.Response]:
    with ThreadPoolExecutor(max_workers=len(payloads)) as pool:
        futures = [
            pool.submit(
                lambda p=p: httpx.post(
                    f"{base}{path}",
                    json=p,
                    headers=_headers(token),
                    timeout=30,
                )
            )
            for p in payloads
        ]
        return [f.result() for f in futures]


def _assert_no_500(responses: list[httpx.Response]) -> None:
    bad = [(r.status_code, r.text) for r in responses if r.status_code >= 500]
    assert not bad, f"unexpected >=500 responses: {bad}"


def test_concurrent_identical_subnet_allocations(server: str) -> None:
    token = _login(server)
    nets = httpx.post(
        f"{server}/api/v1/networks",
        json={"name": "Conc Net", "cidr": "10.90.0.0/16", "site": "Lab"},
        headers=_headers(token),
        timeout=10,
    )
    assert nets.status_code == 201, nets.text
    network_id = nets.json()["id"]

    payloads = [
        {"network_id": network_id, "name": f"race-{i}", "cidr": "10.90.0.0/24"}
        for i in range(6)
    ]
    responses = _race(server, token, "/api/v1/subnets", payloads)

    _assert_no_500(responses)
    codes = [r.status_code for r in responses]
    assert codes.count(201) == 1, f"expected exactly one winner, got {codes}"
    assert codes.count(409) == 5, f"expected 409 for the losers, got {codes}"
    loser_codes = {json.loads(r.text)["error"]["code"] for r in responses if r.status_code == 409}
    assert loser_codes == {"duplicate_cidr"}

    listing = httpx.get(
        f"{server}/api/v1/subnets", params={"network_id": network_id}, timeout=10
    ).json()
    assert listing["total"] == 1


def test_concurrent_identical_ip_registrations(server: str) -> None:
    token = _login(server)
    subnets = httpx.post(
        f"{server}/api/v1/subnets",
        json={"network_id": 1, "name": "ip-race", "cidr": "10.90.1.0/24"},
        headers=_headers(token),
        timeout=10,
    )
    assert subnets.status_code == 201, subnets.text
    subnet_id = subnets.json()["id"]

    payloads = [
        {"subnet_id": subnet_id, "address": "10.90.1.55", "hostname": f"h{i}"}
        for i in range(6)
    ]
    responses = _race(server, token, "/api/v1/ip-addresses", payloads)

    _assert_no_500(responses)
    codes = [r.status_code for r in responses]
    assert codes.count(201) == 1, codes
    assert codes.count(409) == 5, codes
    loser_codes = {json.loads(r.text)["error"]["code"] for r in responses if r.status_code == 409}
    assert loser_codes == {"duplicate_assignment"}


def test_concurrent_overlapping_subnets_never_persist(server: str) -> None:
    token = _login(server)
    net = httpx.post(
        f"{server}/api/v1/networks",
        json={"name": "Conc Overlap", "cidr": "10.91.0.0/16"},
        headers=_headers(token),
        timeout=10,
    )
    assert net.status_code == 201, net.text
    network_id = net.json()["id"]
    # three overlapping candidates of the same parent; interleaving decides
    # which survive, but no overlapping pair may ever remain.
    candidates = ["10.91.0.0/22", "10.91.0.0/24", "10.91.0.0/23"]
    payloads = [
        {"network_id": network_id, "name": f"ovl-{i}", "cidr": candidates[i % len(candidates)]}
        for i in range(6)
    ]
    responses = _race(server, token, "/api/v1/subnets", payloads)
    _assert_no_500(responses)

    survivors = httpx.get(
        f"{server}/api/v1/subnets", params={"network_id": network_id, "page_size": 200}, timeout=10
    ).json()["items"]
    for a, b in itertools.combinations(survivors, 2):
        na = ipaddress.ip_network(a["cidr"])
        nb = ipaddress.ip_network(b["cidr"])
        assert not na.overlaps(nb), f"overlapping allocation survived: {a['cidr']} vs {b['cidr']}"
    assert 1 <= len(survivors) <= 3
