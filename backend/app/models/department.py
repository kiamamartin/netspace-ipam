"""Department model: reusable organizational unit with defaults for planning."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Department(Base, TimestampMixin):
    __tablename__ = "departments"
    __table_args__ = (
        CheckConstraint(
            "vlan_id IS NULL OR (vlan_id >= 1 AND vlan_id <= 4094)", name="ck_dept_vlan"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    default_host_requirement: Mapped[int] = mapped_column(nullable=False, default=10)
    vlan_id: Mapped[int | None] = mapped_column(index=True)
    site: Mapped[str | None] = mapped_column(String(200), index=True)
