"""IPAM persistence service.

All database mutations go through this module so that validation (containment,
alignment, overlap, referential integrity) is enforced uniformly. Route
handlers stay thin: parse -> call service -> serialize.
"""

from __future__ import annotations

import ipaddress
import math
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, conflict, not_found, validation_error
from app.models import (
    AllocationPlan,
    AuditEvent,
    Department,
    IPAddress,
    Network,
    Subnet,
)
from app.schemas.calculator import AllocationPolicyInput, VLSMDepartment
from app.schemas.inventory import NetworkRead
from app.services.subnet_calculator import (
    SubnetCalculationError,
    parse_address,
    parse_network,
    subnet_details,
    usable_capacity,
)
from app.services.vlsm_allocator import (
    AllocationPolicy,
    DepartmentRequirement,
    VLSMError,
    allocate,
)

settings = get_settings()

SUBNET_ACTIVE_STATES = ("allocated", "planned", "reserved")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _audit(
    db: Session,
    resource_type: str,
    resource_id: str | int,
    action: str,
    summary: str,
    actor: str | None = None,
) -> None:
    db.add(
        AuditEvent(
            resource_type=resource_type,
            resource_id=str(resource_id),
            action=action,
            summary=summary,
            actor=actor,
        )
    )


def _policy_from_input(policy: AllocationPolicyInput | dict[str, Any] | None) -> AllocationPolicy:
    if isinstance(policy, dict):
        policy = AllocationPolicyInput(**policy)
    policy = policy or AllocationPolicyInput()
    return AllocationPolicy(
        allow_point_to_point=policy.allow_point_to_point,
        allow_host_route=policy.allow_host_route,
        growth_percent=policy.growth_percent,
        utilization_warning_threshold=policy.utilization_warning_threshold,
        max_departments=settings.max_departments_per_plan,
    )


def requirements_from_schemas(depts: list[VLSMDepartment] | list[dict[str, Any]]) -> list[DepartmentRequirement]:
    normalized = [d if isinstance(d, VLSMDepartment) else VLSMDepartment(**d) for d in depts]
    return [
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
        for d in normalized
    ]


def _vlsm_error_to_app_error(exc: VLSMError) -> AppError:
    status = 409 if exc.code == "insufficient_space" else 422
    return AppError(exc.code, exc.message, status, exc.details)


def _parse_cidr_or_422(value: str, field: str, family: int | None = None) -> ipaddress.IPv4Network | ipaddress.IPv6Network:
    try:
        return parse_network(value, family=family)
    except SubnetCalculationError as exc:
        raise validation_error(exc.message, [{"field": field, "message": exc.message}]) from exc


def paginate(items: list[Any], page: int, page_size: int) -> dict[str, Any]:
    page = max(page, 1)
    page_size = max(min(page_size, settings.max_page_size), 1)
    total = len(items)
    pages = max(math.ceil(total / page_size), 1) if total else 0
    start = (page - 1) * page_size
    return {
        "items": items[start : start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


# ---------------------------------------------------------------------------
# Networks
# ---------------------------------------------------------------------------

def create_network(db: Session, data: dict[str, Any]) -> Network:
    net = _parse_cidr_or_422(data["cidr"], "cidr")
    existing_name = db.scalar(select(Network).where(func.lower(Network.name) == data["name"].strip().lower()))
    if existing_name:
        raise conflict("duplicate_name", f"A network named '{data['name']}' already exists")
    existing_cidr = db.scalar(select(Network).where(Network.cidr == str(net)))
    if existing_cidr:
        raise conflict(
            "duplicate_cidr",
            f"Network '{existing_cidr.name}' already manages {net}",
        )
    obj = Network(
        name=data["name"].strip(),
        cidr=str(net),
        family=net.version,
        description=data.get("description"),
        environment=data.get("environment", "production"),
        site=data.get("site"),
        status=data.get("status", "active"),
    )
    db.add(obj)
    db.flush()
    _audit(db, "network", obj.id, "create", f"Created network {obj.name} ({obj.cidr})")
    db.commit()
    db.refresh(obj)
    return obj


def list_networks(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 50,
    q: str | None = None,
    family: int | None = None,
    environment: str | None = None,
    status: str | None = None,
    site: str | None = None,
    sort: str = "created_at",
    order: str = "desc",
) -> dict[str, Any]:
    stmt = select(Network)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Network.name.ilike(like),
                Network.cidr.ilike(like),
                Network.site.ilike(like),
                Network.description.ilike(like),
            )
        )
    if family:
        stmt = stmt.where(Network.family == family)
    if environment:
        stmt = stmt.where(Network.environment == environment)
    if status:
        stmt = stmt.where(Network.status == status)
    if site:
        stmt = stmt.where(Network.site == site)
    sort_col = {
        "name": Network.name,
        "cidr": Network.cidr,
        "created_at": Network.created_at,
        "updated_at": Network.updated_at,
        "environment": Network.environment,
        "status": Network.status,
    }.get(sort, Network.created_at)
    stmt = stmt.order_by(sort_col.desc() if order.lower() == "desc" else sort_col.asc())
    rows = list(db.scalars(stmt).all())
    page_data = paginate(rows, page, page_size)
    page_data["items"] = [NetworkRead.model_validate(r).model_dump(mode="json") for r in page_data["items"]]
    return page_data


