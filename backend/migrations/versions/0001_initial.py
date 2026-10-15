"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-15

Creates the complete NetSpace IPAM schema: networks, subnets, ip_addresses,
departments, allocation_plans and audit_events.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_host_requirement", sa.Integer(), nullable=False),
        sa.Column("vlan_id", sa.Integer(), nullable=True),
        sa.Column("site", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("vlan_id IS NULL OR (vlan_id >= 1 AND vlan_id <= 4094)", name="ck_dept_vlan"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_departments_name", "departments", ["name"])
    op.create_index("ix_departments_vlan_id", "departments", ["vlan_id"])
    op.create_index("ix_departments_site", "departments", ["site"])

    op.create_table(
        "networks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("cidr", sa.String(length=64), nullable=False),
        sa.Column("family", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("site", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("family IN (4, 6)", name="ck_network_family"),
        sa.CheckConstraint("status IN ('active', 'planned', 'deprecated')", name="ck_network_status"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("cidr"),
    )
    op.create_index("ix_networks_name", "networks", ["name"])
    op.create_index("ix_networks_cidr", "networks", ["cidr"])
    op.create_index("ix_networks_family", "networks", ["family"])
    op.create_index("ix_networks_environment", "networks", ["environment"])
    op.create_index("ix_networks_site", "networks", ["site"])
    op.create_index("ix_networks_status", "networks", ["status"])
    op.create_index("ix_networks_created_at", "networks", ["created_at"])

    op.create_table(
        "subnets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("network_id", sa.Integer(), sa.ForeignKey("networks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("cidr", sa.String(length=64), nullable=False),
        sa.Column("prefix_length", sa.Integer(), nullable=False),
        sa.Column("vlan_id", sa.Integer(), nullable=True),
        sa.Column("gateway", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("vlan_id IS NULL OR (vlan_id >= 1 AND vlan_id <= 4094)", name="ck_subnet_vlan"),
        sa.CheckConstraint(
            "status IN ('allocated', 'planned', 'reserved', 'released')", name="ck_subnet_status"
        ),
        sa.UniqueConstraint("network_id", "cidr", name="uq_subnet_network_cidr"),
    )
    op.create_index("ix_subnets_cidr", "subnets", ["cidr"])
    op.create_index("ix_subnets_network_id", "subnets", ["network_id"])
    op.create_index("ix_subnets_name", "subnets", ["name"])
    op.create_index("ix_subnets_vlan_id", "subnets", ["vlan_id"])
    op.create_index("ix_subnets_status", "subnets", ["status"])
    op.create_index("ix_subnets_created_at", "subnets", ["created_at"])

    op.create_table(
        "ip_addresses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("address", sa.String(length=64), nullable=False),
        sa.Column("family", sa.Integer(), nullable=False),
        sa.Column("subnet_id", sa.Integer(), sa.ForeignKey("subnets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=True),
        sa.Column("device", sa.String(length=255), nullable=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("family IN (4, 6)", name="ck_ip_family"),
        sa.CheckConstraint(
            "status IN ('available', 'reserved', 'assigned', 'deprecated')", name="ck_ip_status"
        ),
        sa.UniqueConstraint("subnet_id", "address", name="uq_ip_subnet_address"),
    )
    op.create_index("ix_ip_addresses_address", "ip_addresses", ["address"])
    op.create_index("ix_ip_addresses_family", "ip_addresses", ["family"])
    op.create_index("ix_ip_addresses_subnet_id", "ip_addresses", ["subnet_id"])
    op.create_index("ix_ip_addresses_device", "ip_addresses", ["device"])
    op.create_index("ix_ip_addresses_department_id", "ip_addresses", ["department_id"])
    op.create_index("ix_ip_addresses_status", "ip_addresses", ["status"])
    op.create_index("ix_ip_addresses_created_at", "ip_addresses", ["created_at"])

    op.create_table(
        "allocation_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("base_network", sa.String(length=64), nullable=False),
        sa.Column("family", sa.Integer(), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("algorithm_version", sa.String(length=50), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'archived', 'failed')", name="ck_plan_status"
        ),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_allocation_plans_name", "allocation_plans", ["name"])
    op.create_index("ix_allocation_plans_base_network", "allocation_plans", ["base_network"])
    op.create_index("ix_allocation_plans_family", "allocation_plans", ["family"])
    op.create_index("ix_allocation_plans_status", "allocation_plans", ["status"])
    op.create_index("ix_allocation_plans_created_at", "allocation_plans", ["created_at"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("actor", sa.String(length=200), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
    )
    op.create_index("ix_audit_events_resource_type", "audit_events", ["resource_type"])
    op.create_index("ix_audit_events_resource_id", "audit_events", ["resource_id"])
    op.create_index("ix_audit_events_timestamp", "audit_events", ["timestamp"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("allocation_plans")
    op.drop_table("ip_addresses")
    op.drop_table("subnets")
    op.drop_table("networks")
    op.drop_table("departments")
