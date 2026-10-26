import ipaddress
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    AllocationPlan,
    Department,
    IPAddress,
    Network,
    Subnet,
)
from app.models.audit import AuditEvent
from app.schemas.inventory import (
    AllocationPolicyInput,
    VLSMDepartment,
)
from app.services.subnet_calculator import (
    SubnetCalculationError,
    parse_network,
    subnet_details,
)
from app.services.vlsm_allocator import allocate

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _audit(
    db: Session,
    resource_type: str,
    resource_id: int,
    action: str,
    summary: str | None = None,
    actor: str | None = None,
) -> None:
    db.add(
        AuditEvent(
            actor=actor,
            resource_type=resource_type,
            resource_id=str(resource_id),
            action=action,
            summary=summary,
        )
    )


def _policy_from_input(
    policy: AllocationPolicyInput | dict[str, Any] | None,
) -> AllocationPolicyInput:
    if isinstance(policy, dict):
        return AllocationPolicyInput(**policy)
    return policy or AllocationPolicyInput()


def _parse_cidr_or_422(cidr: str, field: str = "cidr", family: int | None = None):
    try:
        net = parse_network(cidr, family=family)
    except SubnetCalculationError as exc:
        # codified so the app error handler maps it to 422 validation_error
        raise ValueError("invalid_cidr") from exc
    return net


SUBNET_ACTIVE_STATES = frozenset({"allocated", "active"})


def _vlsm_error_to_app_error(exc: Any) -> ValueError:
    """Translate allocator errors into codified ValueErrors (HTTP status mapping
    lives in app.core.errors). ``InsufficientSpaceError`` carries the allocator
    code ``insufficient_space`` (a capacity conflict -> 409)."""
    if exc.code in ("insufficient_space", "insufficient_capacity", "not_enough_subnets"):
        return ValueError(exc.code)
    return ValueError("vlsm_error")


# ---------------------------------------------------------------------------
# Networks
# ---------------------------------------------------------------------------


