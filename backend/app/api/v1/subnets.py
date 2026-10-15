"""Subnet inventory endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.inventory import SubnetCreate, SubnetRead, SubnetUpdate
from app.services import ipam_service

router = APIRouter()


@router.get("", summary="List subnets")
def list_subnets(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: str | None = Query(None),
    network_id: int | None = Query(None),
    vlan_id: int | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    family: int | None = Query(None),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
) -> dict:
    return ipam_service.list_subnets(
        db,
        page=page,
        page_size=page_size,
        q=q,
        network_id=network_id,
        vlan_id=vlan_id,
        status=status_filter,
        family=family,
        sort=sort,
        order=order,
    )


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create a subnet")
def create_subnet(payload: SubnetCreate, db: Session = Depends(get_db)) -> SubnetRead:
    obj = ipam_service.create_subnet(db, payload.model_dump())
    data = ipam_service.list_subnets(db, network_id=obj.network_id, q=obj.cidr, page_size=200)
    for item in data["items"]:
        if item["id"] == obj.id:
            return item  # type: ignore[return-value]
    raise AssertionError("created subnet not found")  # pragma: no cover


@router.get("/{subnet_id}", summary="Get a subnet")
def get_subnet(subnet_id: int, db: Session = Depends(get_db)) -> dict:
    obj = ipam_service.get_subnet(db, subnet_id)
    from app.services.subnet_calculator import parse_network, subnet_details

    return {
        **ipam_service.subnet_summary_data(obj),
        "network_id": obj.network_id,
        "family": subnet_details(parse_network(obj.cidr)).get("family", 4),
        "details": subnet_details(parse_network(obj.cidr)),
        "ip_address_count": len(obj.ip_addresses),
    }


@router.patch("/{subnet_id}", summary="Update a subnet")
def update_subnet(
    subnet_id: int, payload: SubnetUpdate, db: Session = Depends(get_db)
) -> SubnetRead:
    ipam_service.update_subnet(db, subnet_id, payload.model_dump(exclude_unset=True))
    return get_subnet(subnet_id, db)  # type: ignore[return-value]


@router.delete(
    "/{subnet_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a subnet"
)
def delete_subnet(
    subnet_id: int,
    force: bool = Query(False, description="Delete even when addresses are assigned/reserved"),
    db: Session = Depends(get_db),
) -> Response:
    ipam_service.delete_subnet(db, subnet_id, force=force)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
