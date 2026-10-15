"""IPAddress model: an individually tracked address inside a subnet.

Addresses are tracked on demand (range-based planning lives in the allocator);
we never materialize every address of a large subnet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.subnet import Subnet


class IPAddress(Base, TimestampMixin):
    __tablename__ = "ip_addresses"
    __table_args__ = (
        UniqueConstraint("subnet_id", "address", name="uq_ip_subnet_address"),
        CheckConstraint("family IN (4, 6)", name="ck_ip_family"),
        CheckConstraint(
            "status IN ('available', 'reserved', 'assigned', 'deprecated')",
            name="ck_ip_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    address: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    family: Mapped[int] = mapped_column(nullable=False, index=True)
    subnet_id: Mapped[int] = mapped_column(
        ForeignKey("subnets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hostname: Mapped[str | None] = mapped_column(String(255))
    device: Mapped[str | None] = mapped_column(String(255), index=True)
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="assigned", index=True)
    description: Mapped[str | None] = mapped_column(Text)

    subnet: Mapped["Subnet"] = relationship(back_populates="ip_addresses")
    department: Mapped["Department | None"] = relationship(lazy="selectin")
