"""Subnet model: an allocated child network inside a parent Network."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.ip_address import IPAddress
    from app.models.network import Network


class Subnet(Base, TimestampMixin):
    __tablename__ = "subnets"
    __table_args__ = (
        UniqueConstraint("network_id", "cidr", name="uq_subnet_network_cidr"),
        CheckConstraint("vlan_id IS NULL OR (vlan_id >= 1 AND vlan_id <= 4094)", name="ck_subnet_vlan"),
        CheckConstraint(
            "status IN ('allocated', 'planned', 'reserved', 'released')",
            name="ck_subnet_status",
        ),
        Index("ix_subnets_cidr", "cidr"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    network_id: Mapped[int] = mapped_column(
        ForeignKey("networks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    cidr: Mapped[str] = mapped_column(String(64), nullable=False)
    prefix_length: Mapped[int] = mapped_column(nullable=False)
    vlan_id: Mapped[int | None] = mapped_column(index=True)
    gateway: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="allocated", index=True)
    description: Mapped[str | None] = mapped_column(Text)

    network: Mapped["Network"] = relationship(back_populates="subnets")
    ip_addresses: Mapped[list["IPAddress"]] = relationship(
        back_populates="subnet", cascade="all, delete-orphan", lazy="selectin"
    )