def get_network(db: Session, network_id: int) -> Network:
    obj = db.get(Network, network_id)
    if not obj:
        raise not_found("Network", network_id)
    return obj


def network_detail(db: Session, network_id: int) -> dict[str, Any]:
    obj = get_network(db, network_id)
    detail = subnet_details(parse_network(obj.cidr))
    return {
        **NetworkRead.model_validate(obj).model_dump(mode="json"),
        "details": detail,
        "subnets": [
            subnet_summary_data(s) for s in sorted(obj.subnets, key=lambda s: int(ipaddress.ip_network(s.cidr).network_address))
        ],
    }


def subnet_summary_data(s: Subnet) -> dict[str, Any]:
    return {
        "id": s.id,
        "name": s.name,
        "cidr": s.cidr,
        "prefix_length": s.prefix_length,
        "vlan_id": s.vlan_id,
        "gateway": s.gateway,
        "status": s.status,
        "description": s.description,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def update_network(db: Session, network_id: int, data: dict[str, Any]) -> Network:
    obj = get_network(db, network_id)
    if "name" in data and data["name"]:
        dup = db.scalar(
            select(Network).where(
                func.lower(Network.name) == data["name"].strip().lower(),
                Network.id != network_id,
            )
        )
        if dup:
            raise conflict("duplicate_name", f"A network named '{data['name']}' already exists")
        obj.name = data["name"].strip()
    for field in ("description", "environment", "site", "status"):
        if field in data and data[field] is not None:
            setattr(obj, field, data[field])
    db.flush()
    _audit(db, "network", obj.id, "update", f"Updated network {obj.name}")
    db.commit()
    db.refresh(obj)
    return obj


def delete_network(db: Session, network_id: int) -> None:
    obj = get_network(db, network_id)
    active = [s for s in obj.subnets if s.status in SUBNET_ACTIVE_STATES]
    if active:
        raise conflict(
            "network_not_empty",
            f"Network '{obj.name}' has {len(active)} active subnet(s); "
            "delete or release them first",
            [{"subnet_id": s.id, "cidr": s.cidr, "status": s.status} for s in active],
        )
    _audit(db, "network", obj.id, "delete", f"Deleted network {obj.name} ({obj.cidr})")
    db.delete(obj)
    db.commit()


# ---------------------------------------------------------------------------
# Subnets
# ---------------------------------------------------------------------------

def _check_subnet_geometry(
    db: Session,
    parent: Network,
    cidr: str,
    gateway: str | None,
    exclude_id: int | None = None,
) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ipaddress.IPv4Address | ipaddress.IPv6Address | None]:
    net = _parse_cidr_or_422(cidr, "cidr", family=parent.family)
    # reject input that only matches after host bits are cleared (e.g. 10.0.0.5/24)
    text = cidr.strip()
    if "/" in text:
        try:
            ipaddress.ip_network(text, strict=True)
        except ValueError as exc:
            raise validation_error(
                f"'{text}' has host bits set; use the network address {net}",
                [{"field": "cidr", "message": "network address does not match its prefix length"}],
            ) from exc
    parent_net = parse_network(parent.cidr)
    if net.version != parent_net.version:
        raise validation_error("Address family mismatch between subnet and parent network")
    if not net.subnet_of(parent_net):
        raise validation_error(
            f"{net} is not contained within parent network {parent.cidr}",
            [{"field": "cidr", "message": f"must be inside {parent.cidr}"}],
        )
    block = 1 << (net.max_prefixlen - net.prefixlen)
    if int(net.network_address) % block != 0:
        raise validation_error(
            f"{net} is not aligned to a /{net.prefixlen} boundary",
            [{"field": "cidr", "message": "network address does not match its prefix length"}],
        )
    # overlap with other active subnets of the same parent
    stmt = select(Subnet).where(
        Subnet.network_id == parent.id,
        Subnet.status.in_(SUBNET_ACTIVE_STATES),
    )
    if exclude_id:
        stmt = stmt.where(Subnet.id != exclude_id)
    for other in db.scalars(stmt):
        other_net = parse_network(other.cidr)
        if net.overlaps(other_net):
            raise conflict(
                "overlap",
                f"{net} overlaps existing subnet '{other.name}' ({other.cidr})",
                [{"subnet_id": other.id, "cidr": other.cidr}],
            )
    gw_addr = None
    if gateway:
        try:
            gw_addr = parse_address(gateway, family=net.version)
        except SubnetCalculationError as exc:
            raise validation_error(exc.message, [{"field": "gateway", "message": exc.message}]) from exc
        if not ipaddress.ip_network((gw_addr, gw_addr.max_prefixlen)).subnet_of(net):
            raise validation_error(
                f"Gateway {gw_addr} is outside subnet {net}",
                [{"field": "gateway", "message": "must be inside the subnet"}],
            )
        if net.version == 4 and net.prefixlen <= 30 and gw_addr in (net.network_address, net.broadcast_address):
            raise validation_error(
                f"Gateway {gw_addr} is the network or broadcast address of {net}",
                [{"field": "gateway", "message": "cannot be network/broadcast address"}],
            )
    return net, gw_addr


