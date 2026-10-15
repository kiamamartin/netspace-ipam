"""IP address inventory endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.inventory import IPAddressCreate, IPAddressRead, IPAddressUpdate
from app.services import ipam_service

router = APIRouter()


@router.get("", summary="List IP addresses")
def list_ip_addresses(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: str | None = Query(None),
    subnet_id: int | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    family: int | None = Query(None),
    department_id: int | None = Query(None),
    device: str | None = Query(None),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
) -> dict:
    return ipam_service.list_ip_addresses(
        db,
        page=page,
        page_size=page_size,
        q=q,
        subnet_id=subnet_id,
        status=status_filter,
        family=family,
        department_id=department_id,
        device=device,
        sort=sort,
        order=order,
    )


@router.post("", status_code=status.HTTP_201_CREATED, summary="Register an IP address")
def create_ip_address(payload: IPAddressCreate, db: Session = Depends(get_db)) -> IPAddressRead:
    return ipam_service.create_ip_address(db, payload.model_dump())


@router.get("/{address_id}", summary="Get an IP address")
def get_ip_address(address_id: int, db: Session = Depends(get_db)) -> IPAddressRead:
    return ipam_service.get_ip_address(db, address_id)


@router.patch("/{address_id}", summary="Update an IP address")
def update_ip_address(
    address_id: int, payload: IPAddressUpdate, db: Session = Depends(get_db)
) -> IPAddressRead:
    return ipam_service.update_ip_address(db, address_id, payload.model_dump(exclude_unset=True))


@router.delete(
    "/{address_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an IP address"
)
def delete_ip_address(address_id: int, db: Session = Depends(get_db)) -> Response:
    ipam_service.delete_ip_address(db, address_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
