#!/usr/bin/env python
"""Bootstrap an authentication account (M5).

Usage:
    .venv/Scripts/python.exe scripts/create_admin.py
    .venv/Scripts/python.exe scripts/create_admin.py --username admin --password '…' --role admin

Credentials are never written to source control; pass them interactively or via
arguments on the command line of your choice. Run against the configured
NETSPACE_DATABASE_URL (defaults to the dev SQLite file).
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import USER_ROLES, password_hash  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.models.user import User  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or update an account")
    parser.add_argument("--username", help="unique username")
    parser.add_argument("--password", help="password (min 8 chars); omit to be prompted")
    parser.add_argument("--role", default="admin", choices=USER_ROLES, help="role (default: admin)")
    args = parser.parse_args()

    username = args.username or input("username: ").strip()
    password = args.password or getpass.getpass("password: ")
    if len(password) < 8:
        print("password must be at least 8 characters", file=sys.stderr)
        return 2
    if not username:
        print("username is required", file=sys.stderr)
        return 2

    init_db()
    with SessionLocal() as db:
        existing = db.query(User).filter(User.username == username).first()
        if existing is not None:
            existing.role = args.role
            existing.password_hash = password_hash(password)
            existing.is_active = True
            action = "updated"
        else:
            db.add(User(username=username, role=args.role, password_hash=password_hash(password)))
            action = "created"
        db.commit()
        print(f"account '{username}' {action} with role '{args.role}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