def create_subnet(db: Session, data: dict[str, Any]) -> Subnet:
    parent = get_network(db, data["network_id"])
    net, _ = _check_subnet_geometry(db, parent, data["cidr"], data.get("gateway"))
    dup = db.scalar(
        select(Subnet).where(Subnet.network_id == parent.id, Subnet.cidr == str(net))
    )
    if dup and dup.status != "released":
        raise conflict("duplicate_cidr", f"Subnet {net} already exists in network '{parent.name}'")
    if dup:
        # a released subnet owns the CIDR row; re-allocate it in place
        obj = dup
        obj.name = data["name"].strip()
        obj.prefix_length = net.prefixlen
        obj.vlan_id = data.get("vlan_id")
        obj.gateway = data.get("gateway")
        obj.status = data.get("status", "allocated")
        obj.description = data.get("description")
        db.flush()
        _audit(db, "subnet", obj.id, "create", f"Re-allocated subnet {obj.name} ({obj.cidr}) in {parent.name}")
        db.commit()
        db.refresh(obj)
        return obj
    obj = Subnet(
        network_id=parent.id,
        name=data["name"].strip(),
        cidr=str(net),
        prefix_length=net.prefixlen,
        vlan_id=data.get("vlan_id"),
        gateway=data.get("gateway"),
        status=data.get("status", "allocated"),
        description=data.get("description"),
    )
    db.add(obj)
    db.flush()
    _audit(db, "subnet", obj.id, "create", f"Created subnet {obj.name} ({obj.cidr}) in {parent.name}")
    db.commit()
    db.refresh(obj)
    return obj


def list_subnets(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 50,
    q: str | None = None,
    network_id: int | None = None,
    vlan_id: int | None = None,
    status: str | None = None,
    family: int | None = None,
    sort: str = "created_at",
    order: str = "desc",
) -> dict[str, Any]:
    stmt = select(Subnet).join(Network, Subnet.network_id == Network.id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Subnet.name.ilike(like),
                Subnet.cidr.ilike(like),
                Subnet.gateway.ilike(like),
                Subnet.description.ilike(like),
                Network.name.ilike(like),
            )
        )
    if network_id:
        stmt = stmt.where(Subnet.network_id == network_id)
    if vlan_id is not None:
        stmt = stmt.where(Subnet.vlan_id == vlan_id)
    if status:
        stmt = stmt.where(Subnet.status == status)
    if family:
        stmt = stmt.where(Network.family == family)
    sort_col = {
        "name": Subnet.name,
        "cidr": Subnet.cidr,
        "vlan_id": Subnet.vlan_id,
        "created_at": Subnet.created_at,
        "updated_at": Subnet.updated_at,
        "status": Subnet.status,
    }.get(sort, Subnet.created_at)
    stmt = stmt.order_by(sort_col.desc() if order.lower() == "desc" else sort_col.asc())
    rows = list(db.scalars(stmt).unique().all())
    page_data = paginate(rows, page, page_size)
    items = []
    for r in page_data["items"]:
        try:
            details = subnet_details(parse_network(r.cidr))
        except SubnetCalculationError:
            details = {}
        items.append(
            {
                **subnet_summary_data(r),
                "network_id": r.network_id,
                "family": details.get("family", 4),
                "details": details,
                "ip_address_count": len(r.ip_addresses),
            }
        )
    page_data["items"] = items
    return page_data


