"""Calculator request/response schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VLAN_MIN, VLAN_MAX = 1, 4094


class SubnetCalcRequest(BaseModel):
    """Input for POST /calculator/subnet."""

    model_config = ConfigDict(json_schema_extra={
        "examples": [
            {"network": "192.168.10.0/24"},
            {"network": "192.168.10.0/24", "hosts": 50},
            {"network": "2001:db8::/64"},
        ]
    })

    network: str = Field(..., description="Network in CIDR notation, a bare address, or a bare prefix length")
    family: Literal[4, 6] | None = Field(None, description="Expected address family")
    hosts: int | None = Field(None, ge=1, description="Also compute the smallest prefix providing this many usable hosts")
    prefix_length: int | None = Field(None, ge=0, le=128, description="Also build the network for this prefix")


class VLSMDepartment(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    required_hosts: int = Field(..., ge=1, le=2**31)
    department_id: str | None = Field(None, max_length=64)
    description: str | None = None
    vlan_id: int | None = Field(None, ge=VLAN_MIN, le=VLAN_MAX)
    gateway: str | None = None
    additional_reserved_addresses: int = Field(0, ge=0)
    growth_percent: float | None = Field(None, ge=0, le=1000)
    prefix_length: int | None = Field(None, ge=0, le=128, description="Explicit prefix override")
    allow_point_to_point: bool | None = None
    allow_host_route: bool | None = None


class AllocationPolicyInput(BaseModel):
    allow_point_to_point: bool = False
    allow_host_route: bool = False
    growth_percent: float = Field(0.0, ge=0, le=1000, description="Default growth allowance applied to every department")
    utilization_warning_threshold: float = Field(80.0, ge=0, le=100)


class VLSMRequest(BaseModel):
    """Input for POST /calculator/vlsm."""

    model_config = ConfigDict(json_schema_extra={
        "examples": [
            {
                "base_network": "192.168.10.0/24",
                "departments": [
                    {"name": "Administration", "required_hosts": 50},
                    {"name": "ICT", "required_hosts": 25, "vlan_id": 20},
                    {"name": "Finance", "required_hosts": 20},
                    {"name": "Human Resources", "required_hosts": 12},
                    {"name": "Guest Network", "required_hosts": 10},
                ],
            }
        ]
    })

    base_network: str = Field(..., min_length=3, max_length=64)
    family: Literal[4, 6] | None = None
    policy: AllocationPolicyInput = Field(default_factory=AllocationPolicyInput)
    departments: list[VLSMDepartment] = Field(..., min_length=1, max_length=512)

    @field_validator("departments")
    @classmethod
    def _unique_names(cls, v: list[VLSMDepartment]) -> list[VLSMDepartment]:
        seen: set[str] = set()
        for dept in v:
            key = dept.name.strip().lower()
            if key in seen:
                raise ValueError(f"Duplicate department name '{dept.name}'")
            seen.add(key)
        return v

    @model_validator(mode="after")
    def _family_consistency(self) -> "VLSMRequest":
        return self


class SplitRequest(BaseModel):
    network: str
    family: Literal[4, 6] | None = None
    count: int | None = Field(None, ge=2, le=2**20)
    prefix_length: int | None = Field(None, ge=0, le=128)

    @model_validator(mode="after")
    def _one_of(self) -> "SplitRequest":
        if self.count is None and self.prefix_length is None:
            raise ValueError("Either count or prefix_length must be provided")
        return self


class SummarizeRequest(BaseModel):
    networks: list[str] = Field(..., min_length=1, max_length=4096)
    family: Literal[4, 6] | None = None


class ValidateRequest(BaseModel):
    """Flexible validation input: any combination of fields to check."""

    cidr: str | None = None
    family: Literal[4, 6] | None = None
    vlan_id: int | None = Field(None, ge=0, le=4096)
    gateway: str | None = None
    base_network: str | None = None
    departments: list[VLSMDepartment] | None = None
    policy: AllocationPolicyInput | None = None


class ValidateResponse(BaseModel):
    valid: bool
    normalized: dict[str, Any] = Field(default_factory=dict)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