def create_network(db: Session, data: dict[str, Any], actor: str | None = None) -> Network:
    net = _parse_cidr_or_422(data["cidr"], "cidr")
    existing_name = db.scalar(
        select(Network).where(func.lower(Network.name) == data["name"].strip().lower())
    )
    if existing_name:
        raise ValueError("duplicate_name")
    existing_cidr = db.scalar(select(Network).where(Network.cidr == str(net)))
    if existing_cidr:
        raise ValueError("duplicate_cidr")
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
    _audit(db, "network", obj.id, "create", f"Created network {obj.name} ({obj.cidr})", actor=actor)
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
    stmt = stmt.order_by(
        sort_col.desc() if order.lower() == "desc" else sort_col.asc()
    )
    rows = list(db.scalars(stmt).all())
    items = [
        {
            "id": r.id,
            "name": r.name,
            "cidr": r.cidr,
            "family": r.family,
            "environment": r.environment,
            "site": r.site,
            "status": r.status,
            "description": r.description,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]
    start = (page - 1) * page_size
    total = len(items)
    paged = items[start : start + page_size]
    pages = max(1, -(-total // page_size))
    return {"items": paged, "page": page, "page_size": page_size, "total": total, "pages": pages}


def get_network(db: Session, network_id: int) -> Network | None:
    return db.get(Network, network_id)


def network_detail(db: Session, network_id: int) -> dict[str, Any]:
    obj = get_network(db, network_id)
    detail = subnet_details(parse_network(obj.cidr))
    return {
        **{
            "id": obj.id,
            "name": obj.name,
            "cidr": obj.cidr,
            "family": obj.family,
            "environment": obj.environment,
            "site": obj.site,
            "status": obj.status,
            "description": obj.description,
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
        },
        "details": detail,
        "subnets": [
            subnet_summary_data(s)
            for s in sorted(
                obj.subnets, key=lambda s: int(ipaddress.ip_network(s.cidr).network_address)
            )
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


def update_network(
    db: Session, network_id: int, data: dict[str, Any], actor: str | None = None
) -> Network:
    obj = get_network(db, network_id)
    if not obj:
        raise ValueError("not_found")
    if "name" in data and data["name"]:
        dup = db.scalar(
            select(Network).where(
                and_(Network.id != network_id, func.lower(Network.name) == data["name"].strip().lower())
            )
        )
        if dup:
            raise ValueError("duplicate_name")
        obj.name = data["name"].strip()
    if "environment" in data:
        obj.environment = data["environment"]
    if "site" in data:
        obj.site = data["site"]
    if "description" in data:
        obj.description = data["description"]
    if "status" in data:
        obj.status = data["status"]
    db.flush()
    _audit(db, "network", obj.id, "update", f"Updated network {obj.name}", actor=actor)
    db.commit()
    db.refresh(obj)
    return obj


def delete_network(db: Session, network_id: int, actor: str | None = None) -> None:
    obj = get_network(db, network_id)
    active = [s for s in obj.subnets if s.status in SUBNET_ACTIVE_STATES]
    if active:
        raise ValueError("network_not_empty")
    _audit(db, "network", obj.id, "delete", f"Deleted network {obj.name} ({obj.cidr})", actor=actor)
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
    # host-bit alignment (192.168.10.32/26 is a valid address, not a network boundary)
    try:
        ipaddress.ip_network(cidr, strict=True)
    except ValueError as exc:
        raise ValueError("misaligned_prefix") from exc
    # the child subnet must live inside its parent network
    parent_net = ipaddress.ip_network(parent.cidr)
    if not net.subnet_of(parent_net):
        raise ValueError("cidr_outside_parent")
    if gateway:
        gw_addr = ipaddress.ip_address(gateway)
        if ipaddress.ip_address(gateway) not in net:
            raise ValueError("gateway_out_of_range")
        # the gateway cannot be the network or broadcast address (IPv4, non /31, /32)
        if (
            gw_addr.version == 4
            and net.prefixlen not in (31, 32)
            and gw_addr in (net.network_address, net.broadcast_address)
        ):
            raise ValueError("gateway_reserved")
    else:
        gw_addr = None
    return net, gw_addr


def create_subnet(db: Session, data: dict[str, Any], actor: str | None = None) -> Subnet:
    parent = get_network(db, data["network_id"])
    net, _ = _check_subnet_geometry(db, parent, data["cidr"], data.get("gateway"))
    dup = db.scalar(
        select(Subnet).where(Subnet.network_id == parent.id, Subnet.cidr == str(net))
    )
    if dup and dup.status != "released":
        raise ValueError("duplicate_cidr")
    # overlapping active/released-pending siblings of the same parent are conflicts
    for other in db.scalars(
        select(Subnet).where(
            Subnet.network_id == parent.id,
            Subnet.status != "released",
        )
    ):
        if dup is not None and other.id == dup.id:
            continue
        if net.overlaps(ipaddress.ip_network(other.cidr)):
            raise ValueError("overlap")
    if dup:
        obj = dup
        obj.name = data["name"].strip()
        obj.prefix_length = net.prefixlen
        obj.vlan_id = data.get("vlan_id")
        obj.gateway = data.get("gateway")
        obj.status = data.get("status", "allocated")
        obj.description = data.get("description")
        db.flush()
        _audit(db, "subnet", obj.id, "create", f"Re-allocated subnet {obj.name} ({obj.cidr}) in {parent.name}", actor=actor)
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
    _audit(db, "subnet", obj.id, "create", f"Created subnet {obj.name} ({obj.cidr}) in {parent.name}", actor=actor)
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
    status_filter: str | None = None,
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
    if status_filter:
        stmt = stmt.where(Subnet.status == status_filter)
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
    stmt = stmt.order_by(
        sort_col.desc() if order.lower() == "desc" else sort_col.asc()
    )
    rows = list(db.scalars(stmt).unique().all())
    items = [
        {
            "id": r.id,
            "name": r.name,
            "cidr": r.cidr,
            "prefix_length": r.prefix_length,
            "vlan_id": r.vlan_id,
            "gateway": r.gateway,
            "status": r.status,
            "description": r.description,
            "network_id": r.network_id,
            "family": r.network.family,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]
    start = (page - 1) * page_size
    total = len(items)
    paged = items[start : start + page_size]
    pages = max(1, -(-total // page_size))
    return {"items": paged, "page": page, "page_size": page_size, "total": total, "pages": pages}


def get_subnet(db: Session, subnet_id: int) -> Subnet:
    obj = db.get(Subnet, subnet_id)
    if not obj:
        raise ValueError("not_found")
    return obj


def update_subnet(
    db: Session, subnet_id: int, data: dict[str, Any], actor: str | None = None
) -> Subnet:
    obj = get_subnet(db, subnet_id)
    parent = get_network(db, obj.network_id)
    if "name" in data and data["name"]:
        obj.name = data["name"].strip()
    if "gateway" in data and data["gateway"] is not None:
        net, gw_addr = _check_subnet_geometry(db, parent, obj.cidr, data["gateway"], exclude_id=subnet_id)
        obj.gateway = str(gw_addr) if gw_addr else None
    if "status" in data:
        obj.status = data["status"]
    if "description" in data:
        obj.description = data["description"]
    db.flush()
    _audit(db, "subnet", obj.id, "update", f"Updated subnet {obj.name} ({obj.cidr})", actor=actor)
    db.commit()
    db.refresh(obj)
    return obj


def delete_subnet(
    db: Session, subnet_id: int, *, force: bool = False, actor: str | None = None
) -> None:
    obj = get_subnet(db, subnet_id)
    if not force:
        active = [ip for ip in obj.ip_addresses if ip.status in ("assigned", "reserved")]
        if active:
            raise ValueError("subnet_not_empty")
    _audit(db, "subnet", obj.id, "delete", f"Deleted subnet {obj.name} ({obj.cidr} in {obj.network.name})", actor=actor)
    db.delete(obj)
    db.commit()


# ---------------------------------------------------------------------------
# IP addresses
# ---------------------------------------------------------------------------


def create_ip_address(db: Session, data: dict[str, Any], actor: str | None = None) -> IPAddress:
    subnet = get_subnet(db, data["subnet_id"])  # raises ValueError("not_found") -> 404
    try:
        addr = ipaddress.ip_address(data["address"])
    except ValueError as exc:
        raise ValueError("invalid_address") from exc
    net = ipaddress.ip_network(subnet.cidr)
    # the address must belong to the subnet it is registered in
    if addr not in net:
        raise ValueError("address_outside_subnet")
    # the network and broadcast addresses are reserved (IPv4, non /31, /32)
    if (
        addr.version == 4
        and net.prefixlen not in (31, 32)
        and addr in (net.network_address, net.broadcast_address)
    ):
        raise ValueError("reserved_address")
    dup = db.scalar(
        select(IPAddress).where(
            IPAddress.subnet_id == subnet.id, IPAddress.address == data["address"]
        )
    )
    if dup is not None:
        # an active/reserved record collides with the registration
        if dup.status != "deprecated":
            raise ValueError("duplicate_assignment")
        # a deprecated record is reused for the re-registration
        dup.hostname = data.get("hostname")
        dup.device = data.get("device")
        dup.status = data.get("status", "assigned")
        dup.department_id = data.get("department_id")
        dup.description = data.get("description")
        db.flush()
        _audit(db, "ip_address", dup.id, "update", f"Re-registered IP {dup.address} in {subnet.name}", actor=actor)
        db.commit()
        db.refresh(dup)
        return dup
    obj = IPAddress(
        subnet_id=subnet.id,
        address=data["address"],
        family=addr.version,
        hostname=data.get("hostname"),
        device=data.get("device"),
        department_id=data.get("department_id"),
        status=data.get("status", "assigned"),
        description=data.get("description"),
    )
    db.add(obj)
    db.flush()
    _audit(db, "ip_address", obj.id, "create", f"Registered IP {obj.address} in {subnet.name}", actor=actor)
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
    status_filter: str | None = None,
    family: int | None = None,
    department_id: int | None = None,
    device: str | None = None,
    sort: str = "created_at",
    order: str = "desc",
) -> dict[str, Any]:
    stmt = select(IPAddress).join(Subnet, IPAddress.subnet_id == Subnet.id).join(Network, Subnet.network_id == Network.id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                IPAddress.address.ilike(like),
                IPAddress.hostname.ilike(like),
                IPAddress.device.ilike(like),
                IPAddress.description.ilike(like),
            )
        )
    if subnet_id:
        stmt = stmt.where(IPAddress.subnet_id == subnet_id)
    if status_filter:
        stmt = stmt.where(IPAddress.status == status_filter)
    if family:
        stmt = stmt.where(Network.family == family)
    if department_id:
        stmt = stmt.where(IPAddress.department_id == department_id)
    if device:
        stmt = stmt.where(IPAddress.device.ilike(f"%{device.strip()}%"))
    sort_col = {
        "address": IPAddress.address,
        "hostname": IPAddress.hostname,
        "device": IPAddress.device,
        "created_at": IPAddress.created_at,
        "updated_at": IPAddress.updated_at,
        "status": IPAddress.status,
    }.get(sort, IPAddress.created_at)
    stmt = stmt.order_by(
        sort_col.desc() if order.lower() == "desc" else sort_col.asc()
    )
    rows = list(db.scalars(stmt).unique().all())
    items = [
        {
            "id": r.id,
            "address": r.address,
            "hostname": r.hostname,
            "device": r.device,
            "family": r.family,
            "department_id": r.department_id,
            "status": r.status,
            "description": r.description,
            "subnet_id": r.subnet_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]
    start = (page - 1) * page_size
    total = len(items)
    paged = items[start : start + page_size]
    pages = max(1, -(-total // page_size))
    return {"items": paged, "page": page, "page_size": page_size, "total": total, "pages": pages}


def get_ip_address(db: Session, address_id: int) -> IPAddress:
    obj = db.get(IPAddress, address_id)
    if not obj:
        raise ValueError("not_found")
    return obj


def update_ip_address(
    db: Session, address_id: int, data: dict[str, Any], actor: str | None = None
) -> IPAddress:
    obj = get_ip_address(db, address_id)
    if "hostname" in data:
        obj.hostname = data["hostname"]
    if "device" in data:
        obj.device = data["device"]
    if "status" in data:
        obj.status = data["status"]
    if "department_id" in data:
        obj.department_id = data["department_id"]
    if "description" in data:
        obj.description = data["description"]
    db.flush()
    _audit(db, "ip_address", obj.id, "update", f"Updated IP {obj.address} ({obj.hostname or 'no hostname'})", actor=actor)
    db.commit()
    db.refresh(obj)
    return obj


def delete_ip_address(db: Session, address_id: int, actor: str | None = None) -> None:
    obj = get_ip_address(db, address_id)
    # an address still assigned to a device cannot be removed; deprecate first
    if obj.status == "assigned":
        raise ValueError("ip_assigned")
    _audit(db, "ip_address", obj.id, "delete", f"Deleted IP {obj.address} ({obj.hostname or 'no hostname'})", actor=actor)
    db.delete(obj)
    db.commit()


# ---------------------------------------------------------------------------
# Departments
# ---------------------------------------------------------------------------


def create_department(db: Session, data: dict[str, Any], actor: str | None = None) -> Department:
    dup = db.scalar(
        select(Department).where(func.lower(Department.name) == data["name"].strip().lower())
    )
    if dup:
        raise ValueError("duplicate_name")
    obj = Department(
        name=data["name"].strip(),
        description=data.get("description"),
        default_host_requirement=data.get("default_host_requirement", 10),
        vlan_id=data.get("vlan_id"),
        site=data.get("site"),
    )
    db.add(obj)
    db.flush()
    _audit(db, "department", obj.id, "create", f"Created department {obj.name}", actor=actor)
    db.commit()
    db.refresh(obj)
    return obj


def list_departments(db: Session, *, page: int, page_size: int, q: str | None) -> dict[str, Any]:
    stmt = select(Department)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Department.name.ilike(like), Department.site.ilike(like)))
    rows = list(db.scalars(stmt.order_by(Department.name)).all())
    items = [
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
        for r in rows
    ]
    start = (page - 1) * page_size
    total = len(items)
    paged = items[start : start + page_size]
    pages = max(1, -(-total // page_size))
    return {"items": paged, "page": page, "page_size": page_size, "total": total, "pages": pages}


def get_department(db: Session, department_id: int) -> Department:
    obj = db.get(Department, department_id)
    if not obj:
        raise ValueError("not_found")
    return obj


def update_department(
    db: Session, department_id: int, data: dict[str, Any], actor: str | None = None
) -> Department:
    obj = get_department(db, department_id)
    if "name" in data and data["name"]:
        obj.name = data["name"].strip()
    if "description" in data:
        obj.description = data["description"]
    if "default_host_requirement" in data:
        obj.default_host_requirement = data["default_host_requirement"]
    if "vlan_id" in data:
        obj.vlan_id = data["vlan_id"]
    if "site" in data:
        obj.site = data["site"]
    db.flush()
    _audit(db, "department", obj.id, "update", f"Updated department {obj.name}", actor=actor)
    db.commit()
    db.refresh(obj)
    return obj


def delete_department(db: Session, department_id: int, actor: str | None = None) -> None:
    obj = get_department(db, department_id)
    _audit(db, "department", obj.id, "delete", f"Deleted department {obj.name}", actor=actor)
    db.delete(obj)
    db.commit()


# ---------------------------------------------------------------------------
# Allocation plans
# ---------------------------------------------------------------------------


def _run_plan(base_network: str, depts: list[VLSMDepartment], policy_in: AllocationPolicyInput) -> dict[str, Any]:
    policy = _policy_from_input(policy_in)
    try:
        from app.services.vlsm_allocator import VLSMError

        result = allocate(base_network, depts, policy)
    except VLSMError as exc:
        raise _vlsm_error_to_app_error(exc) from exc
    result["algorithm_version"] = get_settings().algorithm_version
    return result


def create_plan(
    db: Session, data: dict[str, Any], actor: str | None = None
) -> AllocationPlan:
    result = _run_plan(data["base_network"], [VLSMDepartment(**d) for d in data["departments"]], _policy_from_input(data.get("policy")))
    policy_dump = _policy_from_input(data.get("policy")).model_dump(mode="json")
    inputs = {
        "base_network": result["base_network"],
        "family": result["family"],
        "policy": policy_dump,
        "departments": [VLSMDepartment(**d).model_dump(mode="json") for d in data["departments"]],
    }
    dup = db.scalar(
        select(AllocationPlan).where(func.lower(AllocationPlan.name) == data["name"].strip().lower())
    )
    if dup:
        raise ValueError("duplicate_name")
    obj = AllocationPlan(
        name=data["name"].strip(),
        base_network=result["base_network"],
        family=result["family"],
        inputs=inputs,
        algorithm_version=result["algorithm_version"],
        results=result,
        status="draft",
        notes=data.get("notes"),
    )
    db.add(obj)
    db.flush()
    _audit(db, "allocation_plan", obj.id, "create", f"Saved plan '{obj.name}' for {obj.base_network}", actor=actor)
    db.commit()
    db.refresh(obj)
    return obj


def list_plans(
    db: Session,
    *,
    page: int,
    page_size: int,
    status_filter: str | None,
    q: str | None,
) -> dict[str, Any]:
    stmt = select(AllocationPlan)
    if status_filter:
        stmt = stmt.where(AllocationPlan.status == status_filter)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(AllocationPlan.name.ilike(like), AllocationPlan.base_network.ilike(like)))
    rows = list(db.scalars(stmt.order_by(AllocationPlan.created_at.desc())).all())
    items = [
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
        for r in rows
    ]
    return {"items": items, "page": page, "page_size": page_size, "total": len(items)}


def get_plan(db: Session, plan_id: int) -> AllocationPlan:
    obj = db.get(AllocationPlan, plan_id)
    if not obj:
        raise ValueError("not_found")
    return obj


def update_plan(
    db: Session, plan_id: int, data: dict[str, Any], actor: str | None = None
) -> AllocationPlan:
    obj = get_plan(db, plan_id)
    if "name" in data and data["name"]:
        dup = db.scalar(
            select(AllocationPlan).where(
                and_(AllocationPlan.id != plan_id, func.lower(AllocationPlan.name) == data["name"].strip().lower())
            )
        )
        if dup:
            raise ValueError("duplicate_name")
        obj.name = data["name"].strip()
    if "notes" in data:
        obj.notes = data["notes"]
    db.flush()
    _audit(db, "allocation_plan", obj.id, "update", f"Updated plan '{obj.name}'", actor=actor)
    db.commit()
    db.refresh(obj)
    return obj


def recalculate_plan(db: Session, plan_id: int, actor: str | None = None) -> AllocationPlan:
    obj = get_plan(db, plan_id)
    inputs = obj.inputs
    result = _run_plan(
        inputs["base_network"],
        [VLSMDepartment(**d) for d in inputs["departments"]],
        AllocationPolicyInput(**inputs.get("policy", {})),
    )
    obj.results = result
    obj.algorithm_version = result["algorithm_version"]
    db.flush()
    _audit(db, "allocation_plan", obj.id, "recalculate", f"Recalculated plan '{obj.name}'", actor=actor)
    db.commit()
    db.refresh(obj)
    return obj


def activate_plan(db: Session, plan_id: int, actor: str | None = None) -> dict[str, Any]:
    obj = get_plan(db, plan_id)
    if obj.status == "archived":
        raise ValueError("plan_archived")
    if obj.status == "active":
        raise ValueError("plan_active")
    allocations = obj.results.get("allocations", [])
    if not allocations:
        raise ValueError("plan_empty")
    try:
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
                raise ValueError("overlap")
            for other in db.scalars(
                select(Subnet).where(Subnet.network_id == parent.id, Subnet.status.in_(SUBNET_ACTIVE_STATES))
            ):
                if net.overlaps(parse_network(other.cidr)):
                    raise ValueError("overlap")
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
            db,
            "allocation_plan",
            obj.id,
            "activate",
            f"Activated plan '{obj.name}': {created} subnet(s) committed to network '{parent.name}'",
            actor=actor,
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


def archive_plan(db: Session, plan_id: int, actor: str | None = None) -> AllocationPlan:
    obj = get_plan(db, plan_id)
    if obj.status == "archived":
        raise ValueError("plan_archived")
    obj.status = "archived"
    db.flush()
    _audit(db, "allocation_plan", obj.id, "archive", f"Archived plan '{obj.name}'", actor=actor)
    db.commit()
    db.refresh(obj)
    return obj


# ---------------------------------------------------------------------------
# Dashboard / audit
# ---------------------------------------------------------------------------


def network_utilization(db: Session, network: Network) -> dict[str, Any]:
    parent_net = parse_network(network.cidr)
    active = [s for s in network.subnets if s.status in SUBNET_ACTIVE_STATES]
    allocated = sum(parse_network(s.cidr).num_addresses for s in active)
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
    conflicts: list[dict[str, Any]] = []
    networks = list(db.scalars(select(Network)).all())
    for network in networks:
        active = [s for s in network.subnets if s.status in SUBNET_ACTIVE_STATES]
        for i, a in enumerate(active):
            net_a = parse_network(a.cidr)
            for b in active[i + 1:]:
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
    recent = list(db.scalars(select(AuditEvent).order_by(AuditEvent.timestamp.desc()).limit(10)).all())
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
    db: Session,
    *,
    page: int,
    page_size: int,
    resource_type: str | None,
    action: str | None,
) -> dict[str, Any]:
    stmt = select(AuditEvent)
    if resource_type:
        stmt = stmt.where(AuditEvent.resource_type == resource_type)
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    rows = list(db.scalars(stmt.order_by(AuditEvent.timestamp.desc())).all())
    items = [
        {
            "id": r.id,
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
            "action": r.action,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "actor": r.actor,
            "summary": r.summary,
        }
        for r in rows
    ]
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": len(rows),
    }
