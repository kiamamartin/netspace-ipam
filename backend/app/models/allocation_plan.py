"""AllocationPlan model: a saved, previewable VLSM plan.

Plans are separate from committed IPAM allocations: users calculate and preview
a plan without changing production records, then explicitly activate it.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, CheckConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AllocationPlan(Base, TimestampMixin):
    __tablename__ = "allocation_plans"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'active', 'archived', 'failed')", name="ck_plan_status"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    base_network: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    family: Mapped[int] = mapped_column(nullable=False, index=True)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(50), nullable=False)
    results: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    notes: Mapped[str | None] = mapped_column(Text)