def get_subnet(db: Session, subnet_id: int) -> Subnet:
    obj = db.get(Subnet, subnet_id)
    if not obj:
        raise not_found("Subnet", subnet_id)
    return obj


def update_subnet(db: Session, subnet_id: int, data: dict[str, Any]) -> Subnet:
    obj = get_subnet(db, subnet_id)
    parent = get_network(db, obj.network_id)
    new_cidr = data.get("cidr") or obj.cidr
    new_gateway = data.get("gateway", obj.gateway)
    if "gateway" in data and data["gateway"] is None:
        new_gateway = None
    net, _ = _check_subnet_geometry(db, parent, new_cidr, new_gateway, exclude_id=obj.id)
    obj.cidr = str(net)
    obj.prefix_length = net.prefixlen
    obj.gateway = new_gateway
    for field in ("name", "vlan_id", "status", "description"):
        if field in data:
            setattr(obj, field, data[field])
    db.flush()
    _audit(db, "subnet", obj.id, "update", f"Updated subnet {obj.name} ({obj.cidr})")
    db.commit()
    db.refresh(obj)
    return obj


def delete_subnet(db: Session, subnet_id: int, force: bool = False) -> None:
    obj = get_subnet(db, subnet_id)
    blocking = [
        ip for ip in obj.ip_addresses
        if ip.status in ("assigned", "reserved")
    ]
    if blocking and not force:
        raise conflict(
            "subnet_not_empty",
            f"Subnet '{obj.name}' has {len(blocking)} assigned/reserved address(es); "
            "delete them first or pass force=true",
            [{"address_id": ip.id, "address": ip.address, "status": ip.status} for ip in blocking],
        )
    _audit(db, "subnet", obj.id, "delete", f"Deleted subnet {obj.name} ({obj.cidr})")
    db.delete(obj)
    db.commit()


# ---------------------------------------------------------------------------
# IP addresses
# ---------------------------------------------------------------------------

def create_ip_address(db: Session, data: dict[str, Any]) -> IPAddress:
    subnet = get_subnet(db, data["subnet_id"])
    try:
        addr = parse_address(data["address"], family=None)
    except SubnetCalculationError as exc:
        raise validation_error(exc.message, [{"field": "address", "message": exc.message}]) from exc
    parent = get_network(db, subnet.network_id)
    if addr.version != parent.family:
        raise validation_error(
            f"Address {addr} is IPv{addr.version} but subnet is IPv{parent.family}"
        )
    subnet_net = parse_network(subnet.cidr)
    if not ipaddress.ip_network((addr, addr.max_prefixlen)).subnet_of(subnet_net):
        raise validation_error(
            f"Address {addr} is outside subnet {subnet.cidr}",
            [{"field": "address", "message": f"must be inside {subnet.cidr}"}],
        )
    if (
        addr.version == 4
        and subnet_net.prefixlen <= 30
        and addr in (subnet_net.network_address, subnet_net.broadcast_address)
    ):
        raise validation_error(
            f"{addr} is the network or broadcast address of {subnet.cidr}",
            [{"field": "address", "message": "cannot register network/broadcast address"}],
        )
    dup = db.scalar(
        select(IPAddress).where(IPAddress.subnet_id == subnet.id, IPAddress.address == str(addr))
    )
    if dup and dup.status != "deprecated":
        raise conflict(
            "duplicate_assignment",
            f"{addr} is already registered in this subnet with status '{dup.status}'",
            [{"address_id": dup.id}],
        )
    if data.get("department_id") and not db.get(Department, data["department_id"]):
        raise not_found("Department", data["department_id"])
    if dup is not None:
        # Reuse the deprecated record so the (subnet, address) unique constraint holds.
        obj = dup
        obj.hostname = data.get("hostname")
        obj.device = data.get("device")
        obj.department_id = data.get("department_id")
        obj.status = data.get("status", "assigned")
        obj.description = data.get("description")
        obj.family = addr.version
    else:
        obj = IPAddress(
            address=str(addr),
            family=addr.version,
            subnet_id=subnet.id,
            hostname=data.get("hostname"),
            device=data.get("device"),
            department_id=data.get("department_id"),
            status=data.get("status", "assigned"),
            description=data.get("description"),
        )
        db.add(obj)
    db.flush()
    _audit(db, "ip_address", obj.id, "create", f"Registered {addr} in {subnet.cidr}")
    db.commit()
    db.refresh(obj)
    return obj


