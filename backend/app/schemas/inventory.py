"""Schemas for IPAM inventory resources (networks, subnets, IPs, departments, plans)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.calculator import AllocationPolicyInput, VLSMDepartment
from app.schemas.common import ORMModel

Environment = Literal["production", "staging", "development", "lab"]
NetworkStatus = Literal["active", "planned", "deprecated"]
SubnetStatus = Literal["allocated", "planned", "reserved", "released"]
IPStatus = Literal["available", "reserved", "assigned", "deprecated"]
PlanStatus = Literal["draft", "active", "archived", "failed"]


# --- Network ---------------------------------------------------------------

class NetworkCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    cidr: str = Field(..., min_length=3, max_length=64)
    description: str | None = None
    environment: Environment = "production"
    site: str | None = Field(None, max_length=200)
    status: NetworkStatus = "active"


class NetworkUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    environment: Environment | None = None
    site: str | None = Field(None, max_length=200)
    status: NetworkStatus | None = None


class SubnetSummary(ORMModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    cidr: str
    prefix_length: int
    vlan_id: int | None = None
    gateway: str | None = None
    status: SubnetStatus
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class NetworkRead(ORMModel):
    id: int
    name: str
    cidr: str
    family: int
    description: str | None = None
    environment: Environment
    site: str | None = None
    status: NetworkStatus
    created_at: datetime
    updated_at: datetime


class NetworkDetail(NetworkRead):
    subnets: list[SubnetSummary] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict, description="Computed subnet properties")


# --- Subnet ----------------------------------------------------------------

class SubnetCreate(BaseModel):
    network_id: int
    name: str = Field(..., min_length=1, max_length=200)
    cidr: str = Field(..., min_length=3, max_length=64)
    vlan_id: int | None = Field(None, ge=1, le=4094)
    gateway: str | None = None
    status: SubnetStatus = "allocated"
    description: str | None = None


class SubnetUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    cidr: str | None = Field(None, min_length=3, max_length=64)
    vlan_id: int | None = Field(None, ge=1, le=4094)
    gateway: str | None = None
    status: SubnetStatus | None = None
    description: str | None = None


class SubnetRead(SubnetSummary):
    network_id: int
    family: int
    details: dict[str, Any] = Field(default_factory=dict)
    ip_address_count: int = 0


# --- IP addresses ----------------------------------------------------------

class IPAddressCreate(BaseModel):
    subnet_id: int
    address: str = Field(..., min_length=2, max_length=64)
    hostname: str | None = Field(None, max_length=255)
    device: str | None = Field(None, max_length=255)
    department_id: int | None = None
    status: IPStatus = "assigned"
    description: str | None = None


class IPAddressUpdate(BaseModel):
    hostname: str | None = Field(None, max_length=255)
    device: str | None = Field(None, max_length=255)
    department_id: int | None = None
    status: IPStatus | None = None
    description: str | None = None


class IPAddressRead(ORMModel):
    id: int
    subnet_id: int
    address: str
    family: int
    hostname: str | None = None
    device: str | None = None
    department_id: int | None = None
    status: IPStatus
    description: str | None = None
    created_at: datetime
    updated_at: datetime


# --- Departments -----------------------------------------------------------

class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    default_host_requirement: int = Field(10, ge=1, le=2**31)
    vlan_id: int | None = Field(None, ge=1, le=4094)
    site: str | None = Field(None, max_length=200)


class DepartmentUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    default_host_requirement: int | None = Field(None, ge=1, le=2**31)
    vlan_id: int | None = Field(None, ge=1, le=4094)
    site: str | None = Field(None, max_length=200)


class DepartmentRead(ORMModel):
    id: int
    name: str
    description: str | None = None
    default_host_requirement: int
    vlan_id: int | None = None
    site: str | None = None
    created_at: datetime
    updated_at: datetime


# --- Allocation plans ------------------------------------------------------

class PlanCreate(BaseModel):
    """Save a validated allocation plan without committing anything."""

    name: str = Field(..., min_length=1, max_length=200)
    base_network: str = Field(..., min_length=3, max_length=64)
    family: Literal[4, 6] | None = None
    policy: AllocationPolicyInput = Field(default_factory=AllocationPolicyInput)
    departments: list[VLSMDepartment] = Field(..., min_length=1, max_length=512)
    notes: str | None = None


class PlanUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    notes: str | None = None


class PlanRead(ORMModel):
    id: int
    name: str
    base_network: str
    family: int
    algorithm_version: str
    status: PlanStatus
    inputs: dict[str, Any]
    results: dict[str, Any]
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class PlanList(ORMModel):
    id: int
    name: str
    base_network: str
    family: int
    algorithm_version: str
    status: PlanStatus
    department_count: int = 0
    overall_utilization_percent: float = 0.0
    created_at: datetime
    updated_at: datetime


class PlanActivateResponse(BaseModel):
    plan_id: int
    status: PlanStatus
    subnets_created: int
    network_id: int | None = None
    results: dict[str, Any]


# --- Dashboard / audit -----------------------------------------------------

class NetworkUtilization(BaseModel):
    network_id: int
    name: str
    cidr: str
    allocated_addresses: int
    total_addresses: int
    utilization_percent: float
    subnet_count: int


class DashboardSummary(BaseModel):
    total_networks: int
    total_subnets: int
    total_ip_addresses: int
    ip_available: int
    ip_reserved: int
    ip_assigned: int
    ip_deprecated: int
    total_plans: int
    active_plans: int
    average_utilization_percent: float
    networks: list[NetworkUtilization]
    conflicts: list[dict[str, Any]]
    near_capacity: list[NetworkUtilization]
    recent_activity: list[dict[str, Any]]


class AuditEventRead(BaseModel):
    id: int
    resource_type: str
    resource_id: str
    action: str
    timestamp: datetime
    actor: str | None = None
    summary: str | None = None


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    database: str
    algorithm_version: str
