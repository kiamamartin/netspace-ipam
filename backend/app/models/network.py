"""Network model: a parent (container) IP network."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.subnet import Subnet


class Network(Base, TimestampMixin):
    __tablename__ = "networks"
    __table_args__ = (
        CheckConstraint("family IN (4, 6)", name="ck_network_family"),
        CheckConstraint(
            "status IN ('active', 'planned', 'deprecated')", name="ck_network_status"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    cidr: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    family: Mapped[int] = mapped_column(nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    environment: Mapped[str] = mapped_column(
        String(32), nullable=False, default="production", index=True
    )
    site: Mapped[str | None] = mapped_column(String(200), index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)

    subnets: Mapped[list["Subnet"]] = relationship(
        back_populates="network", cascade="all, delete-orphan", lazy="selectin"
    )