def list_ip_addresses(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 50,
    q: str | None = None,
    subnet_id: int | None = None,
    status: str | None = None,
    family: int | None = None,
    department_id: int | None = None,
    device: str | None = None,
    sort: str = "created_at",
    order: str = "desc",
) -> dict[str, Any]:
    stmt = select(IPAddress).join(Subnet, IPAddress.subnet_id == Subnet.id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                IPAddress.address.ilike(like),
                IPAddress.hostname.ilike(like),
                IPAddress.device.ilike(like),
                IPAddress.description.ilike(like),
                Subnet.cidr.ilike(like),
                Subnet.name.ilike(like),
            )
        )
    if subnet_id:
        stmt = stmt.where(IPAddress.subnet_id == subnet_id)
    if status:
        stmt = stmt.where(IPAddress.status == status)
    if family:
        stmt = stmt.where(IPAddress.family == family)
    if department_id:
        stmt = stmt.where(IPAddress.department_id == department_id)
    if device:
        stmt = stmt.where(IPAddress.device.ilike(f"%{device}%"))
    sort_col = {
        "address": IPAddress.address,
        "hostname": IPAddress.hostname,
        "status": IPAddress.status,
        "created_at": IPAddress.created_at,
        "updated_at": IPAddress.updated_at,
    }.get(sort, IPAddress.created_at)
    stmt = stmt.order_by(sort_col.desc() if order.lower() == "desc" else sort_col.asc())
    rows = list(db.scalars(stmt).unique().all())
    page_data = paginate(rows, page, page_size)
    page_data["items"] = [
        {
            "id": r.id,
            "subnet_id": r.subnet_id,
            "address": r.address,
            "family": r.family,
            "hostname": r.hostname,
            "device": r.device,
            "department_id": r.department_id,
            "status": r.status,
            "description": r.description,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in page_data["items"]
    ]
    return page_data


def get_ip_address(db: Session, address_id: int) -> IPAddress:
    obj = db.get(IPAddress, address_id)
    if not obj:
        raise not_found("IPAddress", address_id)
    return obj


def update_ip_address(db: Session, address_id: int, data: dict[str, Any]) -> IPAddress:
    obj = get_ip_address(db, address_id)
    if "department_id" in data and data["department_id"] and not db.get(Department, data["department_id"]):
        raise not_found("Department", data["department_id"])
    for field in ("hostname", "device", "department_id", "status", "description"):
        if field in data:
            setattr(obj, field, data[field])
    db.flush()
    _audit(db, "ip_address", obj.id, "update", f"Updated address {obj.address}")
    db.commit()
    db.refresh(obj)
    return obj


def delete_ip_address(db: Session, address_id: int) -> None:
    obj = get_ip_address(db, address_id)
    if obj.status == "assigned":
        raise conflict(
            "address_assigned",
            f"Address {obj.address} is assigned; set it to another status before deleting",
        )
    _audit(db, "ip_address", obj.id, "delete", f"Deleted address {obj.address}")
    db.delete(obj)
    db.commit()


# ---------------------------------------------------------------------------
# Departments
# ---------------------------------------------------------------------------

def create_department(db: Session, data: dict[str, Any]) -> Department:
    dup = db.scalar(select(Department).where(func.lower(Department.name) == data["name"].strip().lower()))
    if dup:
        raise conflict("duplicate_name", f"Department '{data['name']}' already exists")
    obj = Department(
        name=data["name"].strip(),
        description=data.get("description"),
        default_host_requirement=data.get("default_host_requirement", 10),
        vlan_id=data.get("vlan_id"),
        site=data.get("site"),
    )
    db.add(obj)
    db.flush()
    _audit(db, "department", obj.id, "create", f"Created department {obj.name}")
    db.commit()
    db.refresh(obj)
    return obj


def list_departments(db: Session, *, page: int, page_size: int, q: str | None) -> dict[str, Any]:
    stmt = select(Department)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Department.name.ilike(like), Department.site.ilike(like)))
    rows = list(db.scalars(stmt.order_by(Department.name)).all())
    page_data = paginate(rows, page, page_size)
    page_data["items"] = [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "default_host_requirement": r.default_host_requirement,
            "vlan_id": r.vlan_id,
            "site": r.site,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in page_data["items"]
    ]
    return page_data


