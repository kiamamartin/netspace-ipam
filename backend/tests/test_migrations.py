"""Verify the Alembic migration creates the complete schema."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_upgrade_head_creates_all_tables() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "migrated.db"
        os.environ["NETSPACE_DATABASE_URL"] = f"sqlite:///{db_path}"
        try:
            cfg = Config(str(BACKEND_DIR / "alembic.ini"))
            cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
            cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
            command.upgrade(cfg, "head")
        finally:
            os.environ["NETSPACE_DATABASE_URL"] = "sqlite:///:memory:"

        con = sqlite3.connect(db_path)
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        con.close()
        assert {
            "networks",
            "subnets",
            "ip_addresses",
            "departments",
            "allocation_plans",
            "audit_events",
            "alembic_version",
        } <= tables


def test_downgrade_removes_tables() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "downgraded.db"
        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")
        con = sqlite3.connect(db_path)
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        con.close()
        assert "networks" not in tables
