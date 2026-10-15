"""Calculator endpoints: stateless calculations, no database access."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.errors import AppError
from app.schemas.calculator import (
    SplitRequest,
    SubnetCalcRequest,
    SummarizeRequest,
    ValidateRequest,
    ValidateResponse,
    VLSMRequest,
)
from app.services import subnet_calculator as calc
from app.services.vlsm_allocator import (
    AllocationPolicy,
    DepartmentRequirement,
    VLSMError,
    allocate,
)

router = APIRouter()
settings = get_settings()


@router.post("/subnet", summary="Calculate subnet properties")
def calculate_subnet(payload: SubnetCalcRequest) -> dict:
    """Calculate IPv4/IPv6 subnet properties for a CIDR, address or prefix.

    Optionally also reports the smallest prefix that satisfies ``hosts``.
    """
    try:
        return calc.calculate(
            payload.network,
            family=payload.family,
            hosts=payload.hosts,
            prefix_length=payload.prefix_length,
        )
    except calc.SubnetCalculationError as exc:
        raise AppError("invalid_cidr", exc.message, 422, [{"field": exc.field, "message": exc.message}]) from exc


@router.post("/vlsm", summary="Run a dynamic VLSM allocation")
def calculate_vlsm(payload: VLSMRequest) -> dict:
    """Allocate subnets for department requirements inside a parent network.

    Largest-first aligned first-fit; returns the full allocation table,
    remaining address ranges and utilization summary. Raises ``409`` when the
    parent network cannot accommodate all requirements.
    """
    policy = AllocationPolicy(
        allow_point_to_point=payload.policy.allow_point_to_point,
        allow_host_route=payload.policy.allow_host_route,
        growth_percent=payload.policy.growth_percent,
        utilization_warning_threshold=payload.policy.utilization_warning_threshold,
        max_departments=settings.max_departments_per_plan,
    )
    departments = [
        DepartmentRequirement(
            name=d.name.strip(),
            required_hosts=d.required_hosts,
            department_id=d.department_id,
            description=d.description,
            vlan_id=d.vlan_id,
            gateway=d.gateway,
            additional_reserved_addresses=d.additional_reserved_addresses,
            growth_percent=d.growth_percent,
            prefix_length=d.prefix_length,
            allow_point_to_point=d.allow_point_to_point,
            allow_host_route=d.allow_host_route,
        )
        for d in payload.departments
    ]
    try:
        result = allocate(payload.base_network, departments, policy)
    except VLSMError as exc:
        status = 409 if exc.code == "insufficient_space" else 422
        raise AppError(exc.code, exc.message, status, exc.details) from exc
    result["algorithm_version"] = settings.algorithm_version
    return result


@router.post("/split", summary="Split a network into equal subnets")
def split(payload: SplitRequest) -> dict:
    try:
        parent = calc.parse_network(payload.network, family=payload.family)
    except calc.SubnetCalculationError as exc:
        raise AppError("invalid_cidr", exc.message, 422, [{"field": "network", "message": exc.message}]) from exc
    try:
        subnets = calc.split_network(parent, count=payload.count, prefix_length=payload.prefix_length)
    except calc.SubnetCalculationError as exc:
        raise AppError("validation_error", exc.message, 422, [{"field": exc.field, "message": exc.message}]) from exc
    return {
        "parent": str(parent),
        "parent_details": calc.subnet_details(parent),
        "count": len(subnets),
        "subnets": subnets,
    }


@router.post("/summarize", summary="Summarize networks into aggregates")
def summarize(payload: SummarizeRequest) -> dict:
    try:
        return calc.summarize_networks(payload.networks, family=payload.family)
    except calc.SubnetCalculationError as exc:
        details = getattr(exc, "details", [{"field": exc.field, "message": exc.message}])
        raise AppError("validation_error", exc.message, 422, details) from exc


@router.post("/validate", response_model=ValidateResponse, summary="Validate inputs")
def validate(payload: ValidateRequest) -> ValidateResponse:
    """Validate CIDR notation, family, VLAN IDs and (optionally) a full set of
    allocation constraints without allocating anything."""
    errors: list[dict] = []
    warnings: list[str] = []
    normalized: dict = {}

    if payload.cidr is not None:
        try:
            net = calc.parse_network(payload.cidr, family=payload.family)
            normalized["cidr"] = str(net)
            if not calc.is_normalized(payload.cidr, family=payload.family):
                warnings.append(f"'{payload.cidr}' had host bits set; normalized to {net}")
        except calc.SubnetCalculationError as exc:
            errors.append({"field": "cidr", "message": exc.message})

    if payload.vlan_id is not None and not 1 <= payload.vlan_id <= 4094:
        errors.append({"field": "vlan_id", "message": "VLAN ID must be between 1 and 4094"})
    elif payload.vlan_id is not None:
        normalized["vlan_id"] = payload.vlan_id

    if payload.gateway is not None:
        family = payload.family
        try:
            gw = calc.parse_address(payload.gateway, family=family)
            normalized["gateway"] = str(gw)
        except calc.SubnetCalculationError as exc:
            errors.append({"field": "gateway", "message": exc.message})

    if payload.departments is not None:
        base = payload.base_network or normalized.get("cidr", "0.0.0.0/0")
        try:
            policy = AllocationPolicy(
                allow_point_to_point=payload.policy.allow_point_to_point if payload.policy else False,
                allow_host_route=payload.policy.allow_host_route if payload.policy else False,
                growth_percent=payload.policy.growth_percent if payload.policy else 0.0,
                max_departments=settings.max_departments_per_plan,
            )
            departments = [
                DepartmentRequirement(
                    name=d.name.strip(),
                    required_hosts=d.required_hosts,
                    department_id=d.department_id,
                    vlan_id=d.vlan_id,
                    gateway=d.gateway,
                    additional_reserved_addresses=d.additional_reserved_addresses,
                    growth_percent=d.growth_percent,
                    prefix_length=d.prefix_length,
                )
                for d in payload.departments
            ]
            result = allocate(base, departments, policy)
            normalized["department_count"] = len(result["allocations"])
            warnings.extend(result["summary"].get("warnings", []))
        except VLSMError as exc:
            errors.append({"field": "departments", "message": exc.message})
            for detail in exc.details:
                errors.append(detail)

    return ValidateResponse(valid=not errors, normalized=normalized, errors=errors, warnings=warnings)