def get_department(db: Session, department_id: int) -> Department:
    obj = db.get(Department, department_id)
    if not obj:
        raise not_found("Department", department_id)
    return obj


def update_department(db: Session, department_id: int, data: dict[str, Any]) -> Department:
    obj = get_department(db, department_id)
    for field in ("name", "description", "default_host_requirement", "vlan_id", "site"):
        if field in data and data[field] is not None:
            setattr(obj, field, data[field].strip() if field == "name" else data[field])
    db.flush()
    _audit(db, "department", obj.id, "update", f"Updated department {obj.name}")
    db.commit()
    db.refresh(obj)
    return obj


def delete_department(db: Session, department_id: int) -> None:
    obj = get_department(db, department_id)
    _audit(db, "department", obj.id, "delete", f"Deleted department {obj.name}")
    db.delete(obj)
    db.commit()


# ---------------------------------------------------------------------------
# Allocation plans
# ---------------------------------------------------------------------------

def _run_plan(base_network: str, depts: list[VLSMDepartment], policy_in: AllocationPolicyInput) -> dict[str, Any]:
    policy = _policy_from_input(policy_in)
    try:
        result = allocate(base_network, requirements_from_schemas(depts), policy)
    except VLSMError as exc:
        raise _vlsm_error_to_app_error(exc) from exc
    result["algorithm_version"] = settings.algorithm_version
    return result


def create_plan(db: Session, data: dict[str, Any]) -> AllocationPlan:
    result = _run_plan(data["base_network"], data["departments"], data.get("policy"))
    policy_in = data.get("policy")
    if isinstance(policy_in, AllocationPolicyInput):
        policy_dump = policy_in.model_dump(mode="json")
    else:
        policy_dump = AllocationPolicyInput(**(policy_in or {})).model_dump(mode="json")
    inputs = {
        "base_network": result["base_network"],
        "family": result["family"],
        "policy": policy_dump,
        "departments": [
            (d if isinstance(d, VLSMDepartment) else VLSMDepartment(**d)).model_dump(mode="json")
            for d in data["departments"]
        ],
    }
    dup = db.scalar(select(AllocationPlan).where(func.lower(AllocationPlan.name) == data["name"].strip().lower()))
    if dup:
        raise conflict("duplicate_name", f"An allocation plan named '{data['name']}' already exists")
    obj = AllocationPlan(
        name=data["name"].strip(),
        base_network=result["base_network"],
        family=result["family"],
        inputs=inputs,
        algorithm_version=settings.algorithm_version,
        results=result,
        status="draft",
        notes=data.get("notes"),
    )
    db.add(obj)
    db.flush()
    _audit(db, "allocation_plan", obj.id, "create", f"Saved plan '{obj.name}' for {obj.base_network}")
    db.commit()
    db.refresh(obj)
    return obj


def list_plans(db: Session, *, page: int, page_size: int, status: str | None, q: str | None) -> dict[str, Any]:
    stmt = select(AllocationPlan)
    if status:
        stmt = stmt.where(AllocationPlan.status == status)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(AllocationPlan.name.ilike(like), AllocationPlan.base_network.ilike(like)))
    rows = list(db.scalars(stmt.order_by(AllocationPlan.created_at.desc())).all())
    page_data = paginate(rows, page, page_size)
    page_data["items"] = [
        {
            "id": r.id,
            "name": r.name,
            "base_network": r.base_network,
            "family": r.family,
            "algorithm_version": r.algorithm_version,
            "status": r.status,
            "department_count": len(r.results.get("allocations", [])),
            "overall_utilization_percent": r.results.get("summary", {}).get("overall_utilization_percent", 0.0),
            "notes": r.notes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in page_data["items"]
    ]
    return page_data


def get_plan(db: Session, plan_id: int) -> AllocationPlan:
    obj = db.get(AllocationPlan, plan_id)
    if not obj:
        raise not_found("AllocationPlan", plan_id)
    return obj


def update_plan(db: Session, plan_id: int, data: dict[str, Any]) -> AllocationPlan:
    obj = get_plan(db, plan_id)
    for field in ("name", "notes"):
        if field in data and data[field] is not None:
            setattr(obj, field, data[field].strip() if field == "name" else data[field])
    db.flush()
    _audit(db, "allocation_plan", obj.id, "update", f"Updated plan '{obj.name}'")
    db.commit()
    db.refresh(obj)
    return obj


def recalculate_plan(db: Session, plan_id: int) -> AllocationPlan:
    """Recalculate from stored inputs. Never commits an active allocation."""
    obj = get_plan(db, plan_id)
    inputs = obj.inputs
    result = _run_plan(
        inputs["base_network"],
        [VLSMDepartment(**d) for d in inputs["departments"]],
        AllocationPolicyInput(**inputs.get("policy", {})),
    )
    obj.results = result
    obj.algorithm_version = settings.algorithm_version
    db.flush()
    _audit(db, "allocation_plan", obj.id, "recalculate", f"Recalculated plan '{obj.name}'")
    db.commit()
    db.refresh(obj)
    return obj


def activate_plan(db: Session, plan_id: int) -> dict[str, Any]:
    """Validate and commit a plan transactionally.

    Revalidates every allocation against the *current* database state inside a
    transaction: overlap, containment and duplicate names are re-checked so a
    plan that became stale (e.g. a subnet was created after preview) is rejected
    rather than silently committed.
    """
    obj = get_plan(db, plan_id)
    if obj.status == "archived":
        raise conflict("plan_archived", f"Plan '{obj.name}' is archived and cannot be activated")
    if obj.status == "active":
        raise conflict("plan_active", f"Plan '{obj.name}' is already active")

    allocations = obj.results.get("allocations", [])
    if not allocations:
        raise conflict("plan_empty", f"Plan '{obj.name}' has no allocations to activate")

    try:
        # find-or-create the parent network inside the same transaction
        parent = db.scalar(select(Network).where(Network.cidr == obj.base_network))
        if parent is None:
            parent = Network(
                name=f"Plan: {obj.name}"[:200],
                cidr=obj.base_network,
                family=obj.family,
                description=f"Created by activating allocation plan '{obj.name}'",
                environment="production",
                status="active",
            )
            db.add(parent)
            db.flush()

        created = 0
        for alloc in allocations:
            net = _parse_cidr_or_422(alloc["network"], "cidr", family=obj.family)
            if not net.subnet_of(parse_network(parent.cidr)):
                raise conflict("overlap", f"Allocation {net} is outside {parent.cidr}")
            for other in db.scalars(
                select(Subnet).where(
                    Subnet.network_id == parent.id,
                    Subnet.status.in_(SUBNET_ACTIVE_STATES),
                )
            ):
                if net.overlaps(parse_network(other.cidr)):
                    raise conflict(
                        "overlap",
                        f"Plan allocation {net} ('{alloc['department']}') overlaps existing "
                        f"subnet '{other.name}' ({other.cidr}); recalculate the plan",
                        [{"subnet_id": other.id, "cidr": other.cidr}],
                    )
            sub = Subnet(
                network_id=parent.id,
                name=str(alloc["department"])[:200],
                cidr=str(net),
                prefix_length=net.prefixlen,
                vlan_id=alloc.get("vlan_id"),
                gateway=alloc.get("gateway"),
                status="allocated",
                description=alloc.get("description"),
            )
            db.add(sub)
            created += 1

        obj.status = "active"
        _audit(
            db, "allocation_plan", obj.id, "activate",
            f"Activated plan '{obj.name}': {created} subnet(s) committed to network '{parent.name}'",
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(obj)
    return {
        "plan_id": obj.id,
        "status": obj.status,
        "subnets_created": created,
        "network_id": parent.id,
        "results": obj.results,
    }


def archive_plan(db: Session, plan_id: int) -> AllocationPlan:
    obj = get_plan(db, plan_id)
    if obj.status == "archived":
        raise conflict("plan_archived", f"Plan '{obj.name}' is already archived")
    obj.status = "archived"
    db.flush()
    _audit(db, "allocation_plan", obj.id, "archive", f"Archived plan '{obj.name}'")
    db.commit()
    db.refresh(obj)
    return obj


# ---------------------------------------------------------------------------
# Dashboard / audit
# ---------------------------------------------------------------------------

def network_utilization(db: Session, network: Network) -> dict[str, Any]:
    parent_net = parse_network(network.cidr)
    active = [s for s in network.subnets if s.status in SUBNET_ACTIVE_STATES]
    allocated = 0
    for s in active:
        allocated += parse_network(s.cidr).num_addresses
    total = parent_net.num_addresses
    return {
        "network_id": network.id,
        "name": network.name,
        "cidr": network.cidr,
        "allocated_addresses": allocated,
        "total_addresses": total,
        "utilization_percent": round(100.0 * allocated / total, 2) if total else 0.0,
        "subnet_count": len(active),
    }


def detect_conflicts(db: Session) -> list[dict[str, Any]]:
    """Detect overlapping active subnets across the whole inventory."""
    conflicts: list[dict[str, Any]] = []
    networks = list(db.scalars(select(Network)).all())
    for network in networks:
        active = [s for s in network.subnets if s.status in SUBNET_ACTIVE_STATES]
        for i, a in enumerate(active):
            net_a = parse_network(a.cidr)
            for b in active[i + 1 :]:
                if net_a.overlaps(parse_network(b.cidr)):
                    conflicts.append(
                        {
                            "type": "overlap",
                            "network_id": network.id,
                            "subnet_a": {"id": a.id, "name": a.name, "cidr": a.cidr},
                            "subnet_b": {"id": b.id, "name": b.name, "cidr": b.cidr},
                        }
                    )
    return conflicts


def dashboard_summary(db: Session) -> dict[str, Any]:
    networks = list(db.scalars(select(Network)).all())
    subnets = list(db.scalars(select(Subnet)).all())
    ips = list(db.scalars(select(IPAddress)).all())
    plans = list(db.scalars(select(AllocationPlan)).all())

    utilizations = [network_utilization(db, n) for n in networks]
    avg_util = (
        round(sum(u["utilization_percent"] for u in utilizations) / len(utilizations), 2)
        if utilizations
        else 0.0
    )
    ip_counts = {"available": 0, "reserved": 0, "assigned": 0, "deprecated": 0}
    for ip in ips:
        ip_counts[ip.status] = ip_counts.get(ip.status, 0) + 1

    recent = list(
        db.scalars(select(AuditEvent).order_by(AuditEvent.timestamp.desc()).limit(10)).all()
    )
    return {
        "total_networks": len(networks),
        "total_subnets": len([s for s in subnets if s.status in SUBNET_ACTIVE_STATES]),
        "total_ip_addresses": len(ips),
        "ip_available": ip_counts["available"],
        "ip_reserved": ip_counts["reserved"],
        "ip_assigned": ip_counts["assigned"],
        "ip_deprecated": ip_counts["deprecated"],
        "total_plans": len(plans),
        "active_plans": len([p for p in plans if p.status == "active"]),
        "average_utilization_percent": avg_util,
        "networks": utilizations,
        "conflicts": detect_conflicts(db),
        "near_capacity": [u for u in utilizations if u["utilization_percent"] >= 80],
        "recent_activity": [
            {
                "id": e.id,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "action": e.action,
                "summary": e.summary,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            }
            for e in recent
        ],
    }


def list_audit_events(
    db: Session, *, page: int, page_size: int, resource_type: str | None, action: str | None
) -> dict[str, Any]:
    stmt = select(AuditEvent)
    if resource_type:
        stmt = stmt.where(AuditEvent.resource_type == resource_type)
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    rows = list(db.scalars(stmt.order_by(AuditEvent.timestamp.desc())).all())
    page_data = paginate(rows, page, page_size)
    page_data["items"] = [
        {
            "id": r.id,
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
            "action": r.action,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "actor": r.actor,
            "summary": r.summary,
        }
        for r in page_data["items"]
    ]
    return page_data


__all__ = [
    "activate_plan",
    "archive_plan",
    "create_department",
    "create_ip_address",
    "create_network",
    "create_plan",
    "create_subnet",
    "dashboard_summary",
    "delete_department",
    "delete_ip_address",
    "delete_network",
    "delete_subnet",
    "detect_conflicts",
    "get_department",
    "get_ip_address",
    "get_network",
    "get_plan",
    "get_subnet",
    "list_audit_events",
    "list_departments",
    "list_ip_addresses",
    "list_networks",
    "list_plans",
    "list_subnets",
    "network_detail",
    "recalculate_plan",
    "update_department",
    "update_ip_address",
    "update_network",
    "update_plan",
    "update_subnet",
    "usable_capacity",
]
